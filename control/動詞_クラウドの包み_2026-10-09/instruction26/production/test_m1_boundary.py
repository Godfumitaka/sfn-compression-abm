"""指示20の観察境界。模型は起動せず、適用外と原記録必須の境界を検査する。"""
from pathlib import Path
import gzip
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
from checkpoint_observer import m1_checkpoint


def test_without_attention_and_stage2_records_not_applicable(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    dest = tmp_path / 'checkpoint'; dest.mkdir()
    m1_checkpoint(out, dest, 500, attention_enabled=False, stage2_enabled=False)
    record = json.loads((dest / 'm1_at_trial500.json').read_text())
    assert record['applicable'] is False and record['automatic_stop'] is False
    assert 'definitions_at_most_one' not in record and 'fraction' not in record
    assert not (out / 'attention').exists()


@pytest.mark.parametrize('attention,stage2', [(True, False), (True, True), (False, True)])
def test_required_attention_file_cannot_be_waived(tmp_path, attention, stage2):
    with pytest.raises(AssertionError, match='原注意'):
        m1_checkpoint(tmp_path, tmp_path, 500, attention_enabled=attention, stage2_enabled=stage2)
    assert not (tmp_path / 'm1_at_trial500.json').exists()


def test_attention_m1_uses_all_301_original_rows(tmp_path):
    out = tmp_path / 'output'; path = out / 'attention/cell/seed001.jsonl.gz'
    path.parent.mkdir(parents=True)
    with gzip.open(path, 'wt') as stream:
        for i in range(200, 501):
            stream.write(json.dumps({'trial': i, 'definitions': 1 if i < 480 else 2}) + '\n')
    dest = tmp_path / 'checkpoint'; dest.mkdir()
    m1_checkpoint(out, dest, 500, attention_enabled=True, stage2_enabled=True)
    record = json.loads((dest / 'm1_at_trial500.json').read_text())
    assert record['trials'] == 301 and record['definitions_at_most_one'] == 280
    assert record['claude_confirmation_required'] and not record['automatic_stop']
