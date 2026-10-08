"""C*の確率記録の書き出しだけを検査し、計算用辞書と旧いバイトを保つ。"""
from pathlib import Path
import copy
import io
import json
import sys

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "tools"), str(Path(__file__).resolve().parents[1])]
import smeshared


def test_mixed_none_name_keys_write_without_changing_probabilities(monkeypatch):
    record = {"kind": "sme_result", "probabilities": {"r": {None: .25, "fold": .75}}}
    original = copy.deepcopy(record)
    stream = io.StringIO()
    monkeypatch.setattr(smeshared, "LOG", {"f": stream})
    monkeypatch.setattr(smeshared, "_diagnosing", lambda: False)
    smeshared._log(record)
    assert json.loads(stream.getvalue())["probabilities"]["r"] == {"null": .25, "fold": .75}
    assert record == original


def test_existing_record_bytes_are_unchanged():
    record = {"kind": "sme_result", "args": [(1, 2), (3, 4)], "counts": {3: 7, 1: 9}}
    assert json.dumps(smeshared._record_json_keys(record), ensure_ascii=False, sort_keys=True) == json.dumps(record, ensure_ascii=False, sort_keys=True)


def test_none_and_literal_null_collision_stops():
    with pytest.raises(ValueError, match="衝突"):
        smeshared._record_json_keys({None: .25, "null": .75})
