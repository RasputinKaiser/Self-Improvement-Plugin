import json

import pytest
import self_correct


@pytest.mark.parametrize('score', [None, '', 'bad', float('nan'), float('inf'), True])
def test_unavailable_latest_score_does_not_fabricate_regression(tmp_path, score):
    path = tmp_path / 'results.jsonl'
    runs = [{'caseId': 'case', 'score': s, 'finishedAtISO': str(i)}
            for i, s in enumerate([1, 1, 1, score])]
    path.write_text('\n'.join(map(json.dumps, runs)))
    assert self_correct.find_eval_regressions(path) == []


def test_valid_zero_still_reports_regression(tmp_path):
    path = tmp_path / 'results.jsonl'
    runs = [{'caseId': 'case', 'score': s, 'finishedAtISO': str(i)}
            for i, s in enumerate([1, 1, 1, 0])]
    path.write_text('\n'.join(map(json.dumps, runs)))
    result = self_correct.find_eval_regressions(path)
    assert len(result) == 1
    assert result[0]['latest'] == 0


def test_missing_history_does_not_count_toward_minimum_baseline(tmp_path):
    path = tmp_path / 'results.jsonl'
    runs = [{'caseId': 'case', 'score': s, 'finishedAtISO': str(i)}
            for i, s in enumerate([None, 1, 1, 0])]
    path.write_text('\n'.join(map(json.dumps, runs)))
    assert self_correct.find_eval_regressions(path) == []
