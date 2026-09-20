import copy
from sips_runtime.procedures import retrieval_audit,retrieve
from sips_runtime.visuals import episode_view
from test_adaptive_core import setup_episode,build,step


def procedure():
    return {'schema':'sips.procedure.v1','version':'1','task':'parse payload','applicability':{'version':'2'},
            'actions':[{'action':'inspect'}],'bindings':{},'expected_evidence':['receipt'],'failure_modes':[],
            'sources':[{'episode':'source','revision':1,'event_digest':'digest'}],'valid_until':20,'negative_contexts':[]}


def test_audit_reasons_and_legacy_projection():
    p=procedure();a=retrieval_audit([p],'parse',{'version':'2'},10,lambda _:True)
    assert len(a['eligible'])==1 and not a['rejected']
    assert retrieve([p],'parse',{'version':'2'},10,lambda _:True)==a['eligible']
    bad=copy.deepcopy(p);bad['valid_until']=0;bad['negative_contexts']=[{'version':'3'}]
    a=retrieval_audit([bad],'unrelated',{'version':'3'},10,lambda _:False)
    assert not a['eligible']
    assert set(a['rejected'][0]['reasons'])=={'expired','source_changed_or_unavailable','applicability_mismatch','known_negative_context','unrelated'}
    assert a['rejected'][0]['score']==0


def test_diagram_has_no_user_controlled_node_identifiers():
    s={'state':'ready_for_review','evidence':[], 'effectiveness':'x"] --> BAD["<script>'}
    v=episode_view(s,'id',3,{'affected':['a']},[])
    assert '<script>' not in v['mermaid'] and '&lt;script&gt;' in v['mermaid']
    assert 'x"]' not in v['mermaid']
    assert v['summary']['affected_dependency_nodes']==1


def test_visual_read_tracks_drift_without_events(tmp_path):
    c,r,root,_=setup_episode(tmp_path);r=step(c,build(c,r),'evaluate')
    count=len(c.history(r['episode']));v=c.read(r['episode'],'visual')['visual']
    assert v['summary']['state']=='ready_for_review' and v['summary']['affected_dependency_nodes']==0
    (root/'helper.py').write_text('changed')
    assert c.read(r['episode'],'visual')['visual']['summary']['affected_dependency_nodes']>0
    assert len(c.history(r['episode']))==count


def test_controller_explains_rejected_procedure_artifact(tmp_path):
    import json,time
    from pathlib import Path
    c,source,root,_=setup_episode(tmp_path);event=c.history(source['episode'])[-1]
    value=procedure();value['sources']=[{'episode':source['episode'],'revision':source['revision'],'event_digest':event.event_digest}];value['valid_until']=time.time()+3600
    name='sips-artifacts/procedure/parse.json';check={'kind':'artifact','path':name,'exists':True}
    r=c.write('observe',{'workspace':str(root),'task':'parse','allowed_files':[name],'suite':{g:[check] for g in ['original','regression','counterexamples']},'expected_revision':0,'idempotency_key':'procedure'})
    r=step(c,r,'propose',intervention='consolidate',rationale='retain workflow');r=step(c,r,'build')
    p=Path(r['candidate_path'])/name;p.parent.mkdir(parents=True);p.write_text(json.dumps(value));r=step(c,r,'artifact',kind='procedure',path=name)
    assert c.read(source['episode'],'procedures',query='parse',context={'version':'2'})['procedures']
    p.write_text('{}')
    result=c.read(source['episode'],'procedures',query='parse',context={'version':'2'})
    assert not result['procedures']
    assert result['retrieval_audit']['artifact_rejections'][0]['episode']==r['episode']


def test_dependency_diagram_is_bounded_and_prioritizes_drift():
    nodes=[{'id':f'file-{i:02}','status':'current'} for i in range(30)]
    nodes[-1]['status']='stale'
    deps={'nodes':nodes,'affected':['file-29'],'edges':[{'from':'file-00','to':'file-29'}]}
    v=episode_view({'state':'building'},'x',1,deps,[])
    assert v['dependency_nodes_omitted']==6 and 'file-29: stale' in v['dependency_mermaid']
    assert v['dependency_mermaid'].count('["')==24
