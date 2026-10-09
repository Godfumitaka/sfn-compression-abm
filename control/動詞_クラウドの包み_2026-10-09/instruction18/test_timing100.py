"""観察の構造だけを確かめる。模型は起動しない。"""
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent/'tools'))
from timing100_observer import observe_timing


class Ledger:
    def __init__(self): self.rows = []
    def append(self, row):
        self.rows.append(row)
        return len(self.rows)


def test_calls_native_once_preserves_rows_and_restores_entry(tmp_path):
    ledger = Ledger()
    native = ledger.append
    rows = [{'prediction_order': n, 'unchanged': {'n': n}} for n in range(201)]
    with observe_timing(tmp_path, ledger):
        for n, row in enumerate(rows): assert ledger.append(row) == n+1
    assert ledger.append == native and 'append' not in vars(ledger)
    assert ledger.rows == rows and all(a is b for a, b in zip(ledger.rows, rows))
    values = [json.loads(x) for x in (tmp_path/'timing100.jsonl').read_text().splitlines()]
    assert [v['completed_trials'] for v in values] == [100, 200]
    assert all(v['configured_trial_count'] == v['horizon'] == 5000 for v in values)


def test_failure_does_not_add_a_completed_record_and_restores_instance_entry(tmp_path):
    ledger = Ledger()
    def fail(row): raise ValueError('原入口の失敗')
    ledger.append = fail
    with pytest.raises(ValueError), observe_timing(tmp_path, ledger):
        ledger.append({'prediction_order': 0})
    assert ledger.append is fail and not ledger.rows
    assert (tmp_path/'timing100.jsonl').read_text() == ''
