import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import adaptation
import fix_drafter
import tool_contracts
from harness_homebase_mcp import tool_factory_payload
from sips_runtime.canonical import canonical_hash

ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / 'scripts/tool_factory.py'


def contract():
    return {'schema': 'sips.tool-contract.v1', 'status': 'implemented', 'version': '1',
            'description': 'Normalize receipt', 'inputs': ['raw'], 'outputs': ['normalized'],
            'preconditions': ['local'], 'effects': ['stdout only'], 'failure_semantics': 'nonzero on bad input',
            'cases': [{'id': 'normal', 'args': [], 'stdout': 'normalized\n'}]}


def helper(tmp_path, lang='py'):
    scripts = tmp_path / 'scripts'; scripts.mkdir(exist_ok=True)
    script = scripts / f'normalizer.{lang}'
    script.write_text('print("normalized")\n' if lang == 'py' else '#!/usr/bin/env bash\nprintf "normalized\\n"\n')
    script.with_suffix('.contract.json').write_text(json.dumps(contract()))
    return script


def cli(home, *args):
    return subprocess.run([sys.executable, str(FACTORY), *args], capture_output=True, text=True,
                          env={**os.environ, 'SIPS_HOME': str(home)}, timeout=30)


def test_comment_does_not_promote_scaffold(tmp_path):
    assert cli(tmp_path, 'scaffold', 'empty', '--summary', 'empty').returncode == 0
    (tmp_path / 'scripts/run_tests.py').write_text('# empty\n')
    result = cli(tmp_path, 'validate', 'empty')
    assert result.returncode == 1
    receipt = json.loads(result.stdout)
    assert receipt['ready_for_promote'] is False
    assert 'implemented' in receipt['errors'][0]


@pytest.mark.parametrize('lang', ['py', 'sh'])
def test_executes_language_and_exact_behavior(tmp_path, lang):
    script = helper(tmp_path, lang)
    result = tool_contracts.validate(script)
    assert result['ready_for_promote']
    data = contract(); data['cases'][0]['stdout'] = 'incorrect\n'
    script.with_suffix('.contract.json').write_text(json.dumps(data))
    result = tool_contracts.validate(script)
    assert not result['ready_for_promote']
    assert result['cases'][0]['exit'] == 0
    assert result['cases'][0]['passed'] is False


def test_no_empty_or_help_only_verification(tmp_path):
    script = helper(tmp_path)
    for cases in ([], [{'id': 'help', 'args': ['--help'], 'stdout': 'normalized\n'}]):
        data = contract(); data['cases'] = cases
        script.with_suffix('.contract.json').write_text(json.dumps(data))
        assert not tool_contracts.validate(script)['ready_for_promote']


def test_packaged_resource_and_pinned_version(tmp_path):
    script = helper(tmp_path)
    script.write_text('from pathlib import Path\nprint(Path(__file__).with_name("data.txt").read_text())\n')
    (script.parent / 'data.txt').write_text('normalized')
    data = contract(); data['resources'] = ['data.txt']
    script.with_suffix('.contract.json').write_text(json.dumps(data))
    result = cli(tmp_path, 'promote', script.stem)
    assert result.returncode == 0, result.stderr
    active = json.loads((tmp_path / 'skills/normalizer/active.json').read_text())
    entry = Path(active['entrypoint'])
    script.write_text('raise RuntimeError("edited original")\n')
    assert subprocess.check_output([sys.executable, str(entry)], text=True) == 'normalized\n'
    assert 'dispatch.py' in (tmp_path / 'skills/normalizer/SKILL.md').read_text()
    assert subprocess.check_output([sys.executable, str(tmp_path / 'skills/normalizer/dispatch.py')], text=True) == 'normalized\n'
    assert 'unverified' in active['discovery_status']


def test_fixture_case_isolation(tmp_path):
    script = helper(tmp_path)
    script.write_text('from pathlib import Path\nimport sys\nif "--help" not in sys.argv:\n p=Path("x"); print(p.exists()); p.write_text("x")\n')
    data = contract(); data['cases'] = [{'id': str(i), 'args': [], 'stdout': 'False\n'} for i in range(2)]
    script.with_suffix('.contract.json').write_text(json.dumps(data))
    assert tool_contracts.validate(script)['ready_for_promote']
    data['resources'] = ['../outside']
    script.with_suffix('.contract.json').write_text(json.dumps(data))
    assert not tool_contracts.validate(script)['ready_for_promote']


