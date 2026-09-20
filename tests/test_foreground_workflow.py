import copy
import json
from pathlib import Path
import pytest
from sips_runtime.adaptation import AdaptationController
from sips_runtime.events import RevisionConflict
from sips_runtime.evaluation import check
from sips_runtime.workflow import comparison
from test_adaptive_core import setup_episode,step,build


def advance(c,r,output=None):
    packet=c.read(r['episode'],'next')['next']
    return c.write('advance',{'episode':r['episode'],'expected_revision':r['revision'],'idempotency_key':'advance-'+str(r['revision']), 'packet_id':packet['packet_id'],'output':output or {}})


def author(): return {'agent':'test fixture','model_label':'none','summary':'fixture edit, not a model trial','evidence':['fixture:helper']}


def test_resumable_foreground_loop_and_review_boundary(tmp_path):
    c,r,root,_=setup_episode(tmp_path)
    before=c.read(r['episode'],'events')
    packet=c.read(r['episode'],'next')['next']
    assert packet['kind']=='investigate' and c.read(r['episode'],'events')==before
    r=advance(c,r,{'hypotheses':[{'id':'impl','claim':'bad implementation'}],'probes':[]})
    c=AdaptationController(c.home) # fresh controller resumes from events
    assert c.read(r['episode'],'next')['next']['kind']=='choose_intervention'
    r=advance(c,r,{'intervention':'repair_implementation','rationale':'observed wrong stdout'})
    r=advance(c,r)
    (Path(r['candidate_path'])/'helper.py').write_text('print("right")\n')
    r=advance(c,r,{'authorship':author()})
    assert r['state']=='ready_for_review' and r['authorship'][0]['actual_tokens'] is None
    assert c.read(r['episode'],'next')['next']['kind']=='review'
    with pytest.raises(ValueError,match='review'): advance(c,r)
    assert (root/'helper.py').read_text()=='print("wrong")\n'


def test_packet_tampering_duplicate_and_stale(tmp_path):
    c,r,_,_=setup_episode(tmp_path);p=c.read(r['episode'],'next')['next']
    req={'episode':r['episode'],'expected_revision':r['revision'],'idempotency_key':'a','packet_id':p['packet_id'],'output':{'hypotheses':[{'id':'x','claim':'x'}],'probes':[]}}
    with pytest.raises(ValueError): c.write('advance',{**req,'packet_id':'tampered'})
    with pytest.raises(ValueError): c.write('advance',{**req,'output':{**req['output'],'action':'activate'}})
    result=c.write('advance',req)
    assert c.write('advance',req)==result
    with pytest.raises(RevisionConflict): c.write('advance',{**req,'idempotency_key':'other'})


def test_missing_authorship_and_exhausted_packet(tmp_path):
    c,r,_,_=setup_episode(tmp_path);r=build(c,r)
    with pytest.raises(ValueError): advance(c,r,{'authorship':{}})
    from sips_runtime.workflow import next_packet
    exhausted={**r,'evaluation_seconds':r['limits']['evaluation_seconds']}
    assert next_packet(exhausted,r['episode'],r['revision'])['action'] is None


def challenge():
    return {'kind':'evaluator_challenge','control':{'helper.py':'import sys\nprint(int(sys.argv[1])*2)\n'},
            'mutants':[{'id':'constant','files':{'helper.py':'print(4)\n'}}],
            'checks':[{'kind':'command','argv':['{python}','helper.py','2'],'stdout':'4\n'},
                      {'kind':'command','argv':['{python}','helper.py','3'],'stdout':'6\n'}]}


def test_oracle_kills_behavioral_mutant_and_preserves_workspace(tmp_path):
    (tmp_path/'helper.py').write_text('original')
    r=check(challenge(),tmp_path,tmp_path,10)
    assert r['status']=='passed' and not r['surviving_mutants'] and r['checks_run']==4
    assert (tmp_path/'helper.py').read_text()=='original'


def test_weak_oracle_and_broken_control_fail_closed(tmp_path):
    spec=challenge();spec['checks']=spec['checks'][:1]
    r=check(spec,tmp_path,tmp_path,10)
    assert r['status']=='failed' and r['surviving_mutants']==['constant']
    spec=challenge();spec['control']['helper.py']='raise RuntimeError("broken dependency")'
    assert check(spec,tmp_path,tmp_path,10)['status']=='unavailable'


@pytest.mark.parametrize('change', ['crash','escape','recursive','identical','empty'])
def test_invalid_challenges_never_pass(tmp_path,change):
    spec=challenge()
    if change=='crash': spec['mutants'][0]['files']['helper.py']='raise RuntimeError()'
    if change=='escape': spec['control']={'../escape':'bad'}
    if change=='recursive': spec['checks']=[challenge()]
    if change=='identical': spec['mutants'][0]['files']=copy.deepcopy(spec['control'])
    if change=='empty': spec['mutants']=[]
    assert check(spec,tmp_path,tmp_path,10)['status']=='unavailable'


