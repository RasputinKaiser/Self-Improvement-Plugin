import copy
import json
from pathlib import Path
import sys
import time
import pytest
from sips_runtime.adaptation import AdaptationController
from sips_runtime.canonical import canonical_hash
from sips_runtime.hypergraph import compose,compatible,invalidated,schema
from sips_runtime.investigation import investigation,reduce_failure
from sips_runtime.procedures import motif,validate_policy,rank_policy,retrieve,pareto
from sips_runtime.evaluation import check
from test_adaptive_core import setup_episode,step,build


def scalar(kind='string',version=1): return {'type':kind,'schema_version':version}
def tool(name='parse',inputs=None,outputs=None):
    return {'schema':'sips.tool-contract.v2','id':name,'status':'implemented','version':'1',
            'inputs':inputs or {'raw':scalar()},'outputs':outputs or {'parsed':scalar('integer')},
            'preconditions':['local'],'resources':[],'dependencies':[],'consumers':['consumer'],
            'bindings':{k:k for k in (inputs or {'raw':scalar()})},'effects':{'reads':[],'writes':[]},
            'validation_status':'current'}


def test_hypergraph_joint_inputs_bindings_and_backward_search():
    a=tool();b=tool('render',{'n':scalar('integer'),'format':scalar('boolean')},{'report':scalar('object')})
    assert compose([a,b],{'raw':scalar()},{'out':scalar('object')},prerequisites=['local'])['status']=='insufficient_fit'
    result=compose([a,b],{'raw':scalar(),'flag':scalar('boolean')},{'out':scalar('object')},prerequisites=['local'])
    assert result['status']=='proposed' and [s['tool'] for s in result['steps']]==['parse','render']
    assert result['steps'][1]['bindings']=={'n':'parse.parsed','format':'flag'}
    assert result['consumer_validation']=='required'


@pytest.mark.parametrize('change',[{'validation_status':'stale'}, {'preconditions':['missing']}, {'dependencies':['dep'],'resources':['dep']}, {'outputs':{'n':scalar('integer',2)}}])
def test_planner_rejects_stale_prerequisites_dependencies_versions(change):
    assert compose([{**tool(),**change}],{'raw':scalar()},{'n':scalar('integer')},prerequisites=['local'])['status']=='insufficient_fit'


def test_planner_rejects_effect_conflict_cycles_and_ambiguity():
    a=tool();b=tool('next',{'n':scalar('integer')},{'b':scalar('boolean')})
    a['effects']['writes']=['same'];b['effects']['writes']=['same']
    assert compose([a,b],{'raw':scalar()},{'b':scalar('boolean')},prerequisites=['local'])['status']=='insufficient_fit'
    assert compose([tool()],{'a':scalar(),'b':scalar()},{'n':scalar('integer')},prerequisites=['local'])['status']=='insufficient_fit'
    cyclic=tool('cycle',{'i':scalar('integer')},{'o':scalar()})
    assert compose([tool(),cyclic],{}, {'o':scalar()},prerequisites=['local'])['status']=='insufficient_fit'


def test_structural_objects_and_dependencies():
    required={'type':'object','properties':{'n':scalar('integer')},'required':['n'],'additionalProperties':False}
    assert compatible(required,required)
    assert not compatible({**required,'required':[]},required)
    assert not compatible({**required,'properties':{**required['properties'],'x':scalar()}},required)
    with pytest.raises(ValueError): schema({'type':'string','pattern':'.*'})
    assert invalidated({'dep':'old'},{'dep':'new'},{'tool':['dep'],'plan':['tool'],'other':[]})==['dep','plan','tool']


def hypotheses(): return [{'id':'implementation','claim':'wrong helper'}, {'id':'environment','claim':'missing dependency'}]
def probes(): return [{'id':'replay','check':{'kind':'command','argv':['{python}','helper.py'],'stdout':'right\n'},'cost_seconds':1,'reversible':True,'predictions':{'implementation':'failed','environment':'unavailable'}}]


def test_investigation_probe_durable_idempotency_and_conclusion(tmp_path):
    c,r,root,_=setup_episode(tmp_path)
    r=step(c,r,'investigate',hypotheses=hypotheses(),probes=probes())
    request={'episode':r['episode'],'expected_revision':r['revision'],'idempotency_key':'probe','probe':'replay'}
    r=c.write('probe',request)
    assert r['investigation']['results'][0]['supports']==['implementation']
    assert r['evidence'][-1]['receipt']['result']['command']
    assert c.write('probe',request)['revision']==r['revision']
    assert c.read(r['episode'],'investigation')['investigation']['results']
    r=step(c,r,'conclude',outcome='stop',rationale='No useful intervention')
    assert r['state']=='canceled' and not (c.directory(r['episode'])/'candidate').exists()


