from pathlib import Path
import json
import local_release


def test_explicit_stage_excludes_private_work_and_detects_drift(tmp_path):
    receipt = local_release.stage(tmp_path / 'stage')
    package = Path(receipt['package'])
    assert local_release.verify(receipt, package)['ok']
    assert (package / 'fixtures/benchmarks/policy_benchmark.py').is_file()
    assert (package / 'install.sh').is_file()
    assert not any(name.startswith(('docs/research/', '.hermes/', '.selfloop/', 'references/legacy/')) for name in receipt['files'])
    assert json.loads((package / '.codex-plugin/plugin.json').read_text())['version'] == local_release.VERSION
    (package / 'README.md').write_text('drift')
    assert local_release.verify(receipt, package)['mismatches'] == ['README.md']


def test_fresh_source_mcp_process():
    receipt = local_release.fresh_process(local_release.SOURCE)
    assert receipt['ok'], receipt
    assert 'homebase_adaptation_write' in receipt['tools']


def test_generated_projection_is_verified_not_blindly_ignored(tmp_path):
    receipt = local_release.stage(tmp_path / 'stage')
    package = Path(receipt['package'])
    projection = package / '.codex-plugin/migrated-command-skills/source-command-improve/SKILL.md'
    projection.parent.mkdir(parents=True)
    command = (package / 'commands/improve.md').read_text().split('---',2)
    description = next(line.partition(':')[2].strip() for line in command[1].splitlines() if line.startswith('description:'))
    projection.write_text('---\nname: "source-command-improve"\ndescription: '+json.dumps(description)+'\n---\n\n# source-command-improve\n\nUse this skill when the user asks to run the migrated source command `improve`.\n\n## Command Template\n\n'+command[2].strip()+'\n')
    assert local_release.verify(receipt,package)['ok']
    projection.write_text(projection.read_text()+'unexpected instruction\n')
    assert not local_release.verify(receipt,package)['ok']


def test_refresh_preserves_loaded_cache_and_model_settings(tmp_path,monkeypatch):
    import shutil
    from types import SimpleNamespace
    stage = tmp_path / 'stage'
    receipt = local_release.stage(stage)
    home = tmp_path / 'codex'; home.mkdir()
    (home/'config.toml').write_text('model = "user-model"\n[plugins."harness-self-improvement@harness-local".mcp_servers.sips-homebase]\nenabled_tools = ["homebase_status"]\n')
    cache = home/'plugins/cache/harness-local/harness-self-improvement'
    old = cache/'0.4.0'; old.mkdir(parents=True)
    (old/'loaded-hook.py').write_text('original hook')
    monkeypatch.setenv('CODEX_HOME',str(home))
    def install_command(*args,**kwargs):
        shutil.rmtree(old)
        shutil.copytree(receipt['package'],cache/receipt['version'])
        return SimpleNamespace(returncode=0,stdout='installed',stderr='')
    monkeypatch.setattr(local_release.subprocess,'run',install_command)
    monkeypatch.setattr(local_release,'fresh_process',lambda root:{'ok':True})
    result=local_release.install(stage)
    assert result['parity']['ok']
    assert (old/'loaded-hook.py').read_text() == 'original hook'
    config=(home/'config.toml').read_text()
    assert 'model = "user-model"' in config
    assert 'homebase_adaptation_write' in config
