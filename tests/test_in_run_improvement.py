from pathlib import Path
import pytest
from sips_runtime.opportunities import capture,project
from test_adaptive_core import setup_episode,step


def request(**changes):
    return {'kind':'create_skill','path':'skills/example/SKILL.md','title':'Capture reproducible workflow',
            'rationale':'Repeated interface failure','evidence_indices':[0],
            'acceptance':['Original failure fixed','Consumer command passes','Wrong trigger excluded'],**changes}


def state(tmp_path):
    return {'workspace':str(tmp_path),'evidence':[{'command':'example','exit':1}]}


def test_notice_deduplicates_without_creating_target(tmp_path):
    s=state(tmp_path);capture(s,request());capture(s,request())
    assert len(s['opportunities'])==1 and not (tmp_path/'skills').exists()
    assert project(s)[0]['status']=='proposed'
    assert project(s)[0]['activation']=='none'
    assert project(s)[0]['observation_template']['allowed_files']==['skills/example/SKILL.md']


@pytest.mark.parametrize('change',[{'evidence_indices':[]},{'evidence_indices':[1]},{'evidence_indices':[True]},
    {'kind':'activate'},{'path':'../other'},{'path':'/tmp/other'},{'path':'skill.md'},{'acceptance':[]},
    {'kind':'refresh_skill'},{'title':''}])
def test_bad_notice_rejected(tmp_path,change):
    with pytest.raises(ValueError): capture(state(tmp_path),request(**change))


def test_existing_skill_refresh_and_drift(tmp_path):
    p=tmp_path/'skills/example/SKILL.md';p.parent.mkdir(parents=True);p.write_text('old')
    s=state(tmp_path)
    with pytest.raises(ValueError): capture(s,request())
    capture(s,request(kind='refresh_skill'));assert project(s)[0]['status']=='proposed'
    p.write_text('changed');assert project(s)[0]['status']=='stale'


def test_symlink_does_not_become_fresh(tmp_path):
    s=state(tmp_path);capture(s,request());target=tmp_path/'skills/example/SKILL.md';target.parent.mkdir(parents=True)
    other=tmp_path/'other';other.write_text('data');target.symlink_to(other)
    assert project(s)[0]['status']=='stale'
    with pytest.raises(ValueError): capture(s,request(kind='refresh_skill'))


def test_controller_notice_revision_and_read_purity(tmp_path):
    c,r,root,_=setup_episode(tmp_path)
    # Observation without explicit evidence cannot fabricate evidence references.
    r=step(c,r,'investigate',hypotheses=[{'id':'h','claim':'Wrong output'}],probes=[{'id':'p','check':{'kind':'command','argv':['{python}','helper.py'],'stdout':'right\n'},'cost_seconds':1,'reversible':True,'predictions':{'h':'failed'}}])
    r=step(c,r,'probe',probe='p')
    r=step(c,r,'notice',**request())
    assert r['state']=='diagnosing'
    d=c.directory(r['episode']);before={str(p):p.stat().st_mtime_ns for p in d.rglob('*') if p.is_file()}
    assert len(c.read(r['episode'],'opportunities')['opportunities'])==1
    assert before=={str(p):p.stat().st_mtime_ns for p in d.rglob('*') if p.is_file()}
    assert c.read(r['episode'],'next')['next']['improvement_notices']==1
    assert not (root/'skills').exists()


def test_directory_cannot_be_a_tool_target(tmp_path):
    (tmp_path/'scripts').mkdir()
    with pytest.raises(ValueError,match='file'): capture(state(tmp_path),request(kind='compose_tools',path='scripts'))
