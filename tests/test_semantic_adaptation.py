"""Semantic compatibility, validity propagation, and executable diagnostic graphs."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from sips_runtime.hypergraph import compatible, accepts, schema, compose
from sips_runtime.policy_graph import validate, run
from sips_runtime.procedures import validate_policy
from sips_runtime.adaptation import AdaptationController
from test_adaptive_core import setup_episode, step, build
from test_transferable_core import tool, hypotheses, probes


def number(**constraints):
    return {'type':'number','semantic':constraints}


@pytest.mark.parametrize('constraint',[{'unit':'seconds'},{'role':'duration'},{'context':{'workspace':'abc'}},{'minimum':0},{'maximum':10}])
def test_semantic_requirements_cannot_be_invented(constraint):
    assert not compatible(number(),number(**constraint))
    assert compatible(number(**constraint),number(**constraint))
    assert compatible(number(**constraint),number())


def test_semantic_narrowing_runtime_and_nested_types():
    assert compatible(number(minimum=1,maximum=9),number(minimum=0,maximum=10))
    assert not compatible(number(minimum=0,maximum=11),number(minimum=0,maximum=10))
    assert not compatible(number(unit='seconds'),number(unit='milliseconds'))
    assert accepts(number(minimum=0,maximum=10),4)
    assert not accepts(number(minimum=0,maximum=10),11)
    assert not compatible({'type':'array','items':number(unit='seconds')},{'type':'array','items':number(unit='milliseconds')})
    assert not compatible({'type':'integer','enum':[1]},{'type':'integer','enum':[True]})


@pytest.mark.parametrize('bad',[{'minimum':float('nan')},{'minimum':10,'maximum':1},{'unit':''},{'context':{'a':1}},{'predicate':'execute'}])
def test_unsupported_semantic_constraints(bad):
    with pytest.raises(ValueError): schema(number(**bad))


def test_v3_planning_preserves_semantic_binding():
    t=tool(inputs={'seconds':number(unit='seconds')},outputs={'milliseconds':number(unit='milliseconds')})
    t['schema']='sips.tool-contract.v3'
    good=compose([t],{'duration':number(unit='seconds')},{'result':number(unit='milliseconds')},prerequisites=['local'])
    assert good['status']=='proposed' and good['steps'][0]['bindings']=={'seconds':'duration'}
    assert compose([t],{'duration':number(unit='bytes')},{'result':number(unit='milliseconds')},prerequisites=['local'])['status']=='insufficient_fit'


def policy():
    return {'schema':'sips.policy.v2','kind':'diagnosis','scope':'diagnosis','version':'1',
            'inputs':['probe_outcomes'],'outputs':['intervention'],'entry':'check','assumptions':[],
            'nodes':{'check':{'probe':'replay','on':{'passed':'done','failed':'repair','unavailable':'evidence'}},
                     'done':{'intervention':'stop','rationale':'No reproduced failure'},
                     'repair':{'intervention':'repair_interface','rationale':'Failure reproduced'},
                     'evidence':{'intervention':'gather_evidence','rationale':'Environment unknown'}}}


@pytest.mark.parametrize('outcome,decision',[('passed','stop'),('failed','repair_interface'),('unavailable','gather_evidence')])
def test_branch_outcomes_are_distinct(tmp_path,outcome,decision):
    r=run(policy(),{'replay':outcome},tmp_path,0)
    assert r['decision']['intervention']==decision and r['activation']=='none'
    assert r['effectiveness']=='unknown'
    assert run(policy(),{},tmp_path,0)['status']=='needs_evidence'
    assert validate_policy(policy())==policy()


@pytest.mark.parametrize('mutation',['cycle','unreachable','missing','command','activation','scope'])
def test_graph_rejects_invalid_or_privileged_programs(mutation):
    p=policy()
    if mutation=='cycle': p['nodes']['check']['on']['failed']='check'
    if mutation=='unreachable': p['nodes']['extra']={'intervention':'stop','rationale':'unused'}
    if mutation=='missing': del p['nodes']['check']['on']['unavailable']
    if mutation in {'command','activation'}: p['nodes']['repair']={mutation:'do it'}
    if mutation=='scope': p['scope']='activation'
    with pytest.raises(ValueError): validate(p)


def test_expiring_assumptions_and_symlinks(tmp_path):
    f=tmp_path/'environment';f.write_text('v1');p=policy()
    p['assumptions']=[{'path':'environment','sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'valid_until':10}]
    assert run(p,{},tmp_path,9)['status']=='needs_evidence'
    assert run(p,{},tmp_path,10)['invalid_assumptions'][0]['reason']=='expired'
    f.write_text('v2');assert run(p,{},tmp_path,0)['status']=='inapplicable'
    f.unlink();f.symlink_to(tmp_path/'target');(tmp_path/'target').write_text('v1')
    assert run(p,{},tmp_path,0)['status']=='inapplicable'


@pytest.mark.parametrize('target',['baseline/helper.py','fixtures/extra','evaluator/extra','candidate/helper.py','suite.json','workspace/helper.py'])
def test_dependency_graph_drift_propagates_without_writing(tmp_path,target):
    c,r,root,_=setup_episode(tmp_path);r=step(c,build(c,r),'evaluate');d=c.directory(r['episode'])
    g=c.read(r['episode'],'dependencies')['dependencies'];assert not g['affected']
    path=root/'helper.py' if target.startswith('workspace') else d/target
    path.write_text('{}')
    before={str(p):p.stat().st_mtime_ns for p in d.rglob('*') if p.is_file()}
    g=c.read(r['episode'],'dependencies')['dependencies']
    assert 'receipt' in g['affected'] and g['reasons']['receipt']
    assert {str(p):p.stat().st_mtime_ns for p in d.rglob('*') if p.is_file()}==before
    assert c.read(r['episode'])['state']=='ready_for_review'
    assert g['activation']=='none'


def test_unknown_graph_read_has_no_side_effect(tmp_path):
    c=AdaptationController(tmp_path/'absent')
    with pytest.raises(ValueError): c.read('a'*64,'dependencies')
    assert not c.home.exists()


def test_controller_branch_trial_uses_durable_probe_not_caller_claim(tmp_path):
    c,target,root,_=setup_episode(tmp_path)
    target=step(c,target,'investigate',hypotheses=hypotheses(),probes=probes())
    target=step(c,target,'probe',probe='replay')
    name='sips-artifacts/policy/diagnosis.json';spec={'kind':'artifact','path':name,'text':json.dumps(policy())}
    r=c.write('observe',{'workspace':str(root),'task':'branch policy trial','allowed_files':[name],
                        'suite':{g:[spec] for g in ['original','regression','counterexamples']},'expected_revision':0,'idempotency_key':'branch'})
    r=step(c,r,'propose',intervention='create_tool',rationale='diagnostic branches');r=step(c,r,'build')
    f=Path(r['candidate_path'])/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(policy()))
    r=step(c,r,'artifact',kind='policy',path=name)
    r=step(c,r,'policy_trial',target_episode=target['episode'],outcomes={'replay':'passed'})
    assert r['policy_trial']['decision']['intervention']=='repair_interface'
    assert r['policy_trial']['target']['revision']==target['revision']
    assert r['state']=='building' and not (root/name).exists()
    (root/'helper.py').write_text('changed source')
    r=step(c,r,'policy_trial',target_episode=target['episode'])
    assert r['policy_trial']['status']=='inapplicable' and 'workspace:helper.py' in r['policy_trial']['stale_evidence']
    f.write_text(json.dumps({**policy(),'version':'tampered'}))
    with pytest.raises(ValueError,match='artifact changed'): step(c,r,'policy_trial',target_episode=target['episode'])


def test_frozen_branch_evaluator_rejects_wrong_empty_and_missing(tmp_path):
    from sips_runtime.evaluation import check
    (tmp_path/'policy.json').write_text(json.dumps(policy()))
    cases=[{'outcomes':{'replay':'failed'},'now':0,'expected':{'status':'proposed','intervention':'repair_interface'}},
           {'outcomes':{},'now':0,'expected':{'status':'needs_evidence','probe':'replay'}}]
    spec={'kind':'policy_cases','path':'policy.json','cases':cases}
    assert check(spec,tmp_path,tmp_path,1)['checks_run']==2
    assert check(spec,tmp_path,tmp_path,1)['status']=='passed'
    wrong=copy.deepcopy(spec);wrong['cases'][0]['expected']['intervention']='stop'
    assert check(wrong,tmp_path,tmp_path,1)['status']=='failed'
    assert check({**spec,'cases':[]},tmp_path,tmp_path,1)['status']=='unavailable'
    assert check({**spec,'path':'missing'},tmp_path,tmp_path,1)['status']=='unavailable'


def test_policy_cases_evaluate_from_frozen_engine(tmp_path):
    root=tmp_path/'project';root.mkdir();c=AdaptationController(tmp_path/'home');name='sips-artifacts/policy/diagnosis.json'
    initial=root/name;initial.parent.mkdir(parents=True);bad=policy();bad['nodes']['repair']['intervention']='stop';initial.write_text(json.dumps(bad))
    spec={'kind':'policy_cases','path':name,'cases':[{'outcomes':{'replay':'failed'},'now':0,'expected':{'status':'proposed','intervention':'repair_interface'}}]}
    r=c.write('observe',{'workspace':str(root),'task':'executable branch','allowed_files':[name],
                        'suite':{g:[spec] for g in ['original','regression','counterexamples']},'expected_revision':0,'idempotency_key':'branch'})
    r=step(c,r,'propose',intervention='create_tool',rationale='bounded branching');r=step(c,r,'build')
    f=Path(r['candidate_path'])/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(policy()))
    r=step(c,r,'artifact',kind='policy',path=name);r=step(c,r,'evaluate')
    assert r['state']=='ready_for_review' and json.loads((root/name).read_text())==bad
