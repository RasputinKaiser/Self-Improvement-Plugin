"""Capability registry projected from current contracts and validation receipts."""
import json
from pathlib import Path
import sys
from sips_paths import harness_home
from .canonical import canonical_hash
from .events import atomic_write_json


def record_validation(receipt):
    identity = canonical_hash(receipt)
    path = harness_home() / 'tool_factory' / 'validations' / (identity + '.json')
    atomic_write_json(path, receipt)
    return path


def registry(root):
    from tool_contracts import read_contract, bundle_files, evaluator_identity
    receipts = []
    for path in (harness_home() / 'tool_factory/validations').glob('*.json'):
        try:
            value = json.loads(path.read_text())
            if value.get('ready_for_promote'): receipts.append((path, value))
        except (ValueError, OSError): pass
    result = []
    for script in sorted((Path(root) / 'scripts').glob('*')):
        if script.suffix not in {'.py', '.sh'} or not script.is_file(): continue
        try:
            contract = read_contract(script); files = bundle_files(script, contract)
        except (ValueError, OSError, TypeError, KeyError): continue
        matched = [(path, r) for path, r in receipts if Path(r.get('script','')).resolve() == script.resolve()
                   and r.get('evaluator_digest') == evaluator_identity()
                   and r.get('files') == files and r.get('contract_digest') == canonical_hash(contract)
                   and r.get('environment',{}).get('python') == sys.version
                   and r.get('environment',{}).get('platform') == sys.platform]
        result.append({**contract, 'id': script.name, 'version': contract['version'], 'inputs': contract['inputs'],
                       'outputs': contract['outputs'], 'preconditions': contract['preconditions'],
                       'effects': contract['effects'], 'dependencies': contract.get('resources',[]),
                       'consumers': contract.get('consumers', []), 'description': contract['description'],
                       'validation_status': 'current' if matched else 'stale_or_unavailable',
                       'receipt': str(matched[-1][0]) if matched else None})
    return result


def activate_package(skill_dir, payload):
    """One authoritative pointer; all human-facing projections follow it."""
    skill_dir = Path(skill_dir)
    dispatcher = skill_dir / 'dispatch.py'
    dispatcher.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
active=json.loads(Path(__file__).with_name('active.json').read_text())
os.execv(active['interpreter'], [active['interpreter'], active['entrypoint'], *sys.argv[1:]])
''')
    skill_dir.joinpath('SKILL.md').write_text('---\nname: '+skill_dir.name+'\ndescription: Validated local helper\n---\n\nRun `python3 '+str(dispatcher)+'` with the helper arguments. The authoritative active.json selects the validated version.\n')
    atomic_write_json(skill_dir / 'active.json', payload)


def intervention_memories(workspace, query, limit=10):
    """Advisory evidence projection; no state writes and no zero-overlap matches."""
    import re
    from .adaptation import workspace_id
    terms = set(re.findall(r'[a-z0-9]+', query.lower())) - {'a', 'the', 'to', 'for', 'and'}
    if not terms: return []
    matches = []
    for path in (harness_home() / 'adaptation').glob('*/memory-*.json'):
        try:
            record = json.loads(path.read_text())
            if record.get('workspace_id') != workspace_id(workspace): continue
            score = len(terms & set(re.findall(r'[a-z0-9]+', record.get('task','').lower())))
            if not score or not Path(record.get('receipt','')).is_file(): continue
            matches.append({**record, 'memory_path': str(path), 'score': score,
                            'recorded_at': path.stat().st_mtime, 'verify_before_use': True})
        except (OSError, ValueError, TypeError): continue
    matches.sort(key=lambda r: (-r['score'], -r['recorded_at']))
    return matches[:max(0, min(limit, 100))]
