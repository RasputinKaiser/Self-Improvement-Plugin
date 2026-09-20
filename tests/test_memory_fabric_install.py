from __future__ import annotations

from memory_fabric_install_copy import copy_source


def test_cache_copy_excludes_plugin_wrapper_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "payload.txt").write_text("ready\n", encoding="utf-8")
    (source / "wrapper").symlink_to(source, target_is_directory=True)
    target = tmp_path / "cache" / "plugin" / "1.0.0"

    copy_source(source, target)

    assert (target / "payload.txt").read_text(encoding="utf-8") == "ready\n"
    assert not (target / "wrapper").exists()


def test_release_workspaces_are_not_copied_or_fingerprinted(tmp_path):
    from memory_fabric_install_fingerprint import fingerprint_files
    source=tmp_path/'source';source.mkdir()
    (source/'script.py').write_text('print("public")')
    private=source/'.local-release'/'trial';private.mkdir(parents=True)
    (private/'receipt.json').write_text('private trial')
    target=tmp_path/'cache'
    copy_source(source,target)
    assert (target/'script.py').is_file()
    assert not (target/'.local-release').exists()
    assert [p.relative_to(source).as_posix() for p in fingerprint_files(source)]==['script.py']
