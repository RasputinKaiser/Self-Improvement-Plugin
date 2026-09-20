"""Local, non-model evaluation with executable evidence and frozen suite identity."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import random
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from .canonical import canonical_hash

GROUPS = ('original', 'regression', 'counterexamples')


def path_in(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root):
        raise ValueError('path must remain in workspace')
    return path


def engine_identity():
    import hashlib
    import tool_contracts
    paths = [Path(__file__), Path(tool_contracts.__file__), Path(__file__).with_name('canonical.py'), Path(__file__).with_name('hypergraph.py'), Path(__file__).with_name('semantics.py'), Path(__file__).with_name('policy_graph.py')]
    return {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def check(spec, workspace, fixtures, timeout):
    start = time.monotonic()
    result = {'id': spec.get('id', '') if isinstance(spec, dict) else '', 'status': 'unavailable', 'checks_run': 0}
    try:
        if not isinstance(spec, dict): raise ValueError('check must be an object')
        kind = spec['kind']
        if kind == 'evaluator_challenge':
            result.update(challenge(spec, workspace, fixtures, timeout))
        elif kind == 'transfer':
            if not spec.get('task_family') or spec.get('split') != 'held_out' or not spec.get('instance_digest'):
                raise ValueError('held-out instance identity and task family required')
            case = spec['check']
            if case.get('kind') != 'command' or not any('{fixtures}' in arg for arg in case.get('argv',[])):
                raise ValueError('external frozen fixture consumer required')
            reports = {}
            for mode in ('none','episodic','procedure'):
                remaining = timeout - (time.monotonic()-start)
                if remaining <= 0: raise ValueError('transfer budget exhausted')
                with tempfile.TemporaryDirectory(prefix='sips-transfer-') as td:
                    clone = Path(td) / 'workspace'; shutil.copytree(workspace,clone)
                    reports[mode] = check({**case,'argv':case['argv']+['--memory-mode',mode]},clone,fixtures,remaining)
            result.update(arms=reports, task_family=spec['task_family'], instance_digest=spec['instance_digest'],
                checks_run=sum(r['checks_run'] for r in reports.values()),
                status='unavailable' if any(r['status']=='unavailable' for r in reports.values()) else reports['procedure']['status'],
                effectiveness='paired_task_improvement' if reports['procedure']['status']=='passed' and all(reports[m]['status']=='failed' for m in ('none','episodic')) else 'unknown',
                claim='Single supplied held-out instance; independent sealing and cross-family transfer not established by this adapter')
        elif kind in {'property', 'metamorphic'}:
            count = spec.get('samples', 8)
            if type(count) is not int or not 1 <= count <= 64 or type(spec.get('seed')) is not int:
                raise ValueError('seed and 1..64 samples required')
            generator = spec.get('generator', {})
            if set(generator) != {'min','max'} or any(type(x) is not int for x in generator.values()) or not -1000000 <= generator['min'] <= generator['max'] <= 1000000:
                raise ValueError('bounded integer generator required')
            if spec.get('relation') not in {'identity','idempotent'}: raise ValueError('unsupported independent relation')
            rng = random.Random(spec['seed']); cases = []
            for index in range(count):
                value = rng.randint(generator['min'], generator['max'])
                argv = spec['argv']
                if '{input}' not in argv: raise ValueError('literal input binding required')
                first = check({'kind':'command','argv':[str(value) if a=='{input}' else a for a in argv], 'json':value}, workspace, fixtures, max(.001, timeout-(time.monotonic()-start)))
                if spec['relation'] == 'identity': cases.append(first)
                else:
                    if first.get('exit') != 0: cases.append({**first,'status':'unavailable'});break
                    output = json.loads(first['stdout'])
                    second = check({'kind':'command','argv':[json.dumps(output) if a=='{input}' else a for a in argv], 'json':output}, workspace, fixtures, max(.001,timeout-(time.monotonic()-start)))
                    cases.append({'status':second['status'],'checks_run':1,'first':first,'second':second})
                if time.monotonic()-start >= timeout: raise ValueError('property budget exhausted')
            result.update(cases=cases, seed=spec['seed'], checks_run=sum(c['checks_run'] for c in cases),
                          status='unavailable' if any(c['status']=='unavailable' for c in cases) else 'passed' if all(c['status']=='passed' for c in cases) else 'failed')
        elif kind in {'command', 'pytest'}:
            argv = spec['argv']
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise ValueError('argv must be a nonempty string array')
            argv = [x.replace('{workspace}', str(workspace)).replace('{fixtures}', str(fixtures)).replace('{python}', sys.executable) for x in argv]
            if kind == 'command' and not any(k in spec for k in ('stdout', 'json', 'files')):
                raise ValueError('command needs behavioral assertions, not exit alone')
            with tempfile.TemporaryDirectory(prefix='sips-evaluator-') as td:
                xml = Path(td) / 'results.xml'
                if kind == 'pytest':
                    argv = [sys.executable, '-m', 'pytest', *argv, '--junitxml', str(xml)]
                env = {**os.environ, 'SIPS_HOME': str(Path(td) / 'home'), 'PYTHONDONTWRITEBYTECODE': '1'}
                process = subprocess.Popen(argv, cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                try: stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.communicate(); raise
                proc = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
                result.update(command=argv, exit=proc.returncode, stdout=proc.stdout[-8000:], stderr=proc.stderr[-4000:])
                if kind == 'pytest':
                    if not xml.exists():
                        raise ValueError('test report missing')
                    cases = ET.parse(xml).getroot().findall('.//testcase')
                    executed = [c for c in cases if c.find('skipped') is None]
                    if not executed:
                        raise ValueError('zero executed tests')
                    result['checks_run'] = len(executed)
                    result['assertion_failures'] = sum(c.find('failure') is not None for c in executed)
                    result['execution_errors'] = sum(c.find('error') is not None for c in executed)
                    result['status'] = 'passed' if proc.returncode == 0 and all(c.find('failure') is None and c.find('error') is None for c in executed) else 'failed'
                else:
                    passed = proc.returncode == spec.get('exit', 0)
                    assertions = []
                    if 'stdout' in spec:
                        assertions.append(proc.stdout == spec['stdout'])
                    if 'json' in spec:
                        try: assertions.append(json.loads(proc.stdout) == spec['json'])
                        except ValueError: assertions.append(False)
                    for name, content in spec.get('files', {}).items():
                        path = path_in(workspace, name)
                        assertions.append(path.is_file() and path.read_text() == content)
                    if not assertions: raise ValueError('zero behavioral assertions')
                    result.update(checks_run=len(assertions), assertions=assertions,
                                  status='passed' if passed and all(assertions) else 'failed')
        elif kind == 'policy_cases':
            from .policy_graph import run
            policy = json.loads(path_in(workspace, spec['path']).read_text())
            cases = spec['cases']
            if not isinstance(cases,list) or not 1 <= len(cases) <= 32: raise ValueError('1..32 frozen policy cases required')
            reports=[]; assertions=[]
            for case in cases:
                expected=case['expected']
                if not isinstance(expected,dict) or not expected or set(expected)-{'status','intervention','probe'} or 'status' not in expected: raise ValueError('explicit policy result assertion required')
                report=run(policy,case['outcomes'],fixtures,case['now'])
                actual={'status':report['status'],'intervention':report.get('decision',{}).get('intervention'),'probe':report.get('probe')}
                assertions.append(all(actual[k]==v for k,v in expected.items()))
                reports.append(report)
            result.update(checks_run=len(assertions),assertions=assertions,policy_cases=reports,status='passed' if all(assertions) else 'failed')
        elif kind == 'artifact':
            path = path_in(workspace, spec['path'])
            assertions = []
            if 'exists' in spec: assertions.append(path.exists() == spec['exists'])
            if 'text' in spec: assertions.append(path.is_file() and path.read_text() == spec['text'])
            if 'pattern' in spec: assertions.append(path.is_file() and re.search(spec['pattern'], path.read_text()) is not None)
            if not assertions: raise ValueError('artifact assertion missing')
            result.update(checks_run=len(assertions), assertions=assertions, status='passed' if all(assertions) else 'failed')
        elif kind == 'sequence':
            sequence = json.loads(path_in(workspace, spec['path']).read_text())
            expected = spec['ordered']
            if not isinstance(sequence, list) or not expected: raise ValueError('nonempty sequence requirement needed')
            pos = 0
            for item in sequence:
                if pos < len(expected) and item == expected[pos]: pos += 1
            result.update(checks_run=1, status='passed' if pos == len(expected) else 'failed', observed=sequence)
        elif kind == 'contract':
            from tool_contracts import validate
            receipt = validate(path_in(workspace, spec['script']))
            result.update(receipt=receipt, checks_run=len(receipt['cases']),
                          status='passed' if receipt['ready_for_promote'] else 'failed' if receipt['cases'] else 'unavailable')
        elif kind == 'llmJudge':
            raise ValueError('model judge requires explicit active-task review; no model launched')
        else:
            raise ValueError('unsupported adapter: ' + str(kind))
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        result.update(status='unavailable', error=str(exc))
    result['duration_seconds'] = time.monotonic() - start
    return result


def evaluate(suite, workspace, fixtures, *, command_timeout=120, budget_seconds=600):
    start = time.monotonic(); identity = engine_identity()
    report = {'schema': 'sips.evaluation.v2', 'suite_digest': canonical_hash(suite),
              'engine': identity, 'groups': {}, 'status': 'unavailable', 'checks_run': 0}
    for group in GROUPS:
        results = []
        specs = suite.get(group, [])
        if not isinstance(specs, list) or not specs:
            results.append({'status': 'unavailable', 'error': 'required group has zero cases', 'checks_run': 0})
        else:
            for spec in specs:
                remaining = budget_seconds - (time.monotonic() - start)
                if remaining <= 0:
                    results.append({'status': 'unavailable', 'error': 'evaluation budget exhausted', 'checks_run': 0}); break
                results.append(check(spec, Path(workspace), Path(fixtures), min(command_timeout, remaining)))
        report['groups'][group] = results
    flat = [r for group in report['groups'].values() for r in group]
    report['checks_run'] = sum(r['checks_run'] for r in flat)
    report['status'] = 'unavailable' if any(r['status'] == 'unavailable' for r in flat) else 'passed' if all(r['status'] == 'passed' for r in flat) else 'failed'
    if engine_identity() != identity:
        report.update(status='unavailable', error='evaluator changed during execution')
    report['duration_seconds'] = time.monotonic() - start
    return report


def challenge(spec, workspace, fixtures, timeout):
    """Challenge a frozen oracle with a known-good control and declared mutants.

    Trusted local fixture execution, not an OS sandbox. Infrastructure errors
    and nonzero command exits do not count as successful mutant rejection.
    """
    started=time.monotonic();control=spec.get('control');mutants=spec.get('mutants');checks=spec.get('checks')
    def patch_shape(patch):
        if not isinstance(patch,dict) or not patch or len(patch)>16 or any(not isinstance(k,str) or not isinstance(v,str) or len(v)>100000 for k,v in patch.items()):
            raise ValueError('bounded text-file patches required')
        for name in patch: path_in(workspace,name)
    patch_shape(control)
    if not isinstance(mutants,list) or not 1<=len(mutants)<=16: raise ValueError('1..16 mutants required')
    if not isinstance(checks,list) or not 1<=len(checks)<=32 or any(not isinstance(c,dict) or c.get('kind') not in {'command','artifact','sequence','pytest'} for c in checks):
        raise ValueError('1..32 independent nonrecursive checks required')
    seen=set()
    for mutant in mutants:
        if not isinstance(mutant,dict) or not isinstance(mutant.get('id'),str) or not mutant['id'] or mutant['id'] in seen: raise ValueError('unique mutant IDs required')
        seen.add(mutant['id']);patch_shape(mutant.get('files'))
        if not set(mutant['files'])<=set(control): raise ValueError('mutants must change only declared control files')
        if all(control[k]==v for k,v in mutant['files'].items()): raise ValueError('mutant identical to control')
    arms=[]
    for name,patch in [('control',{}),*[(m['id'],m['files']) for m in mutants]]:
        with tempfile.TemporaryDirectory(prefix='sips-oracle-challenge-') as td:
            clone=Path(td)/'workspace';shutil.copytree(workspace,clone)
            for filename,content in {**control,**patch}.items():
                dest=path_in(clone,filename);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)
            results=[]
            for case in checks:
                remaining=timeout-(time.monotonic()-started)
                if remaining<=0: raise ValueError('challenge budget exhausted')
                r=check(case,clone,fixtures,remaining)
                if case['kind']=='command' and r.get('exit')!=0:
                    r={**r,'status':'unavailable','error':'nonzero execution is not behavioral mutant rejection'}
                if case['kind']=='pytest' and (r.get('exit') not in (0,1) or r.get('execution_errors',0) or (r.get('exit')==1 and not r.get('assertion_failures'))):
                    r={**r,'status':'unavailable','error':'pytest infrastructure failure'}
                results.append(r)
            status='unavailable' if any(r['status']=='unavailable' for r in results) else 'failed' if any(r['status']=='failed' for r in results) else 'passed'
            arms.append({'id':name,'status':status,'checks':results,'patch_digest':canonical_hash({**control,**patch})})
    status='unavailable' if arms[0]['status']!='passed' or any(a['status']=='unavailable' for a in arms) else 'passed' if all(a['status']=='failed' for a in arms[1:]) else 'failed'
    return {'status':status,'checks_run':sum(r['checks_run'] for a in arms for r in a['checks']),
            'arms':arms,'surviving_mutants':[a['id'] for a in arms[1:] if a['status']=='passed'],
            'challenge_identity':canonical_hash(spec),'claim':'Sensitivity to declared mutations only; not completeness of the evaluator.'}
