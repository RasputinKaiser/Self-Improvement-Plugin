import json
from pathlib import Path
import sys
import pytest
from sips_runtime.adaptation import AdaptationController, manifest
from sips_runtime.events import RevisionConflict, IdempotencyConflict
from sips_runtime.evaluation import evaluate


def setup_episode(tmp_path):
    root = tmp_path / 'project'; root.mkdir()
    (root / 'helper.py').write_text('print("wrong")\n')
    (root / 'untouched').write_text('keep')
    controller = AdaptationController(tmp_path / 'home')
    case = {'kind': 'command', 'argv': ['{python}', 'helper.py'], 'stdout': 'right\n'}
    request = {'workspace': str(root), 'task': 'Produce right output', 'allowed_files': ['helper.py'],
               'context_files': ['untouched'], 'suite': {'original': [case], 'regression': [case], 'counterexamples': [case]},
               'expected_revision': 0, 'idempotency_key': 'initial'}
    result = controller.write('observe', request)
    return controller, result, root, request


def step(controller, result, action, **kwargs):
    return controller.write(action, {'episode': result['episode'], 'expected_revision': result['revision'],
                                      'idempotency_key': action + str(result['revision']), **kwargs})


def build(controller, result):
    result = step(controller, result, 'propose', intervention='repair_implementation', rationale='Observed wrong stdout')
    result = step(controller, result, 'build')
    (Path(result['candidate_path']) / 'helper.py').write_text('print("right")\n')
    return result


def test_end_to_end_review_activation_rollback(tmp_path):
    c, r, root, _ = setup_episode(tmp_path)
    r = build(c, r); r = step(c, r, 'evaluate')
    assert r['state'] == 'ready_for_review', r
    assert r['effectiveness'] == 'paired_improvement'
    assert (root / 'helper.py').read_text() == 'print("wrong")\n'
    assert '+print("right")' in c.read(r['episode'], 'diff')['diff']
    with pytest.raises(ValueError, match='approval'): step(c, r, 'activate')
    r = step(c, r, 'activate', approved_candidate=r['candidate_digest'])
    assert r['state'] == 'activated'
    assert (root / 'helper.py').read_text() == 'print("right")\n'
    r = step(c, r, 'rollback', approved_candidate=r['candidate_digest'])
    assert r['state'] == 'canceled'
    assert (root / 'helper.py').read_text() == 'print("wrong")\n'
    assert (root / 'untouched').read_text() == 'keep'


def test_reads_do_not_create_state(tmp_path):
    c = AdaptationController(tmp_path / 'absent')
    with pytest.raises(ValueError, match='unknown'): c.read('a' * 64)
    assert not c.home.exists()


def test_revision_and_idempotency(tmp_path):
    c, r, root, request = setup_episode(tmp_path)
    assert c.write('observe', request)['revision'] == r['revision']
    with pytest.raises(IdempotencyConflict): c.write('observe', {**request, 'task': 'changed'})
    with pytest.raises(RevisionConflict):
        c.write('diagnose', {'episode': r['episode'], 'expected_revision': 0, 'idempotency_key': 'stale'})


@pytest.mark.parametrize('target', ['suite.json', 'baseline/helper.py', 'fixtures/new', 'evaluator/worker.py'])
def test_frozen_inputs(tmp_path, target):
    c, r, _, _ = setup_episode(tmp_path); r = build(c, r)
    path = c.directory(r['episode']) / target
    path.write_text('{}')
    with pytest.raises(ValueError, match='drift'): step(c, r, 'evaluate')


def test_scope_and_recovery(tmp_path):
    c, r, _, _ = setup_episode(tmp_path); r = build(c, r)
    (Path(r['candidate_path']) / 'untouched').write_text('altered')
    with pytest.raises(ValueError, match='scope'): step(c, r, 'evaluate')
    r = step(c, r, 'recover'); assert r['state'] == 'unavailable'
    assert Path(r['candidate_path']).exists()


def test_workspace_conflict_prevents_activation(tmp_path):
    c, r, root, _ = setup_episode(tmp_path); r = step(c, build(c, r), 'evaluate')
    (root / 'helper.py').write_text('user changed')
    with pytest.raises(ValueError, match='conflict'): step(c, r, 'activate', approved_candidate=r['candidate_digest'])
    assert (root / 'helper.py').read_text() == 'user changed'


def test_empty_missing_unsupported_checks(tmp_path):
    for suite in ({}, {'original': [{'kind': 'unknown'}], 'regression': [], 'counterexamples': []}):
        assert evaluate(suite, tmp_path, tmp_path)['status'] == 'unavailable'


def test_diagnostic_proposal_needs_no_artifact(tmp_path):
    c, r, _, _ = setup_episode(tmp_path)
    r = step(c, r, 'propose', intervention='gather_evidence', rationale='Need trace')
    assert r['state'] == 'proposed' and 'candidate_path' not in r


def test_pytest_zero_collection_unavailable(tmp_path):
    suite = {g: [{'kind': 'pytest', 'argv': [str(tmp_path)]}] for g in ('original','regression','counterexamples')}
    assert evaluate(suite, tmp_path, tmp_path)['status'] == 'unavailable'


