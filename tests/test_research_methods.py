import itertools
import json
import subprocess
import sys
from pathlib import Path
import pytest
from sips_runtime.methods import analyze
from sips_runtime.events import RevisionConflict
from test_adaptive_core import setup_episode
from agent_patterns import classify_outcomes, extract_approach_metrics


def design():
    return {'hypotheses':['a','b','c'],'probes':[
        {'id':'cheap','cost_seconds':1,'predictions':{'a':'passed','b':'failed','c':'unavailable'}},
        {'id':'expensive','cost_seconds':10,'predictions':{'a':'passed','b':'failed','c':'passed'}}],'budget_seconds':1}


def test_probe_selection_cost_and_unavailable():
    result=analyze('diagnosis',design())
    assert result['selected_probes']==['cheap']
    assert result['distinguished_pairs']==1
    assert result['intrinsically_unseparated_pairs']==[['a','c']]
    assert result['activation']=='none' and result['acceptance']=='not_evaluated'
    assert result==analyze('diagnosis',design())


def test_coverage_exact_feasible_interactions():
    request={'factors':{'a':[0,1],'b':[0,1],'c':[0,1]},'forbidden':[{'a':1,'b':1}]}
    result=analyze('coverage',request)
    assert result['status']=='complete' and not result['uncovered']
    assert all(not (row['a']==row['b']==1) for row in result['cases'])
    feasible=[dict(zip('abc',v)) for v in itertools.product([0,1],repeat=3) if not (v[0]==v[1]==1)]
    for keys in itertools.combinations('abc',2):
        assert {tuple(r[k] for k in keys) for r in feasible}=={tuple(r[k] for k in keys) for r in result['cases']}
    assert analyze('coverage',{**request,'max_cases':1})['status']=='bounded_incomplete'


def test_no_feasible_and_scalar_types():
    assert analyze('coverage',{'factors':{'x':[1]},'strength':1,'forbidden':[{'x':1}]})['status']=='no_feasible_configurations'
    result=analyze('coverage',{'factors':{'x':[True,1]},'strength':1,'forbidden':[{'x':True}]})
    assert result['cases']==[{'x':1}] and type(result['cases'][0]['x']) is int
    assert analyze('morphology',{'factors':{'x':[1,2]},'strength':1})['control']['intervention']=='no_change'


@pytest.mark.parametrize('method,payload',[
    ('coverage',{'factors':{'x':[1,1]},'strength':1}),
    ('coverage',{'factors':{'x':[float('nan')]},'strength':1}),
    ('coverage',{'factors':{str(i):list(range(8)) for i in range(5)}}),
    ('coverage',{'factors':{'x':[1]},'strength':True}),
    ('diagnosis',{'hypotheses':['a','a']}),
    ('diagnosis',{'hypotheses':['a'],'budget_seconds':601}),
    ('drift',{'baseline':[1,2,3,4,5],'samples':[2],'baseline_identity':'a','sample_identity':'b'}),
    ('assumptions',{'facts':{},'rules':[{'id':'x','conclusion':'x','value':True,'premises':{}}]}),
])
def test_bounds(method,payload):
    with pytest.raises(ValueError): analyze(method,payload)


def test_assumption_cycles_retraction_and_contradictions():
    rules=[{'id':'ab','conclusion':'b','value':True,'premises':{'a':True}}, {'id':'ba','conclusion':'a','value':True,'premises':{'b':True}}]
    assert analyze('assumptions',{'facts':{},'rules':rules})['claims']['b']['state']=='unknown'
    facts={'a':{'state':'inconsistent','evidence':['receipt:1']},'unrelated':{'state':'supported'}}
    result=analyze('assumptions',{'facts':facts,'rules':rules})
    assert result['claims']['b']['evidence']==['receipt:1']
    assert result['inconsistent']==['a'] and result['claims']['unrelated']['state']=='unknown'
    facts['a']['evidence']=[]
    assert analyze('assumptions',{'facts':facts,'rules':rules})['claims']['b']['state']=='unknown'


def test_drift_missing_and_degenerate_baseline():
    request={'baseline':[9,10,11,10,10],'samples':[None,100],'baseline_identity':'metric-v1','sample_identity':'metric-v1'}
    result=analyze('drift',request)
    assert result['missing']==1 and result['signals']==1
    assert result['rows'][0]=={'index':0,'status':'unavailable'}
    assert analyze('drift',{**request,'baseline':[1]*5})['status']=='unavailable'


def test_cli_is_read_only_and_matches_library(tmp_path):
    request=tmp_path/'input.json';request.write_text(json.dumps(design()))
    script=Path(__file__).resolve().parents[1]/'scripts/research_methods.py'
    result=subprocess.run([sys.executable,str(script),'diagnosis','--request-file',str(request)],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==analyze('diagnosis',design())
    assert list(tmp_path.iterdir())==[request]


def test_controller_method_idempotency_revision_and_no_activation(tmp_path):
    c,r,root,_=setup_episode(tmp_path)
    request={'episode':r['episode'],'expected_revision':r['revision'],'idempotency_key':'method','method':'diagnosis','input':design()}
    result=c.write('analyze',request)
    assert result['state']=='observed' and len(result['method_results'])==1
    assert c.write('analyze',request)==result
    with pytest.raises(RevisionConflict): c.write('analyze',{**request,'idempotency_key':'stale'})
    assert (root/'helper.py').read_text()=='print("wrong")\n'


def test_unknown_metrics_and_conflicting_outcomes():
    records=[{'tags':['outcome','success','failure'],'body':'tool_calls: 3'},
             {'tags':['outcome','success'],'body':'tool_calls: invalid'},
             {'tags':['outcome','failure'],'body':'tool_calls: 0'}]
    result=classify_outcomes(records)
    assert result['unknown']==1 and result['success_rate']==.5
    metrics=extract_approach_metrics(records)
    assert len(metrics)==2 and 'tool_calls' not in metrics[0] and metrics[1]['tool_calls']==0


def test_mcp_parity_and_invalid_requests():
    from harness_homebase_mcp import handle_request
    message={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'homebase_method','arguments':{'method':'diagnosis','request_json':json.dumps(design())}}}
    result=handle_request(message)
    assert result['result']['structuredContent']==analyze('diagnosis',design())
    message['params']['arguments']['request_json']='{"hypotheses":["a"],"probes":[null]}'
    assert handle_request(message)['error']['code']==-32602


def test_packaged_method_contract():
    from tool_contracts import validate
    result=validate(Path(__file__).resolve().parents[1]/'scripts/research_methods.py')
    assert result['ok'],result
    assert len(result['cases'])==3