def test_probe_recovery_and_timeout_cannot_support(tmp_path):
    from sips_runtime.events import EventStore
    from sips_runtime.investigation import execute
    result=execute({**probes()[0],'check':{'kind':'command','argv':['missing-command-sips'],'stdout':''}},tmp_path,tmp_path,1,1,{})
    assert result['supports']==result['contradicts']==[]
    c,r,_,_=setup_episode(tmp_path)
    state={k:v for k,v in r.items() if k not in {'episode','revision'}}
    state.update(probe_running='x',probe_started_at=time.time()-1)
    EventStore(c.directory(r['episode'])).append('interrupted',r['episode'],{'state':state})
    r=c.read(r['episode'])
    with pytest.raises(ValueError,match='recovery'): step(c,r,'diagnose')
    r=step(c,r,'recover');assert r['state']=='unavailable' and r['evaluation_seconds']>=1


def test_reducer_and_property_checks(tmp_path, monkeypatch):
    spec={'kind':'command','argv':['{python}','-c','import sys;print("bug" if "x" in sys.argv[1] else "ok")','{input}'],'stdout':'bug\n'}
    # Verify the subprocess contract once; reduction order must not depend on
    # interpreter startup latency under CI or concurrent host load.
    original={**spec,'argv':[a.replace('{input}','abcxdef') for a in spec['argv']]}
    assert check(original,tmp_path,tmp_path,5)['status']=='passed'
    with monkeypatch.context() as patch:
        patch.setattr('sips_runtime.investigation.check',lambda case,*args:
                      {'status':'passed' if 'x' in case['argv'][-1] else 'failed'})
        a=reduce_failure(spec,'abcxdef',tmp_path,tmp_path,1,10)
        b=reduce_failure(spec,'abcxdef',tmp_path,tmp_path,1,10)
        assert a['reduced']==b['reduced']=='x'
        assert a['status']==b['status']=='deletion_minimal'
        assert [r['input'] for r in a['checks']]==[r['input'] for r in b['checks']]
        bounded=reduce_failure(spec,'abcxdef',tmp_path,tmp_path,1,10,max_checks=1)
        assert bounded['status']=='bounded' and bounded['reduced']=='abcxdef'
        patch.setattr('sips_runtime.investigation.check',lambda *args: {'status':'unavailable'})
        assert reduce_failure(spec,'abcxdef',tmp_path,tmp_path,1,10)['status']=='unavailable'
    for relation in ['identity','idempotent']:
        case={'kind':'property','seed':4,'samples':4,'generator':{'min':-3,'max':3},'relation':relation,'argv':['{python}','-c','import sys;print(sys.argv[1])','{input}']}
        assert check(case,tmp_path,tmp_path,5)['status']=='passed'
        case['argv'][2]='print(99)'
        if relation=='identity': assert check(case,tmp_path,tmp_path,5)['status']=='failed'


def test_counterexamples_additive_and_replayed(tmp_path):
    c,r,_,_=setup_episode(tmp_path);r=build(c,r)
    old=r['suite_digest']; original=(c.directory(r['episode'])/'suite.json').read_bytes()
    r=step(c,r,'add_counterexamples',checks=[{'kind':'artifact','path':'helper.py','text':'not right'}])
    assert r['prior_suite_digest']==old and r['suite_digest']!=old
    assert (c.directory(r['episode'])/'suite.json').read_bytes()==original
    r=step(c,r,'evaluate');assert r['state']=='rejected'
    reports=c.read(r['episode'],'receipt')['results']['reports']
    assert reports['candidate']['groups']['counterexamples'][-1]['status']=='failed'
    assert reports['baseline']['suite_digest']==reports['candidate']['suite_digest']


def policy(): return {'schema':'sips.policy.v1','kind':'diagnosis','scope':'diagnosis','version':'1','inputs':['features'],'outputs':['ranking'],'description':'bounded','weights':{'discrimination':2,'cost':1,'reversibility':1}}


def test_policy_surface_and_rank():
    with pytest.raises(ValueError): validate_policy({**policy(),'evaluator':'override'})
    with pytest.raises(ValueError): validate_policy({**policy(),'scope':'activation'})
    with pytest.raises(ValueError): validate_policy({**policy(),'weights':{'discrimination':float('nan')}})
    assert rank_policy(policy(),[{'id':'a','features':{'discrimination':1,'cost':0,'reversibility':1}},{'id':'b','features':{'discrimination':0,'cost':1,'reversibility':1}}])[0]['id']=='a'


def procedure():
    return {'schema':'sips.procedure.v1','version':'1','task':'repair parser schema','applicability':{'schema':2},
            'actions':[{'action':'inspect','arg':'$first'}], 'bindings':{},'expected_evidence':['replay'],
            'failure_modes':['environment unavailable'],'sources':[{'episode':'a'*64,'revision':1,'event_digest':'b'*64}],
            'valid_until':200,'negative_contexts':[{'consumer':'unsupported'}]}