def test_router_rejects_substring_and_command_runs(tmp_path):
    scripts = tmp_path / 'scripts'; scripts.mkdir()
    (scripts / 'state.py').write_text('')
    result = tool_factory_payload(tmp_path, 'make a parser for receipts', 'receipt_parser', '', False)
    assert result['decision'] == 'insufficient_fit'
    assert not result['candidate_scripts']
    result = tool_factory_payload(tmp_path, 'make a parser for receipts', 'receipt_parser', '', True)
    run = subprocess.run(result['next_argv'], cwd=ROOT, env={**os.environ, 'SIPS_HOME': str(tmp_path)}, capture_output=True)
    assert run.returncode == 0


def test_joint_types_and_composition(tmp_path, monkeypatch):
    monkeypatch.setenv("SIPS_HOME", str(tmp_path / "home"))
    one = helper(tmp_path); data = contract()
    data['inputs'] = ['raw']; data['outputs'] = ['middle']
    one.with_suffix('.contract.json').write_text(json.dumps(data))
    two = one.parent / 'second.sh'; two.write_text('echo normalized')
    data['inputs'] = ['middle']; data['outputs'] = ['final']
    two.with_suffix('.contract.json').write_text(json.dumps(data))
    from sips_runtime.capabilities import record_validation
    for script in (one, two):
        record_validation(tool_contracts.validate(script))
    result = tool_factory_payload(tmp_path, 'convert', '', '', False, ['raw', 'local'], ['final'])
    assert result['decision'] == 'compose'
    assert result['composition']['steps'] == ['normalizer.py', 'second.sh']
    result = tool_factory_payload(tmp_path, 'convert', '', '', False, ['raw'], ['final'])
    assert result['decision'] == 'insufficient_fit'


def test_diagnosis_preserves_unknown_and_evidence():
    case = {'id': 'sample', 'grading': [{'kind': 'grep', 'arguments': {'path': 'absent'}}]}
    analysis = fix_drafter.analyze_failure(case, {'checkResults': [{'passed': False, 'evidence': 'file does not exist'}]})
    assert analysis['rootCause'] == 'Unestablished'
    assert analysis['failedChecks'][0]['evidence'] == 'file does not exist'
    assert 'relax' not in analysis['proposedFix']
    missing = fix_drafter.analyze_failure(case, {})
    assert len(missing['unavailableChecks']) == 1
    assert missing['failedChecks'] == []
    error = fix_drafter.analyze_failure(case, {'errorMessage': 'provider unavailable'})
    assert error['fixType'] == 'infrastructure'


def test_stale_case_is_not_diagnosed_as_current_failure():
    result = fix_drafter.analyze_failure({'id': 'x', 'version': 2, 'grading': [{'kind': 'grep'}]},
                                        {'caseVersion': 1, 'checkResults': [{'passed': False}]})
    assert result['fixType'] == 'evidence_unavailable'
    assert result['failedChecks'] == []


def test_scaffold_handles_multiline_summary_and_reports_unimplemented(tmp_path):
    result = cli(tmp_path, 'scaffold', 'quoted', '--summary', 'Parse "receipts"\nand normalize')
    assert result.returncode == 0
    run = subprocess.run([sys.executable, str(tmp_path / 'scripts/quoted.py'), '--json'], capture_output=True, text=True)
    assert run.returncode == 2
    assert json.loads(run.stdout)['status'] == 'not_implemented'


def test_router_validates_exact_candidate_outside_plugin(tmp_path):
    script = helper(tmp_path)
    payload = tool_factory_payload(tmp_path, 'normalize receipt', '', '', False)
    result = subprocess.run(payload['next_argv'], cwd=tmp_path, env={**os.environ, 'SIPS_HOME': str(tmp_path / 'home')},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['script'] == str(script.resolve())
    assert receipt['ready_for_promote']


def test_evaluator_revision_invalidates_registry(tmp_path,monkeypatch):
    monkeypatch.setenv('SIPS_HOME',str(tmp_path/'home'))
    script=helper(tmp_path)
    from sips_runtime.capabilities import registry, record_validation
    receipt=tool_contracts.validate(script)
    record_validation(receipt)
    assert registry(tmp_path)[0]['validation_status']=='current'
    monkeypatch.setattr(tool_contracts,'evaluator_identity',lambda:'different-evaluator')
    assert registry(tmp_path)[0]['validation_status']=='stale_or_unavailable'
