"""Executable contracts and bounded typed composition for local helpers.

Contracts contain direct helper invocations and output assertions, not shell commands.
Validation runs in disposable working directories; this is isolation of fixtures,
not an OS sandbox. Only validate trusted local helpers.
"""
from __future__ import annotations

import hashlib
import fnmatch
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from collections import deque

from sips_runtime.canonical import canonical_hash


def local_path(root, name):
    path = Path(root) / name
    if not isinstance(name, str) or Path(name).is_absolute() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('artifact paths must stay within their directory')
    return path


def read_contract(script):
    path = script.with_suffix('.contract.json')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError('contract must be an object')
    if data.get('schema') not in {'sips.tool-contract.v1', 'sips.tool-contract.v2', 'sips.tool-contract.v3'} or data.get('status') != 'implemented':
        raise ValueError('an implemented sips.tool-contract v1, v2 or v3 is required')
    for key in ('description', 'version', 'inputs', 'outputs', 'failure_semantics'):
        if not data.get(key):
            raise ValueError(f'missing contract field: {key}')
    if data['schema'] in {'sips.tool-contract.v2','sips.tool-contract.v3'}:
        from sips_runtime.hypergraph import validate_contract
        validate_contract(data)
    for key in (() if data['schema'] in {'sips.tool-contract.v2','sips.tool-contract.v3'} else ('inputs', 'outputs', 'preconditions', 'effects')):
        if not isinstance(data[key], list) or not all(isinstance(x, str) and x for x in data[key]):
            raise ValueError(f'{key} must be a nonempty list of strings')
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('nonempty behavioral cases required')
    names = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'] or case['id'] in names:
            raise ValueError('unique case ids required')
        names.add(case['id'])
        if not isinstance(case.get('args'), list) or not all(isinstance(x, str) for x in case['args']):
            raise ValueError('case args must be a string array')
        if '--help' in case['args'] or '-h' in case['args']:
            raise ValueError('help is not a behavioral case')
        if 'stdout' not in case and 'json' not in case and not case.get('files'):
            raise ValueError('case needs an exact stdout, JSON, or file assertion')
        if type(case.get('exit', 0)) is not int:
            raise ValueError('case exit must be an integer')
    resources = data.get('resources', [])
    if not isinstance(resources, list) or not all(isinstance(x, str) for x in resources):
        raise ValueError('resources must be a string array')
    return data


def bundle_files(script, contract):
    paths = [script.name, script.with_suffix('.contract.json').name]
    if script.with_suffix('.md').exists():
        paths.append(script.with_suffix('.md').name)
    paths += contract.get('resources', [])
    result = {}
    for name in sorted(set(paths)):
        path = local_path(script.parent, name)
        if not path.is_file():
            raise ValueError(f'missing resource: {name}')
        if name in {'validation.json', 'active.json', 'SKILL.md'}:
            raise ValueError('reserved package resource name')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def evaluator_identity():
    from sips_runtime import canonical
    return canonical_hash({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (Path(__file__), Path(canonical.__file__), Path(canonical.__file__).with_name('hypergraph.py'), Path(canonical.__file__).with_name('semantics.py'))})