def test_later_use_requires_executed_authored_receipts(tmp_path):
    c,r,_,_=setup_episode(tmp_path);r=build(c,r);r=advance(c,r,{'authorship':author()})
    other=tmp_path/'other';other.mkdir()
    c2,target,_,_=setup_episode(other)
    # Both episodes must live in the same durable store, but task workspaces can differ.
    import shutil
    shutil.copytree(c2.directory(target['episode']),c.directory(target['episode']))
    target=build(c,target);target=advance(c,target,{'authorship':author()})
    r=step(c,r,'link_outcome',source_candidate=r['candidate_digest'],target_episode=target['episode'],memory_mode='procedure',task_identity='task-1')
    report=c.read(r['episode'],'outcomes')['outcomes']
    assert report['episodes']==1 and report['effectiveness']=='unmeasured'
    with pytest.raises(ValueError,match='duplicate'): step(c,r,'link_outcome',source_candidate=r['candidate_digest'],target_episode=target['episode'],memory_mode='none',task_identity='task-2')


def test_comparison_reports_negative_transfer_and_unknown():
    def row(mode,status): return {'task_identity':'x','memory_mode':mode,'candidate_status':status,'evaluation_seconds':1}
    r=comparison([row('none','passed'),row('episodic','failed'),row('procedure','failed')])
    assert r['observed_negative_transfer']==1 and r['observed_procedure_gains']==0
    r=comparison([row('none','unavailable'),row('episodic','failed'),row('procedure','passed')])
    assert r['unavailable_groups']==1 and r['observed_procedure_gains']==0


def test_receipt_mutation_is_not_valid_later_evidence(tmp_path):
    c,r,_,_=setup_episode(tmp_path);r=build(c,r);r=advance(c,r,{'authorship':author()})
    path=c.directory(r['episode'])/r['receipt'];receipt=json.loads(path.read_text());receipt['reports']['candidate']['status']='failed';path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='receipt drift'): c.read(r['episode'],'receipt')


def test_challenge_in_pinned_evaluator_and_recovery_packet(tmp_path):
    c,r,root,request=setup_episode(tmp_path)
    request={**request,'idempotency_key':'challenge-suite','suite':{k:[challenge()] for k in ('original','regression','counterexamples')}}
    r=c.write('observe',request);r=build(c,r);r=advance(c,r,{'authorship':author()})
    assert r['state']=='ready_for_review'
    from sips_runtime.workflow import next_packet
    assert next_packet({**r,'state':'evaluating'},r['episode'],r['revision'])['action']=='recover'


def test_cli_and_mcp_packet_parity(tmp_path,monkeypatch):
    c,r,_,_=setup_episode(tmp_path);monkeypatch.setenv('SIPS_HOME',str(c.home))
    from harness_homebase_mcp import handle_request
    req={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'homebase_adaptation_read','arguments':{'episode':r['episode'],'view':'next'}}}
    response=handle_request(req)
    assert response['result']['structuredContent']['next']==c.read(r['episode'],'next')['next']
    import os,subprocess,sys
    script=Path(__file__).resolve().parents[1]/'scripts/adaptation.py'
    result=subprocess.run([sys.executable,str(script),'show','--episode',r['episode'],'--view','next'],env=os.environ,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['next']==c.read(r['episode'],'next')['next']


def test_evidence_intervention_does_not_fabricate_candidate(tmp_path):
    c,r,_,_=setup_episode(tmp_path)
    r=step(c,r,'propose',intervention='gather_evidence',rationale='need observations')
    assert c.read(r['episode'],'next')['next']['kind']=='investigate'
    r=advance(c,r,{'hypotheses':[{'id':'x','claim':'x'}],'probes':[]})
    assert r['state']=='diagnosing' and not (c.directory(r['episode'])/'candidate').exists()


def test_unknown_prediction_neither_supports_nor_contradicts(monkeypatch,tmp_path):
    from sips_runtime import investigation as inv
    monkeypatch.setattr(inv,'check',lambda *a,**k:{'status':'failed','checks_run':1})
    probe={'id':'p','check':{},'predictions':{'impl':'failed','environment':'unavailable','other':'passed'}}
    result=inv.execute(probe,tmp_path,tmp_path,1,1,{})
    assert result['supports']==['impl'] and result['contradicts']==['other']


def test_concurrent_duplicate_advance_executes_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    c,r,_,_=setup_episode(tmp_path);p=c.read(r['episode'],'next')['next']
    req={'episode':r['episode'],'expected_revision':r['revision'],'idempotency_key':'concurrent','packet_id':p['packet_id'],'output':{'hypotheses':[{'id':'x','claim':'x'}],'probes':[]}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:c.write('advance',req),range(2)))
    assert results[0]==results[1]
    assert len(c.read(r['episode'],'events')['events'])==2


def test_unknown_next_read_never_creates_store(tmp_path):
    c=AdaptationController(tmp_path/'absent')
    with pytest.raises(ValueError): c.read('a'*64,'next')
    assert not c.home.exists()


def test_complete_diagnostic_outcome_stops_packet_loop(tmp_path):
    c,r,_,_=setup_episode(tmp_path)
    r=step(c,r,'conclude',outcome='insufficient_evidence',rationale='No discriminating observation available')
    assert c.read(r['episode'],'next')['next']['kind']=='stopped'
    with pytest.raises(ValueError,match='stopped'): advance(c,r)
