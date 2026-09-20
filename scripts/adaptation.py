#!/usr/bin/env python3
"""Thin CLI for the durable local adaptation controller (no automatic activation)."""
import argparse
import json
from pathlib import Path
from sips_runtime.adaptation import AdaptationController, INTERVENTIONS
from sips_runtime.canonical import canonical_hash


def observe(case, run, analysis):
    request = {'workspace': case.get('workspace', str(Path.cwd())), 'task': case.get('prompt') or case.get('id', 'Correction'),
               'allowed_files': case.get('allowed_files', []), 'context_files': case.get('context_files', []),
               'suite': case.get('suite', {}), 'fixtures': case.get('fixtures', {}),
               'evidence': [{'case': case, 'run': run, 'analysis': analysis}],
               'expected_revision': 0, 'idempotency_key': canonical_hash({'case': case, 'run': run})}
    return AdaptationController().write('observe', request)['episode']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['show', 'observe', 'diagnose', 'propose', 'build', 'evaluate', 'activate', 'rollback', 'recover', 'cancel', 'investigate', 'probe', 'reduce', 'conclude', 'add_counterexamples', 'artifact', 'compose', 'policy_trial', 'analyze', 'advance', 'link_outcome', 'notice'])
    parser.add_argument('--request-json', default='{}')
    parser.add_argument('--request-file')
    parser.add_argument('--episode'); parser.add_argument('--view', default='status', choices=['status','events','diff','evidence','receipt','investigation','lineage','procedures','next','outcomes','dependencies','opportunities','visual'])
    args = parser.parse_args()
    try:
        controller = AdaptationController()
        request = json.loads(Path(args.request_file).read_text() if args.request_file else args.request_json)
        if args.episode: request['episode'] = args.episode
        result = controller.read(request['episode'], args.view, request.get('query',''), request.get('context')) if args.action == 'show' else controller.write(args.action, request)
        print(json.dumps(result, indent=2)); return 0
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
