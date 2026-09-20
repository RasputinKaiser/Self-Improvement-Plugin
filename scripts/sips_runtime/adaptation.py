"""Durable proposal-only adaptation controller. All adapters delegate here."""
from __future__ import annotations
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from .canonical import canonical_hash
from .events import EventStore, atomic_write_json, transition_lock, RevisionConflict, IdempotencyConflict
from .snapshots import SnapshotStore
from .evaluation import path_in
from sips_paths import harness_home

INTERVENTIONS = {'gather_evidence', 'refresh_context', 'repair_interface', 'reuse', 'compose',
                 'repair_implementation', 'create_tool', 'consolidate', 'stop'}
DEFAULTS = {'candidate_revisions': 2, 'composition_steps': 4, 'command_timeout': 120, 'evaluation_seconds': 600}


def file_identity(path):
    path = Path(path)
    return canonical_hash({'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'mode': path.stat().st_mode & 0o777})


def manifest(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink(): raise ValueError('candidate/snapshot symlinks are unsupported')
        if path.is_file():
            result[str(path.relative_to(root))] = file_identity(path)
    return result


def workspace_id(root):
    return canonical_hash({'workspace': str(Path(root).resolve())})


class AdaptationController:
    def __init__(self, home=None):
        self.home = Path(home) if home else harness_home()
        self.root = self.home / 'adaptation'

    def validate_tool(self, script):
        from datetime import datetime, timezone
        from tool_contracts import validate
        from .capabilities import record_validation
        receipt = validate(Path(script))
        receipt['validated_at'] = datetime.now(timezone.utc).isoformat()
        return receipt, record_validation(receipt)

    def promote_tool(self, script, receipt, skill_dir):
        """Explicit factory publication; evaluation alone never calls this action."""
        from tool_contracts import validate, bundle_files
        from .capabilities import activate_package
        script, skill_dir = Path(script), Path(skill_dir)
        contract = json.loads(script.with_suffix('.contract.json').read_text())
        versions = skill_dir / 'versions'; versions.mkdir(parents=True, exist_ok=True)
        version = receipt['artifact_digest']; destination = versions / version
        with transition_lock(skill_dir / '.promotion.lock'):
            with tempfile.TemporaryDirectory(prefix='.candidate-', dir=versions) as td:
                staged = Path(td)
                for relative in receipt['files']:
                    target = path_in(staged, relative); target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path_in(script.parent, relative), target)
                if bundle_files(staged / script.name, contract) != receipt['files']:
                    raise ValueError('source changed after validation')
                packaged = validate(staged / script.name)
                if not packaged['ready_for_promote'] or packaged['artifact_digest'] != version:
                    raise ValueError('packaged consumer validation failed')
                if destination.exists():
                    if bundle_files(destination / script.name, contract) != receipt['files']:
                        raise ValueError('existing version has drifted')
                else: os.rename(staged, destination)
                atomic_write_json(destination / 'validation.json', packaged)
            activate_package(skill_dir, {'schema': 'sips.tool-active.v2', 'artifact_digest': version,
                'entrypoint': str(destination / script.name),
                'interpreter': sys.executable if script.suffix == '.py' else shutil.which('bash'),
                'contract': contract, 'validation': str(destination / 'validation.json'),
                'discovery_status': 'packaged; host discovery unverified'})
        return destination

    def directory(self, episode):
        if not isinstance(episode, str) or len(episode) != 64 or any(c not in '0123456789abcdef' for c in episode):
            raise ValueError('episode must be a 64-character hexadecimal identity')
        return self.root / episode

    def history(self, episode):
        directory = self.directory(episode)
        if not (directory / 'head.json').is_file(): raise ValueError('unknown episode')
        with EventStore(directory).event_snapshot() as events:
            return list(events)

    def read(self, episode, view='status', query='', context=None):
        history = self.history(episode)
        if not history: raise ValueError("incomplete observation; no durable event")
        latest = history[-1]
        if 'state' not in latest.payload:
            return {'schema': 'sips.adaptation.v2', 'episode': episode, 'revision': latest.revision,
                    'state': 'unavailable', 'historical_status': latest.payload.get('stage'),
                    'claim_boundary': 'Legacy evaluator claim; not reverified or activated',
                    'events': [dict(e.payload) for e in history]}
        state = dict(latest.payload['state'])
        result = {**state, 'episode': episode, 'revision': latest.revision, 'schema': 'sips.adaptation.v2'}
        directory = self.directory(episode)
        if view == 'visual':
            from .visuals import episode_view
            from .evidence_graph import project as dependencies
            from .opportunities import project as opportunities
            result['visual'] = episode_view(state, episode, latest.revision, dependencies(directory,state), opportunities(state))
        if view == 'opportunities':
            from .opportunities import project
            result['opportunities'] = project(state)
        if view == 'dependencies':
            from .evidence_graph import project
            result['dependencies'] = project(directory, state)
        if view == 'next':
            from .workflow import next_packet
            result['next'] = next_packet(state, episode, latest.revision)
            result['next']['baseline_path'] = str(directory / 'baseline')
            result['next']['acceptance_criteria'] = json.loads((directory / state.get('suite_file','suite.json')).read_text())
        if view == 'outcomes':
            from .workflow import comparison
            result['outcomes'] = comparison(state.get('later_use',[]))
        if view == 'procedures':
            from .procedures import retrieval_audit, motif
            proposals = []; artifact_rejections = []
            for path in sorted(self.root.glob('*/head.json')):
                scoped_procedure = False
                try:
                    other = self.read(path.parent.name)
                    if other.get('workspace_id') != state['workspace_id'] or other.get('artifact',{}).get('kind') != 'procedure': continue
                    scoped_procedure = True
                    self._validate_artifact(path.parent, other)
                    proposals.append(json.loads(path_in(path.parent / 'candidate',other['artifact']['path']).read_text()))
                except (ValueError,OSError,KeyError) as exc:
                    if scoped_procedure: artifact_rejections.append({'episode':path.parent.name,'status':'unavailable','reason':str(exc)[:200]})
            result['retrieval_audit'] = retrieval_audit(proposals, query or state['task'], context or {}, time.time(), self._sources_current)
            result['retrieval_audit']['artifact_rejections'] = artifact_rejections
            result['procedures'] = result['retrieval_audit']['eligible']
            result['motifs'] = {item['identity']:motif(item['procedure']['actions']) for item in result['procedures']}
        if view == 'lineage':
            result['lineage'] = self.lineage(state['workspace_id'])
            from .procedures import pareto
            result['pareto'] = pareto(result['lineage'])
        if view == 'investigation':
            result['investigation'] = state.get('investigation')
        if view == 'events': result['events'] = [dict(e.payload) for e in history]
        if view in {'evidence', 'receipt'}:
            result['results'] = json.loads((directory / state['receipt']).read_text()) if state.get('receipt') else None
            if state.get('receipt_digest') and canonical_hash(result['results']) != state['receipt_digest']: raise ValueError('evaluation receipt drift')
        if view == 'diff':
            lines = []
            for name in state['allowed_files']:
                old, new = directory / 'baseline' / name, directory / 'candidate' / name
                before = old.read_text(errors='replace').splitlines(True) if old.exists() else []
                after = new.read_text(errors='replace').splitlines(True) if new.exists() else []
                lines.extend(difflib.unified_diff(before, after, fromfile='baseline/' + name, tofile='candidate/' + name))
            result['diff'] = ''.join(lines)
        return result

    def lineage(self, identity):
        records = []
        for path in sorted(self.root.glob('*/head.json')):
            try:
                history = self.history(path.parent.name)
                for event in history:
                    state = event.payload.get('state', {})
                    if state.get('workspace_id') != identity or not state.get('candidate_digest'): continue
                    record = {'episode': path.parent.name, 'revision': event.revision,
                              'candidate': state['candidate_digest'], 'state': state['state'],
                              'parent': state.get('parent_candidate'), 'receipt': state.get('receipt'),
                              'cost': state.get('evaluation_seconds'), 'success': None,
                              'complexity': len(state.get('candidate_manifest', {})), 'coverage': None}
                    if state.get('receipt'):
                        receipt = json.loads((path.parent / state['receipt']).read_text())
                        report = receipt.get('reports',{}).get('candidate',{})
                        if report.get('status') in {'passed','failed'}:
                            record['success'] = int(report['status']=='passed')
                            record['coverage'] = report.get('checks_run')
                    records.append(record)
            except (ValueError, OSError): continue
        return records

    def _sources_current(self, sources):
        for source in sources:
            try:
                history = self.history(source['episode'])
                event = next(e for e in history if e.revision == source['revision'])
                if event.event_digest != source['event_digest']: return False
            except (ValueError, OSError, StopIteration): return False
        return True

    def write(self, action, request):
        request = dict(request)
        key = request.get('idempotency_key'); revision = request.get('expected_revision')
        if not isinstance(key, str) or not key.strip() or type(revision) is not int or revision < 0:
            raise ValueError('idempotency_key and nonnegative expected_revision required')
        if action == 'observe':
            episode = canonical_hash({'workspace': workspace_id(request['workspace']), 'key': key})
        else: episode = request['episode']
        directory = self.directory(episode)
        if action != 'observe' and not (directory / 'head.json').exists(): raise ValueError('unknown episode')
        with transition_lock(directory / '.transition.lock'):
            store = EventStore(directory)
            with store.event_snapshot() as snapshot: history = list(snapshot)
            digest = canonical_hash({'action': action, 'request': request})
            for event in history:
                if event.payload.get('request_key') == key:
                    if event.payload['request_digest'] != digest: raise IdempotencyConflict('key reused with different request')
                    return {**event.payload['state'], 'episode': episode, 'revision': event.revision}
            current_revision = history[-1].revision if history else 0
            if revision != current_revision: raise RevisionConflict(f'expected {revision}, actual {current_revision}')
            if history and history[-1].payload.get('state', {}).get('probe_running') and action != 'recover':
                raise ValueError('interrupted probe requires recovery')
            if (directory / 'activation-journal.json').exists() and action != 'recover':
                raise ValueError('activation transaction requires recovery')
            if history and 'state' not in history[-1].payload: raise ValueError('legacy episode is read-only; observe a new episode')
            state = dict(history[-1].payload['state']) if history else {}
            if action == 'observe':
                if history: raise ValueError('episode already exists')
                state = self._observe(directory, request)
            else:
                if not state: raise ValueError('episode has no observation')
                state = self._transition(directory, state, action, request, store, episode)
            event = store.append('adaptation.' + action, episode,
                                 {'state': state, 'request_key': key, 'request_digest': digest},
                                 expected_revision=store.revision)
            SnapshotStore(directory).save(event.revision, event.event_digest, state)
            if action in {'activate', 'rollback'}:
                (directory / 'activation-journal.json').unlink(missing_ok=True)
            return {**state, 'episode': episode, 'revision': event.revision}

    def _observe(self, directory, request):
        workspace = Path(request['workspace']).resolve()
        if not workspace.is_dir(): raise ValueError('workspace missing')
        allowed = request.get('allowed_files', [])
        context = request.get('context_files', [])
        if not isinstance(allowed, list) or not isinstance(context, list): raise ValueError('file scopes must be arrays')
        task = request.get('task', '')
        if not task: raise ValueError('task requirement required')
        limits = {**DEFAULTS, **request.get('limits', {})}
        if set(limits) != set(DEFAULTS) or any(type(v) not in (int, float) or v <= 0 for v in limits.values()):
            raise ValueError('invalid limits')
        if type(limits['candidate_revisions']) is not int or type(limits['composition_steps']) is not int:
            raise ValueError('revision and composition limits must be integers')
        for name in ('baseline', 'fixtures', 'evaluator', 'suite.json'):
            partial = directory / name
            if partial.exists():
                os.rename(partial, directory / (name + '.interrupted-' + str(time.time_ns())))
        baseline = directory / 'baseline'; baseline.mkdir(exist_ok=True)
        for name in sorted(set(allowed + context)):
            src = path_in(workspace, name)
            if (workspace / name).is_symlink(): raise ValueError('symlink scopes unsupported')
            if src.exists():
                if not src.is_file(): raise ValueError('scope entries must name individual files')
                dst = path_in(baseline, name); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        suite = request.get('suite', {})
        fixtures = directory / 'fixtures'; fixtures.mkdir(exist_ok=True)
        for name, content in request.get('fixtures', {}).items():
            path = path_in(fixtures, name); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        atomic_write_json(directory / 'suite.json', suite)
        # Pin an evaluator package outside both the candidate and the working checkout.
        engine = directory / 'evaluator'; (engine / 'sips_runtime').mkdir(parents=True, exist_ok=True)
        (engine / 'sips_runtime/__init__.py').write_text('')
        for name in ['evaluation.py', 'canonical.py', 'hypergraph.py', 'semantics.py', 'policy_graph.py']:
            shutil.copy2(Path(__file__).with_name(name), engine / 'sips_runtime' / name)
        shutil.copy2(Path(__file__).parents[1] / 'tool_contracts.py', engine / 'tool_contracts.py')
        worker = "import sys,json\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).parent))\nfrom sips_runtime.evaluation import evaluate\nsuite=json.loads(Path(sys.argv[1]).read_text())\nprint(json.dumps(evaluate(suite,Path(sys.argv[2]),Path(sys.argv[3]),command_timeout=float(sys.argv[4]),budget_seconds=float(sys.argv[5]))))\n"
        (engine / 'worker.py').write_text(worker)
        return {'state': 'observed', 'workspace': str(workspace), 'workspace_id': workspace_id(workspace),
                'task': task, 'evidence': request.get('evidence', []), 'hypotheses': [],
                'allowed_files': sorted(set(allowed)), 'context_files': sorted(set(context)),
                'baseline_manifest': manifest(baseline), 'suite_digest': canonical_hash(suite),
                'fixtures_manifest': manifest(fixtures), 'evaluator_manifest': manifest(engine),
                'environment': {'python': sys.version, 'platform': sys.platform, 'interpreter': sys.executable},
                'limits': limits, 'attempts': 0, 'evaluation_seconds': 0, 'effectiveness': 'unknown'}

    def _transition(self, directory, state, action, request, store, episode):
        status = state['state']
        if action == 'advance':
            from .workflow import next_packet, validate_authorship
            packet = next_packet(state, episode, request['expected_revision'])
            if request.get('packet_id') != packet['packet_id']: raise ValueError('stale or mismatched work packet')
            if not packet['action']: raise ValueError('packet requires review or is stopped; no automatic activation')
            output = request.get('output',{})
            if not isinstance(output,dict) or set(output) != set(packet['required_output']): raise ValueError('exact work packet output fields required')
            if packet['kind']=='author_candidate':
                authorship = validate_authorship(output['authorship'])
                authorship['candidate_manifest'] = manifest(directory / 'candidate')
                authorship['packet_id'] = packet['packet_id']
                state.setdefault('authorship',[]).append(authorship)
                output = {}
            return self._transition(directory,state,packet['action'],{**request,**output,**packet['fixed_input']},store,episode)
        if action == 'notice':
            from .opportunities import capture
            return capture(state, request)
        if action == 'link_outcome':
            return self._link_outcome(directory,state,request)
        if action in {'investigate', 'probe', 'reduce', 'conclude', 'add_counterexamples', 'artifact', 'compose', 'policy_trial', 'analyze'}:
            return self._research_transition(directory, state, action, request, store, episode)
        if action == 'diagnose':
            if status not in {'observed', 'diagnosing', 'unavailable', 'rejected'}: raise ValueError('cannot diagnose in current state')
            state.update(state='diagnosing', hypotheses=request.get('hypotheses', []))
        elif action == 'propose':
            if status not in {'observed', 'diagnosing', 'unavailable', 'rejected'}: raise ValueError('cannot propose in current state')
            intervention = request.get('intervention')
            if intervention not in INTERVENTIONS or not request.get('rationale'): raise ValueError('intervention and rationale required')
            state.update(state='proposed', intervention=intervention, rationale=request['rationale'])
            state['work_package'] = {key: state[key] for key in ('task', 'evidence', 'hypotheses', 'allowed_files', 'suite_digest', 'intervention', 'limits')}
            state['work_package']['acceptance_criteria'] = json.loads((directory / state.get('suite_file', 'suite.json')).read_text())
            if intervention == 'stop': state.update(state='canceled', reason=request['rationale'])
        elif action == 'build':
            if status != 'proposed': raise ValueError('proposal required')
            if state['attempts'] >= state['limits']['candidate_revisions']:
                state.update(state='unavailable', reason='candidate revision budget exhausted'); return state
            candidate = directory / 'candidate'
            if candidate.exists():
                archive = directory / f"candidate-{state['attempts']}"
                if archive.exists(): raise ValueError('candidate archive already exists; recover first')
                os.rename(candidate, archive)
            shutil.copytree(directory / 'baseline', candidate)
            state['parent_candidate'] = state.get('candidate_digest')
            state.update(state='building', attempts=state['attempts'] + 1, candidate_path=str(candidate))
        elif action == 'evaluate':
            if status != 'building': raise ValueError('candidate must be built')
            self._frozen(directory, state)
            self._validate_artifact(directory, state)
            candidate_manifest = manifest(directory / 'candidate')
            changed = {p for p in set(candidate_manifest) | set(state['baseline_manifest']) if candidate_manifest.get(p) != state['baseline_manifest'].get(p)}
            if not changed <= set(state['allowed_files']): raise ValueError('candidate changed files outside permitted scope')
            state.update(state='evaluating', evaluation_started_at=time.time(), candidate_manifest=candidate_manifest,
                         candidate_digest=canonical_hash({'files': candidate_manifest, 'baseline': state['baseline_manifest'],
                             'suite': state['suite_digest'], 'fixtures': state['fixtures_manifest'],
                             'evaluator': state['evaluator_manifest'], 'environment': state['environment']}))
            store.append('adaptation.evaluation_started', episode, {'state': dict(state)})
            remaining = state['limits']['evaluation_seconds'] - state['evaluation_seconds']
            reports = {}
            started = time.monotonic()
            try:
                if remaining <= 0: raise ValueError('evaluation budget exhausted')
                for variant in ('baseline', 'candidate'):
                    remaining = state['limits']['evaluation_seconds'] - state['evaluation_seconds'] - (time.monotonic() - started)
                    if remaining <= 0: raise ValueError('evaluation budget exhausted')
                    with tempfile.TemporaryDirectory(prefix='evaluation-', dir=directory) as td:
                        workspace = Path(td) / 'workspace'; shutil.copytree(directory / variant, workspace)
                        cmd = [sys.executable, '-I', '-B', str(directory / 'evaluator/worker.py'), str(directory / state.get('suite_file', 'suite.json')),
                               str(workspace), str(directory / 'fixtures'), str(state['limits']['command_timeout']), str(remaining)]
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                        try: out, err = proc.communicate(timeout=remaining + 2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL); proc.communicate(); raise ValueError('evaluation timed out')
                        if proc.returncode: raise ValueError('evaluator failed: ' + err[-2000:])
                        reports[variant] = json.loads(out)
                self._frozen(directory, state)
                if manifest(directory / 'candidate') != candidate_manifest: raise ValueError('candidate changed during evaluation')
                candidate_status = reports['candidate']['status']
                if reports['baseline']['status'] == 'unavailable' or candidate_status == 'unavailable': state['state'] = 'unavailable'
                elif candidate_status == 'passed': state['state'] = 'ready_for_review'
                else: state['state'] = 'rejected'
                state['effectiveness'] = 'paired_improvement' if state['state'] == 'ready_for_review' and reports['baseline']['status'] == 'failed' else 'unknown'
            except (OSError, ValueError, TypeError, KeyError) as exc:
                state.update(state='unavailable', reason=str(exc))
            state['evaluation_seconds'] += time.monotonic() - started
            receipt = f"receipt-{state['attempts']}-{store.revision}.json"
            atomic_write_json(directory / receipt, {'schema': 'sips.adaptation-comparison.v2', 'reports': reports,
                'candidate_digest': state['candidate_digest'], 'suite_digest': state['suite_digest'],
                'state': state['state'], 'effectiveness': state['effectiveness']})
            state['receipt'] = receipt
            state['receipt_digest'] = canonical_hash(json.loads((directory / receipt).read_text()))
            atomic_write_json(directory / f"memory-{state['attempts']}-{store.revision}.json", {'schema': 'sips.intervention-memory.v1',
                'workspace_id': state['workspace_id'], 'task': state['task'], 'intervention': state['intervention'],
                'status': state['state'], 'effectiveness': state['effectiveness'], 'receipt': str(directory / receipt),
                'verify_before_use': True, 'activation': 'none'})
        elif action == 'activate':
            if status != 'ready_for_review' or request.get('approved_candidate') != state.get('candidate_digest'):
                raise ValueError('explicit approval of exact review-ready candidate required')
            self._frozen(directory, state)
            self._validate_artifact(directory, state)
            if manifest(directory / 'candidate') != state['candidate_manifest']: raise ValueError('candidate drift')
            self._apply(directory, state, rollback=False)
            state.update(state='activated', approved_candidate=request['approved_candidate'])
        elif action == 'rollback':
            if status != 'activated' or request.get('approved_candidate') != state.get('candidate_digest'):
                raise ValueError('explicit activated candidate required')
            self._apply(directory, state, rollback=True)
            state.update(state='canceled', reason='explicit rollback')
        elif action == 'recover':
            if (directory / 'activation-journal.json').exists():
                journal = json.loads((directory / 'activation-journal.json').read_text())
                committed = status == ('canceled' if journal['rollback'] else 'activated')
                if committed:
                    (directory / 'activation-journal.json').unlink()
                else:
                    self._recover_activation(directory, state)
                    state.update(state='unavailable', reason='interrupted activation restored to prior state')
            elif state.get('probe_running'):
                state['evaluation_seconds'] = min(state['limits']['evaluation_seconds'], state['evaluation_seconds'] + max(0, time.time()-state.pop('probe_started_at', time.time())))
                state.pop('probe_running', None)
                state.update(state='unavailable', reason='interrupted probe; evidence unavailable')
            elif status in {'evaluating', 'building'}:
                if status == 'evaluating':
                    state['evaluation_seconds'] = min(state['limits']['evaluation_seconds'], state['evaluation_seconds'] + max(0, time.time() - state.get('evaluation_started_at', time.time())))
                state.update(state='unavailable', reason='interrupted work; candidate retained for inspection')
            else: raise ValueError('no interrupted operation')
        elif action == 'cancel':
            if status == 'activated': raise ValueError('use explicit rollback for activated candidate')
            state.update(state='canceled', reason=request.get('reason', 'canceled'))
        else: raise ValueError('unsupported action')
        return state

    def _link_outcome(self, directory, state, request):
        source = request['source_candidate']
        if source != state.get('candidate_digest') or state['state'] not in {'ready_for_review','activated'}:
            raise ValueError('exact reviewed source candidate required')
        self._frozen(directory,state)
        if manifest(directory / 'candidate') != state['candidate_manifest']: raise ValueError('source candidate drift')
        target = self.read(request['target_episode'],'receipt')
        if request['target_episode'] == directory.name: raise ValueError('later use requires a different episode')
        report = target.get('results') or {}
        if report.get('candidate_digest') != target.get('candidate_digest') or report.get('suite_digest') != target.get('suite_digest'):
            raise ValueError('target receipt identity mismatch')
        if not target.get('receipt_digest'): raise ValueError('pinned target receipt required')
        if not target.get('authorship') or target['state'] not in {'ready_for_review','activated','rejected','unavailable'}:
            raise ValueError('executed authored target evaluation required')
        target_dir = self.directory(request['target_episode']); self._frozen(target_dir,target)
        if manifest(target_dir/'candidate') != target.get('candidate_manifest'): raise ValueError('target candidate drift')
        mode = request.get('memory_mode');task = request.get('task_identity')
        if mode not in {'none','episodic','procedure'} or not isinstance(task,str) or not task or len(task)>128: raise ValueError('declared task identity and memory mode required')
        uses = list(state.get('later_use',[]))
        if len(uses)>=128: raise ValueError('later-use archive limit reached')
        if any(r['target_episode']==target['episode'] or (r['task_identity']==task and r['memory_mode']==mode) for r in uses):
            raise ValueError('duplicate episode or matched arm')
        candidate_report = report.get('reports',{}).get('candidate',{})
        status = 'unavailable' if target['state']=='unavailable' else candidate_report.get('status')
        if status not in {'passed','failed','unavailable'}: raise ValueError('executed target report required')
        uses.append({'source_candidate':source,'target_episode':target['episode'],'target_revision':target['revision'],
                     'target_candidate':target['candidate_digest'],'receipt_digest':canonical_hash(report),
                     'task_identity':task,'memory_mode':mode,'candidate_status':status,
                     'evaluation_seconds':target['evaluation_seconds'],'conditions':'caller declared; not randomized'})
        state['later_use']=uses
        return state

    def _validate_artifact(self, directory, state):
        artifact = state.get('artifact')
        if not artifact: return
        from .procedures import validate_policy, validate_procedure
        value = json.loads(path_in(directory / 'candidate', artifact['path']).read_text())
        if artifact['kind'] == 'policy': validate_policy(value)
        else:
            validate_procedure(value)
            if not self._sources_current(value['sources']): raise ValueError('procedure source evidence drift')
        if canonical_hash(value) != artifact['digest']: raise ValueError('artifact changed; register revised artifact')

    def _research_transition(self, directory, state, action, request, store, episode):
        from .investigation import investigation, execute, reduce_failure
        if action == 'analyze':
            if state['state'] not in {'observed','diagnosing','proposed','unavailable','rejected'}: raise ValueError('analysis requires an open diagnostic episode')
            from .methods import analyze
            results = list(state.get('method_results', []))
            if len(results) >= 32: raise ValueError('episode analysis limit reached')
            receipt = analyze(request['method'],request['input'])
            results.append(receipt);state['method_results'] = results
            return state
        if action == 'compose':
            if state['state'] not in {'observed','diagnosing','proposed','rejected','unavailable'}: raise ValueError('no composition during active candidate')
            from .capabilities import registry
            from .hypergraph import compose
            capabilities = registry(state['workspace'])
            identity = canonical_hash({'capabilities':capabilities,'available':request['available'], 'required':request['required'],
                                       'prerequisites':request.get('prerequisites',[]),'dependencies':request.get('dependencies',[]),
                                       'steps':state['limits']['composition_steps']})
            cache = directory / 'plans' / (identity + '.json')
            if cache.is_file(): plan = json.loads(cache.read_text())
            else:
                plan = compose(capabilities, request['available'], request['required'],
                               state['limits']['composition_steps'], request.get('prerequisites', []), request.get('dependencies', []))
                atomic_write_json(cache, plan)
            plan['cache_identity'] = identity
            state['composition'] = plan
            return state
        if action == 'policy_trial':
            if state['state'] != 'building' or state.get('artifact',{}).get('kind') != 'policy': raise ValueError('registered policy candidate required')
            self._validate_artifact(directory, state)
            from .procedures import rank_policy, REFLECTION_BASELINE
            policy = json.loads(path_in(directory / 'candidate',state['artifact']['path']).read_text())
            if policy.get('schema') == 'sips.policy.v2':
                from .policy_graph import run
                target = self.read(request['target_episode'])
                history = self.history(target['episode'])
                outcomes = {r['probe']: r['result']['status'] for r in target.get('investigation',{}).get('results',[]) if r.get('schema') == 'sips.probe-receipt.v1'}
                from .evidence_graph import project
                validity = project(self.directory(target['episode']), target)
                stale = [n for n in validity['affected'] if n in {'suite','environment'} or n.split(':')[0] in {'workspace','baseline','fixtures','evaluator'}]
                state['policy_trial'] = (dict(schema='sips.policy-execution.v2', status='inapplicable', stale_evidence=stale, activation='none', effectiveness='unknown')
                                         if stale else run(policy, outcomes, target['workspace'], time.time()))
                state['policy_trial']['target'] = {'episode':target['episode'], 'revision':target['revision'], 'event_digest':next(e.event_digest for e in history if e.revision == target['revision'])}
                state['policy_trial']['features_provenance'] = 'durable executed probe receipts'
                return state
            alternatives = request['alternatives']
            state['policy_trial'] = {'schema':'sips.policy-trial.v1', 'ranking':rank_policy(policy, alternatives),
                'baseline':'uniform-weight feature ranking', 'reflection_baseline':REFLECTION_BASELINE,
                'baseline_ranking':rank_policy({**policy,'weights':{k:1 for k in policy['weights']}}, alternatives),
                'features_provenance':'caller supplied; advisory only', 'effectiveness':'unknown', 'activation':'none'}
            return state
        if action == 'artifact':
            if state['state'] != 'building': raise ValueError('built artifact candidate required')
            kind, name = request.get('kind'), request.get('path', '')
            prefix = 'sips-artifacts/' + str(kind) + '/'
            if kind not in {'policy', 'procedure'} or '..' in Path(name).parts or not name.startswith(prefix) or not name.endswith('.json') or state['allowed_files'] != [name]:
                raise ValueError('artifact scope must be one declarative JSON file under sips-artifacts/kind/')
            value = json.loads(path_in(directory / 'candidate', name).read_text())
            state['artifact'] = {'kind': kind, 'path': name, 'digest': canonical_hash(value), 'effectiveness': 'unknown'}
            self._validate_artifact(directory, state)
            return state
        if action == 'add_counterexamples':
            if state['state'] not in {'building','rejected','unavailable'}: raise ValueError('counterexamples require an open candidate')
            self._frozen(directory, state)
            if not (directory / 'candidate').is_dir(): raise ValueError('candidate workspace required')
            additions = request.get('checks')
            if not isinstance(additions, list) or not additions or any(not isinstance(x,dict) or not x.get('kind') for x in additions): raise ValueError('nonempty checks required')
            suite = json.loads((directory / state.get('suite_file','suite.json')).read_text())
            old = state['suite_digest']
            suite.setdefault('counterexamples', []).extend(additions)
            state['suite_epoch'] = state.get('suite_epoch', 0) + 1
            name = 'suite-' + canonical_hash(suite) + '.json'
            atomic_write_json(directory / name, suite)
            state.update(suite_file=name, suite_digest=canonical_hash(suite), prior_suite_digest=old, state='building', effectiveness='unknown')
            state.pop('receipt', None)
            state.pop('receipt_digest', None)
            return state
        if state['state'] not in {'observed','diagnosing','proposed','unavailable','rejected'}: raise ValueError('diagnostic state required')
        if action == 'investigate':
            state['investigation'] = investigation(request.get('hypotheses'), request.get('probes', []))
            state.update(state='diagnosing', hypotheses=request['hypotheses'])
        elif action == 'conclude':
            outcome = request.get('outcome')
            if outcome not in {'insufficient_evidence','environment_unavailable','stop','intervention_selected'} or not request.get('rationale'): raise ValueError('diagnostic outcome and rationale required')
            state.setdefault('investigation', {})['outcome'] = outcome
            state['investigation']['rationale'] = request['rationale']
            state['state'] = 'canceled' if outcome == 'stop' else 'unavailable' if outcome == 'environment_unavailable' else 'diagnosing'
        else:
            self._frozen(directory, state)
            remaining = state['limits']['evaluation_seconds'] - state['evaluation_seconds']
            if remaining <= 0: return {**state, 'state':'unavailable', 'reason':'diagnostic budget exhausted'}
            inv = state.get('investigation')
            if not inv: raise ValueError('investigation required')
            probe = next((p for p in inv['probes'] if p['id'] == request.get('probe')), None)
            if not probe: raise ValueError('unknown probe')
            state.update(probe_running=probe['id'], probe_started_at=time.time())
            store.append('adaptation.probe_started', episode, {'state': json.loads(json.dumps(state))})
            started = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix='probe-', dir=directory) as td:
                    workspace = Path(td) / 'workspace'; shutil.copytree(directory / 'baseline', workspace)
                    if action == 'reduce':
                        result = reduce_failure(probe['check'], request['input'], workspace, directory / 'fixtures', state['limits']['command_timeout'], remaining)
                    else:
                        result = execute(probe, workspace, directory / 'fixtures', state['limits']['command_timeout'], remaining, state['environment'])
                self._frozen(directory, state)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                result = {'status':'unavailable','error':str(exc)}
            state['evaluation_seconds'] += time.monotonic() - started
            state.pop('probe_running'); state.pop('probe_started_at')
            inv['results'].append(result); probe['status'] = 'executed'
            state['evidence'].append({'kind':action,'identity':canonical_hash(result),'receipt':result})
            state['state'] = 'diagnosing'
        return state

    def _frozen(self, directory, state):
        if state['environment'] != {'python': sys.version, 'platform': sys.platform, 'interpreter': sys.executable}: raise ValueError('environment drift')
        if manifest(directory / 'baseline') != state['baseline_manifest']: raise ValueError('baseline drift')
        if manifest(directory / 'fixtures') != state['fixtures_manifest']: raise ValueError('fixture drift')
        if manifest(directory / 'evaluator') != state['evaluator_manifest']: raise ValueError('evaluator drift')
        if canonical_hash(json.loads((directory / state.get('suite_file', 'suite.json')).read_text())) != state['suite_digest']: raise ValueError('criteria drift')

    def _apply(self, directory, state, rollback):
        workspace = Path(state['workspace'])
        before = state['candidate_manifest'] if rollback else state['baseline_manifest']
        after = state['baseline_manifest'] if rollback else state['candidate_manifest']
        changed = [name for name in state['allowed_files'] if before.get(name) != after.get(name)]
        for name in changed:
            target = path_in(workspace, name)
            digest = file_identity(target) if target.is_file() else None
            if digest != before.get(name): raise ValueError('workspace conflict: ' + name)
        atomic_write_json(directory / 'activation-journal.json', {'rollback': rollback, 'files': changed})
        try:
            source = directory / ('baseline' if rollback else 'candidate')
            for name in changed: self._replace(path_in(workspace, name), source / name)
        except BaseException:
            self._recover_activation(directory, state); raise

    def _recover_activation(self, directory, state):
        journal = json.loads((directory / 'activation-journal.json').read_text())
        prior = directory / ('candidate' if journal['rollback'] else 'baseline')
        for name in journal['files']:
            target = path_in(Path(state['workspace']), name)
            digest = file_identity(target) if target.is_file() else None
            if digest not in {state['baseline_manifest'].get(name), state['candidate_manifest'].get(name)}:
                raise ValueError('recovery conflict: ' + name)
        for name in journal['files']: self._replace(path_in(Path(state['workspace']), name), prior / name)
        (directory / 'activation-journal.json').unlink()

    @staticmethod
    def _replace(target, source):
        if not source.exists():
            if target.exists(): target.unlink()
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.sips-', dir=target.parent); os.close(fd)
        try:
            shutil.copy2(source, temp); os.replace(temp, target)
        finally:
            if os.path.exists(temp): os.unlink(temp)
