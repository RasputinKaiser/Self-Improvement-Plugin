from __future__ import annotations

import self_correct


def test_find_untested_scripts_recognizes_pytest_and_transitive_coverage(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    tests = tmp_path / "tests"
    scripts.mkdir()
    tests.mkdir()

    (scripts / "run_tests.py").write_text("SUITES = {}\n", encoding="utf-8")
    (scripts / "entry_helper.py").write_text("import covered_helper\n", encoding="utf-8")
    (scripts / "covered_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (scripts / "path_only_validator.py").write_text("VALUE = 2\n", encoding="utf-8")
    (scripts / "uncovered_helper.py").write_text("pass\n", encoding="utf-8")
    (tests / "test_a_entry_helper.py").write_text(
        'HELPER = "entry_helper.py"\nVALIDATOR = "scripts/path_only_validator.py"\n',
        encoding="utf-8",
    )
    (tests / "test_z_unrelated.py").write_text("VALUE = 3\n", encoding="utf-8")

    monkeypatch.setattr(self_correct, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(self_correct, "TESTS_DIR", tests)

    assert self_correct.find_untested_scripts() == ["uncovered_helper.py"]