def test_legacy_episode_read_only(tmp_path):
    from sips_runtime.events import EventStore
    c = AdaptationController(tmp_path)
    ident = 'b' * 64
    EventStore(c.directory(ident)).append('legacy', ident, {'stage': 'accepted'})
    assert c.read(ident)['historical_status'] == 'accepted'
    with pytest.raises(ValueError, match='read-only'):
        c.write('activate', {'episode': ident, 'expected_revision': 1, 'idempotency_key': 'x', 'approved_candidate':'anything'})


def test_concurrent_writes_one_revision_wins(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    c, r, _, _ = setup_episode(tmp_path)
    def write(i):
        try:
            return c.write('diagnose', {'episode':r['episode'],'expected_revision':r['revision'],
                                       'idempotency_key':str(i),'hypotheses':['inspect']})['state']
        except RevisionConflict: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(write,[1,2]))
    assert sorted(results)==['conflict','diagnosing']


def test_budget_exhaustion_is_reviewable(tmp_path):
    c,r,_,_=setup_episode(tmp_path)
    for _ in range(2):
        r=build(c,r);r=step(c,r,'recover')
    r=step(c,r,'propose',intervention='repair_implementation',rationale='retry')
    r=step(c,r,'build')
    assert r['state']=='unavailable' and 'budget' in r['reason']


def test_memory_relevance_and_unknown_outcomes(tmp_path,monkeypatch):
    from memory_fabric_semantic_match import match_score
    from agent_patterns import classify_outcomes,extract_approach_metrics
    from recall_ranker import rank
    assert match_score({}, {'direct_terms':['quantum'],'expanded_terms':[]}, [('orchard',10)])==0
    unknown={'tags':['outcome','acceptance-unknown']}
    assert classify_outcomes([unknown])['success_rate'] is None
    assert extract_approach_metrics([unknown])==[]
    records=[{'id':'old','created_at':'2020-01-01T00:00:00Z'},
             {'id':'new','created_at':'2026-09-19T00:00:00Z'},
             {'id':'expired','valid_until':'2020-01-01T00:00:00Z'}]
    assert [r['id'] for r in rank(records)]==['new','old']


def test_no_retired_host_execution():
    root=Path(__file__).resolve().parents[1]
    forbidden=['find_ncode','/bin/ncode','which("ncode")','bypassPermissions']
    for path in (root/'scripts').rglob('*.py'):
        if path.name=='run_tests.py': continue # Historical fixtures, not executable host backends.
        text=path.read_text()
        assert not any(token in text for token in forbidden),path
    assert '.ncode' not in (root/'install.sh').read_text()


def test_adapter_failure_timeout_and_dependency_unavailable(tmp_path):
    from sips_runtime.evaluation import check
    assert check({'kind':'command','argv':['missing-sips-test-executable'],'stdout':''},tmp_path,tmp_path,1)['status']=='unavailable'
    result=check({'kind':'command','argv':[sys.executable,'-c','import time;time.sleep(1)'],'stdout':''},tmp_path,tmp_path,.01)
    assert result['status']=='unavailable'
    result=check({'kind':'command','argv':[sys.executable,'-c','print("wrong")'],'stdout':'right\n'},tmp_path,tmp_path,1)
    assert result['status']=='failed' and result['checks_run']==1


def test_evaluation_interruption_recovery_budget(tmp_path):
    from sips_runtime.events import EventStore
    import time
    c,r,_,_=setup_episode(tmp_path);r=build(c,r)
    state={k:v for k,v in r.items() if k not in {'revision','episode'}}
    state.update(state='evaluating',evaluation_started_at=time.time()-5)
    EventStore(c.directory(r['episode'])).append('interrupted',r['episode'],{'state':state})
    r=c.read(r['episode']);r=step(c,r,'recover')
    assert r['state']=='unavailable' and r['evaluation_seconds']>=5


def test_interrupted_activation_restores_baseline(tmp_path,monkeypatch):
    c,r,root,_=setup_episode(tmp_path);r=step(c,build(c,r),'evaluate')
    from sips_runtime.events import atomic_write_json
    directory=c.directory(r['episode'])
    atomic_write_json(directory/'activation-journal.json',{'rollback':False,'files':['helper.py']})
    (root/'helper.py').write_text('print("right")\n')
    r=step(c,r,'recover')
    assert r['state']=='unavailable'
    assert (root/'helper.py').read_text()=='print("wrong")\n'


def test_empty_assertions_and_malformed_checks_are_unavailable(tmp_path):
    from sips_runtime.evaluation import check
    for spec in [{'kind': 'command', 'argv': [sys.executable, '-c', 'pass'], 'files': {}}, None]:
        result = check(spec, tmp_path, tmp_path, 5)
        assert result['status'] == 'unavailable'
        assert result['checks_run'] == 0


def test_stop_needs_no_artifact(tmp_path):
    c,r,root,_ = setup_episode(tmp_path)
    r = step(c,r,'propose',intervention='stop',rationale='No supported improvement')
    assert r['state'] == 'canceled'
    assert not (c.directory(r['episode']) / 'candidate').exists()