def test_procedure_retrieval_and_motifs():
    p=procedure();current=lambda sources:True
    assert retrieve([p],'parser',{'schema':2},100,current)
    for query,context,now,checker in [('banana',{'schema':2},100,current),('parser',{'schema':1},100,current),('parser',{'schema':2},201,current),('parser',{'schema':2,'consumer':'unsupported'},100,current),('parser',{'schema':2},100,lambda s:False)]:
        assert retrieve([p],query,context,now,checker)==[]
    assert motif(p['actions'])==motif([{'action':'inspect','arg':'$renamed'}])
    assert motif(p['actions'])!=motif([{'action':'delete','arg':'$renamed'}])
    assert pareto([{'success':1,'cost':1,'complexity':1,'coverage':1},{'success':None}])==[{'success':1,'cost':1,'complexity':1,'coverage':1}]


def test_policy_candidate_scope_and_explicit_activation(tmp_path):
    root=tmp_path/'project';root.mkdir();c=AdaptationController(tmp_path/'home');name='sips-artifacts/policy/diagnosis.json'
    spec={'kind':'artifact','path':name,'text':json.dumps(policy())}
    r=c.write('observe',{'workspace':str(root),'task':'policy trial','allowed_files':[name],'suite':{g:[spec] for g in ['original','regression','counterexamples']},'expected_revision':0,'idempotency_key':'p'})
    r=step(c,r,'propose',intervention='create_tool',rationale='compare diagnosis weights');r=step(c,r,'build')
    target=Path(r['candidate_path'])/name;target.parent.mkdir(parents=True);target.write_text(json.dumps(policy()))
    r=step(c,r,'artifact',kind='policy',path=name)
    r=step(c,r,'policy_trial',alternatives=[{'id':'probe','features':{'discrimination':1,'cost':0,'reversibility':1}}])
    assert r['policy_trial']['effectiveness']=='unknown'
    r=step(c,r,'evaluate');assert r['state']=='ready_for_review'
    assert not (root/name).exists()
    assert c.read(r['episode'],'lineage')['lineage']
    with pytest.raises(ValueError): step(c,r,'activate',approved_candidate='wrong')
    r=step(c,r,'activate',approved_candidate=r['candidate_digest']);assert (root/name).exists()
    r=step(c,r,'rollback',approved_candidate=r['candidate_digest']);assert not (root/name).exists()


def test_transfer_adapter_preserves_all_memory_arms(tmp_path):
    fixture=tmp_path/'fixture';fixture.mkdir()
    (fixture/'consumer.py').write_text('import sys\nprint("right" if sys.argv[-1]=="procedure" else "wrong")\n')
    case={'kind':'transfer','task_family':'parser','split':'held_out','instance_digest':'fixture-only',
          'check':{'kind':'command','argv':['{python}','{fixtures}/consumer.py'],'stdout':'right\n'}}
    result=check(case,tmp_path,fixture,10)
    assert result['status']=='passed' and result['effectiveness']=='paired_task_improvement'
    assert set(result['arms'])=={'none','episodic','procedure'}
    assert result['arms']['none']['status']=='failed'
    case['split']='development';assert check(case,tmp_path,fixture,10)['status']=='unavailable'


def test_suite_revisions_preserve_earlier_receipts(tmp_path):
    c,r,_,_=setup_episode(tmp_path);r=build(c,r);r=step(c,r,'evaluate')
    before=c.directory(r['episode'])/r['receipt'];raw=before.read_bytes()
    r=step(c,r,'cancel')
    assert before.read_bytes()==raw


def test_contract_v2_undeclared_writes_and_declared_dependency_drift(tmp_path):
    from tool_contracts import validate
    script=tmp_path/'helper.py'
    script.write_text('import sys\nfrom pathlib import Path\nif "--help" not in sys.argv:\n Path("output").write_text("hello")\n print("ok")\n')
    contract={**tool(outputs={'result':scalar()}),'description':'write output','failure_semantics':'nonzero','cases':[{'id':'write','args':[],'stdout':'ok\n'}]}
    path=script.with_suffix('.contract.json');path.write_text(json.dumps(contract))
    result=validate(script);assert not result['ready_for_promote']
    assert result['cases'][0]['undeclared_writes']==['output']
    contract['effects']['writes']=['output'];path.write_text(json.dumps(contract))
    assert validate(script)['ready_for_promote']
    contract['resources']=['dependency'];contract['dependencies']=['dependency'];path.write_text(json.dumps(contract))
    assert not validate(script)['ready_for_promote']


def test_optional_schema_constraints_cannot_be_fabricated():
    assert not compatible({'type':'object'}, {'type':'object','properties':{'n':scalar('integer')}})
    with pytest.raises(ValueError):schema({'type':'object','properties':{'x':scalar()},'required':'x'})


def test_runtime_output_schema_enforcement(tmp_path):
    from tool_contracts import validate
    script=tmp_path/'lying.py';script.write_text('print("not an integer")\n')
    contract={**tool(),'description':'bad output type','failure_semantics':'nonzero','cases':[{'id':'wrong','args':[],'stdout':'not an integer\n'}]}
    script.with_suffix('.contract.json').write_text(json.dumps(contract))
    result=validate(script)
    assert not result['ready_for_promote'] and not result['cases'][0]['output_schema_valid']