def validate(script):
    receipt = {'schema': 'sips.tool-validation.v1', 'script': str(script), 'ok': False,
               'ready_for_promote': False, 'cases': [], 'errors': [], 'help_ok': False}
    try:
        contract = read_contract(script)
        files = bundle_files(script, contract)
        interpreter = sys.executable if script.suffix == '.py' else shutil.which('bash')
        if not interpreter:
            raise ValueError('interpreter unavailable')
        receipt.update(contract_digest=canonical_hash(contract), files=files,
                       artifact_digest=canonical_hash({'files': files, 'contract': canonical_hash(contract), 'python': sys.version, 'platform': sys.platform, 'evaluator': evaluator_identity()}),
                       evaluator_digest=evaluator_identity(),
                       environment={'interpreter': interpreter, 'python': sys.version, 'platform': sys.platform},
                       has_doc=script.with_suffix('.md').exists())
        with tempfile.TemporaryDirectory(prefix='sips-tool-validation-') as td:
            root = Path(td)
            bundle = root / 'bundle'; bundle.mkdir()
            for name in files:
                dst = local_path(bundle, name); dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(script.parent / name, dst)
            target = bundle / script.name
            syntax = ([interpreter, '-c', 'import ast,sys; ast.parse(open(sys.argv[1]).read())', str(target)]
                      if script.suffix == '.py' else [interpreter, '-n', str(target)])
            result = subprocess.run(syntax, capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise ValueError('syntax check failed: ' + result.stderr[-1000:])
            env = {**os.environ, 'SIPS_HOME': str(root / 'home'), 'PYTHONDONTWRITEBYTECODE': '1'}
            result = subprocess.run([interpreter, str(target), '--help'], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=10)
            receipt['help_ok'] = result.returncode == 0
            for index, case in enumerate(contract['cases']):
                cwd = root / f'case-{index}'; cwd.mkdir()
                case_env = {**env, 'SIPS_HOME': str(cwd / '.sips')}
                for name, content in case.get('fixtures', {}).items():
                    dst = local_path(cwd, name); dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(content)
                initial_files = {str(p.relative_to(cwd)): hashlib.sha256(p.read_bytes()).hexdigest() for p in cwd.rglob('*') if p.is_file()}
                command = [interpreter, str(target), *case['args']]
                try:
                    result = subprocess.run(command, cwd=cwd, env=case_env, capture_output=True,
                                            text=True, timeout=10)
                    passed = result.returncode == case.get('exit', 0)
                    if 'stdout' in case:
                        passed &= result.stdout == case['stdout']
                    if 'json' in case:
                        try:
                            passed &= json.loads(result.stdout) == case['json']
                        except json.JSONDecodeError:
                            passed = False
                    for name, content in case.get('files', {}).items():
                        path = local_path(cwd, name)
                        passed &= path.is_file() and path.read_text() == content
                    schema_valid = True
                    if contract['schema'] in {'sips.tool-contract.v2','sips.tool-contract.v3'} and result.returncode == 0:
                        from sips_runtime.hypergraph import accepts
                        outputs = contract['outputs']
                        try: value = json.loads(result.stdout)
                        except ValueError: value = result.stdout
                        schema_valid = accepts(next(iter(outputs.values())), value) if len(outputs) == 1 else isinstance(value,dict) and set(value) == set(outputs) and all(accepts(outputs[k],value[k]) for k in outputs)
                        passed &= schema_valid
                    undeclared = []
                    if contract['schema'] in {'sips.tool-contract.v2','sips.tool-contract.v3'}:
                        final_files = {str(p.relative_to(cwd)): hashlib.sha256(p.read_bytes()).hexdigest() for p in cwd.rglob('*') if p.is_file()}
                        changed = {k for k in initial_files.keys() | final_files.keys() if initial_files.get(k) != final_files.get(k)}
                        undeclared = [k for k in sorted(changed) if not any(fnmatch.fnmatchcase(k, pattern) for pattern in contract['effects']['writes'])]
                        passed &= not undeclared
                    receipt['cases'].append({'id': case['id'], 'passed': bool(passed), 'undeclared_writes': undeclared, 'output_schema_valid': schema_valid,
                        'exit': result.returncode, 'args': case['args'],
                        'fixture_digest': canonical_hash(case.get('fixtures', {})),
                        'assertion_digest': canonical_hash(case),
                        'stdout': result.stdout[-2000:], 'stderr': result.stderr[-2000:]})
                except subprocess.TimeoutExpired:
                    receipt['cases'].append({'id': case['id'], 'passed': False, 'error': 'timeout'})
            if bundle_files(target, contract) != files:
                raise ValueError('helper mutated its package during validation')
            if bundle_files(script, contract) != files:
                raise ValueError('source changed during validation')
        receipt['ok'] = receipt['ready_for_promote'] = receipt['help_ok'] and all(c['passed'] for c in receipt['cases'])
    except (ValueError, OSError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        receipt['errors'].append(str(exc))
    return receipt


def compose(capabilities, available, required, max_steps=4, **kwargs):
    """Bounded BFS over joint typed prerequisites. Returns a proposal, not proof."""
    if isinstance(available, dict) or isinstance(required, dict):
        from sips_runtime.hypergraph import compose as structural_compose
        return structural_compose(capabilities, available, required, max_steps, **kwargs)
    start = frozenset(available); goals = set(required)
    queue = deque([(start, [])]); seen = {start}
    while queue and len(seen) <= 1000:
        state, plan = queue.popleft()
        if goals <= state:
            return {'status': 'proposed', 'steps': plan, 'missing': []}
        if len(plan) >= max_steps:
            continue
        for capability in sorted(capabilities, key=lambda c: c['id']):
            if set(capability['inputs']) <= state:
                next_state = state | frozenset(capability['outputs'])
                if next_state not in seen:
                    seen.add(next_state); queue.append((next_state, plan + [capability['id']]))
    return {'status': 'insufficient_fit', 'steps': [], 'missing': sorted(goals - start)}
