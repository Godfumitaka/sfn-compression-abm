"""検査台本が欠けたsourceや未採点行への採点欄混入を取り逃さない。"""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('coll8_source_check',
    Path(__file__).resolve().parents[1] / 'tools/v311c_checks/coll8_source_check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

INITIAL = {'kind': 'v310be', 'trial': 0, 'x': 'no_m1', 'R_B': 0.0,
           'R_E': 0.0, 'C_end': 210, 'zero_release': []}
SCORED = {'kind': 'v310be', 'trial': 1, 'source': '世界', 'K': 0, 'r': 0,
          'cands': [[None, 0, 0, 0, 0, {}]]}


def test_unscored_and_zero_valued_scoring_are_distinct():
    assert module.validate_source(INITIAL, '世界') == 'initial_unscored'
    assert module.validate_source(SCORED, '世界') == 'scored'
    assert module.validate_source({**SCORED, 'source': '報告'}, '報告') == 'scored'


@pytest.mark.parametrize('change', [{'source': None}, {'source': '世界'}, {'K': 0},
    {'r': 0}, {'cands': []}, {'R_B': 1}, {'R_E': 1}, {'trial': 1},
    {'zero_release': [{}]}, {'unknown': 0}])
def test_unscored_record_contamination_is_rejected(change):
    with pytest.raises(ValueError):module.validate_source({**INITIAL, **change}, '世界')


@pytest.mark.parametrize('missing', ['source', 'K', 'r', 'cands'])
def test_scored_record_missing_field_is_rejected(missing):
    row = dict(SCORED);row.pop(missing)
    with pytest.raises(ValueError):module.validate_source(row, '世界')


def test_world_and_report_sources_cannot_be_mixed():
    with pytest.raises(ValueError):module.validate_source(SCORED, '報告')


def test_known_m1_failure_has_no_scoring_fields():
    empty = {'kind': 'v310be', 'trial': 3, 'source': '世界', 'x': None, 'R_E': 0}
    assert module.validate_source(empty, '世界') == 'm1_unscored'
    with pytest.raises(ValueError):module.validate_source({**empty, 'K': 0}, '世界')
