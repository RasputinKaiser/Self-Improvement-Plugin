#!/usr/bin/env python3
"""Stage and verify an explicit local SIPS distribution; install only with --install."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from sips_runtime.events import atomic_write_json

SOURCE = Path(__file__).resolve().parents[1]
VERSION = json.loads((SOURCE / '.codex-plugin/plugin.json').read_text())['version']
DIRECTORIES = ['scripts', 'tests', 'commands', 'skills', 'hooks', 'agents', 'assets',
               '.codex-plugin', '.claude-plugin', 'Graph-Theory']
FILES = ['README.md', 'LICENSE', 'install.sh', 'pyproject.toml', '.mcp.json', 'EVAL.md',
         'references/eval_grader_golden.json', 'fixtures/benchmarks/policy_benchmark.py', 'docs/tool-factory-adaptation.md', 'docs/sips-05.md', 'docs/sips-06.md', 'docs/sips-07.md', 'docs/sips-08.md', 'docs/sips-09.md', 'docs/sips-in-run-improvement.md', 'docs/sips-visual-evidence.md']


def hash_files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def stage(destination):
    destination = Path(destination).resolve()
    if destination.exists(): raise ValueError('stage already exists; use a new directory')
    package = destination / 'plugins/harness-self-improvement'; package.mkdir(parents=True)
    names = set(FILES)
    for directory in DIRECTORIES:
        for p in (SOURCE / directory).rglob('*'):
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                names.add(str(p.relative_to(SOURCE)))
    # References are explicit distribution resources; archived implementations stay local.
    for p in (SOURCE / 'references').glob('*'):
        if p.is_file() and not p.is_symlink(): names.add(str(p.relative_to(SOURCE)))
    for name in sorted(names):
        src = SOURCE / name
        if not src.is_file(): raise ValueError('missing release file: ' + name)
        dst = package / name; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
    marketplace = json.loads((SOURCE / '.agents/plugins/marketplace.json').read_text())
    atomic_write_json(destination / '.agents/plugins/marketplace.json', marketplace)
    # Preserve source metadata for installed manifest checks; no recursive wrapper symlink.
    atomic_write_json(package / '.agents/plugins/marketplace.json', marketplace)
    receipt = {'schema': 'sips.local-release.v1', 'version': VERSION, 'source': str(SOURCE),
               'stage': str(destination), 'package': str(package), 'files': hash_files(package),
               'exclusions': ['research notes', 'transcripts', 'candidate workspaces', '.git', 'historical host implementations'],
               'current_task_discovery': 'unverified'}
    atomic_write_json(destination / 'release.json', receipt)
    return receipt


def verify(receipt, installed):
    actual = hash_files(installed)
    mismatch = [name for name,digest in receipt['files'].items() if actual.get(name) != digest]
    extras = sorted(set(actual) - set(receipt['files']))
    projections = {}
    for name in list(extras):
        parts = Path(name).parts
        if len(parts) != 4 or parts[:2] != ('.codex-plugin', 'migrated-command-skills') or parts[3] != 'SKILL.md': continue
        command = parts[2].removeprefix('source-command-')
        source = Path(installed) / 'commands' / (command + '.md')
        if not source.is_file(): continue
        chunks = source.read_text().split('---', 2)
        if len(chunks) != 3: continue
        description = next((line.partition(':')[2].strip().strip('\"').strip("'") for line in chunks[1].splitlines() if line.startswith('description:')), '')
        skill = 'source-command-' + command
        expected = ('---\nname: ' + json.dumps(skill) + '\ndescription: ' + json.dumps(description, ensure_ascii=False) + '\n---\n\n# ' + skill
                    + '\n\nUse this skill when the user asks to run the migrated source command `' + command
                    + '`.\n\n## Command Template\n\n' + chunks[2].strip() + '\n')
        if (Path(installed) / name).read_text() == expected:
            projections[name] = actual[name]; extras.remove(name)
    return {'ok': not mismatch and not extras, 'mismatches': mismatch, 'unexpected_files': extras, 'verified_host_projections': projections,
            'matched': len(receipt['files']) - len(mismatch)}


def install(stage_path):
    stage_path = Path(stage_path).resolve()
    receipt = json.loads((stage_path / 'release.json').read_text())
    if not verify(receipt, Path(receipt['package']))['ok']: raise ValueError('staged source drift')
    codex_home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    config = codex_home / 'config.toml'
    cache = codex_home / 'plugins/cache/harness-local/harness-self-improvement'
    backup = stage_path / 'recovery'; backup.mkdir(exist_ok=False)
    if config.exists(): shutil.copy2(config, backup / 'config.toml')
    # Preserve cached versions without changing their bytes.
    if cache.exists(): shutil.copytree(cache, backup / 'cache', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    atomic_write_json(backup / 'restore.json', {'config': str(config), 'cache': str(cache), 'backup': str(backup)})
    command = ['codex', '-c', 'marketplaces.harness-local.source=' + json.dumps(str(stage_path)),
               'plugin', 'add', 'harness-self-improvement@harness-local', '--json']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    finally:
        # Codex removes old versions on refresh; keep loaded task hook paths valid.
        for previous in (backup / 'cache').glob('*'):
            target = cache / previous.name
            if previous.is_dir() and not target.exists(): shutil.copytree(previous, target)

    receipt['install_command'] = command
    receipt['install_result'] = {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    if result.returncode:
        atomic_write_json(stage_path / 'install.json', receipt)
        raise ValueError('local plugin installation failed: ' + result.stderr[-1500:])
    installed = cache / receipt['version']
    receipt['installed'] = str(installed); receipt['parity'] = verify(receipt, installed)
    if not receipt['parity']['ok']:
        atomic_write_json(stage_path / 'install.json', receipt); raise ValueError('installed bytes differ from stage')
    # Preserve all user configuration; only extend the existing SIPS tool allowlist.
    if config.exists():
        import re
        text = (backup / "config.toml").read_text()
        header = '[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]'
        start = text.find(header)
        if start >= 0:
            end = text.find('\n[', start + len(header)); end = len(text) if end < 0 else end
            block = text[start:end]
            match = re.search(r'enabled_tools\s*=\s*\[.*?\]', block, re.S)
            if match:
                value = match.group(0)
                for name in ['homebase_adaptation_read', 'homebase_adaptation_write', 'homebase_method']:
                    if '"'+name+'"' not in value:
                        value = value.rstrip()[:-1].rstrip().rstrip(',') + ', "'+name+'"]'
                block = block[:match.start()] + value + block[match.end():]
                text = text[:start] + block + text[end:]
                try:
                    import tomllib
                except ImportError:
                    tomllib = None
                if tomllib is not None:
                    tomllib.loads(text)
                temp = config.with_name('config.toml.sips-release.tmp'); temp.write_text(text)
                os.chmod(temp, config.stat().st_mode); os.replace(temp, config)
    receipt['configuration_backup'] = str(backup / 'config.toml')
    receipt['fresh_process'] = fresh_process(installed)
    atomic_write_json(stage_path / 'install.json', receipt)
    return receipt


def fresh_process(installed):
    requests = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'sips-local-release','version':VERSION}}},
        {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
        {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'homebase_status','arguments':{'root':str(installed)}}}]
    wire = b''
    for request in requests:
        body=json.dumps(request).encode(); wire += f'Content-Length: {len(body)}\r\n\r\n'.encode()+body
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    result=subprocess.run([sys.executable,str(installed/'scripts/harness_homebase_mcp.py')],input=wire,capture_output=True,cwd=installed,env=env,timeout=30)
    raw=result.stdout; responses=[]
    while raw:
        header,sep,rest=raw.partition(b'\r\n\r\n')
        if not sep: break
        length=int(header.split(b':',1)[1].strip());responses.append(json.loads(rest[:length]));raw=rest[length:]
    by_id={r.get('id'):r for r in responses}
    tools=by_id.get(2,{}).get('result',{}).get('tools',[])
    names={t['name'] for t in tools}
    status_result = by_id.get(3,{}).get('result',{})
    status = status_result.get('structuredContent',{})
    ok=(result.returncode==0 and {'homebase_adaptation_read','homebase_adaptation_write','homebase_method'}<=names
        and not status_result.get('isError') and status.get('manifest',{}).get('version') == VERSION
        and status.get('plugin_root') == str(installed) and status.get('status') == 'inspected')
    return {'ok':ok,'exit':result.returncode,'tools':sorted(names),'responses':responses,'stderr':result.stderr.decode()[-2000:],
            'proof':'Fresh direct MCP process from installed files; current desktop task discovery is separate.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage');parser.add_argument('--install');parser.add_argument('--verify');parser.add_argument('--installed')
    args=parser.parse_args()
    if args.stage: result=stage(args.stage)
    elif args.install: result=install(args.install)
    elif args.verify and args.installed: result=verify(json.loads(Path(args.verify).read_text()),Path(args.installed))
    else: parser.error('choose --stage DIR, --install DIR, or --verify RECEIPT --installed DIR')
    print(json.dumps(result,indent=2))
    return 0 if result.get('ok',True) and result.get('fresh_process',{}).get('ok',True) else 1


if __name__=='__main__':
    raise SystemExit(main())
