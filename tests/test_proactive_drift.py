from __future__ import annotations

import proactive_drift
import self_correct


def test_untested_scripts_reuses_canonical_coverage_signal(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    tests = tmp_path / "tests"
    scripts.mkdir()
    tests.mkdir()

    (scripts / "run_tests.py").write_text("SUITES = {}\n", encoding="utf-8")
    (scripts / "entry_helper.py").write_text("import covered_helper\n", encoding="utf-8")
    (scripts / "covered_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (scripts / "uncovered_helper.py").write_text("pass\n", encoding="utf-8")
    (tests / "test_entry_helper.py").write_text(
        'HELPER = "entry_helper.py"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(proactive_drift, "NCODE_DIR", tmp_path)
    monkeypatch.setattr(proactive_drift, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(self_correct, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(self_correct, "TESTS_DIR", tests)

    assert proactive_drift.untested_scripts() == ["uncovered_helper.py"]
