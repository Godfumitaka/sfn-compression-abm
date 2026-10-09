"""試験回答・保存状態・TIMEの比較境界だけを非模型の小さな原記録で検査する。"""
from pathlib import Path
import gzip
import pytest
from compare_probe100 import compare_recordings, required_paths


def write(folder, relative, value):
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.gz':
        with gzip.open(path, 'wb') as out:
            out.write(value)
    else:
        path.write_bytes(value)


def recordings(tmp_path):
    pair = [tmp_path / 'off', tmp_path / 'on']
    for folder in pair:
        for relative in required_paths():
            write(folder, relative, b'{"value":1}\n')
    return pair


def test_probe_answer_mismatch_is_failure(tmp_path):
    pair = recordings(tmp_path)
    path = next(p for p in required_paths() if p.name.endswith('.probe.jsonl'))
    write(pair[1], path, b'{"value":2}\n')
    result = compare_recordings(*pair)
    assert not result['passed'] and result['mismatching_files'] == 1
    assert result['probe_rows_excluded'] == 0


def test_saved_probe_state_mismatch_is_failure(tmp_path):
    pair = recordings(tmp_path)
    path = next(p for p in required_paths() if p.name.endswith('.sme.states.jsonl.gz'))
    write(pair[1], path, b'{"value":1}\n{"probe":true}\n')
    result = compare_recordings(*pair)
    assert not result['passed'] and result['mismatching_files'] == 1


def test_only_stage2_time_values_are_ignored(tmp_path):
    pair = recordings(tmp_path)
    path = Path('stage2/seed001.jsonl')
    write(pair[0], path, b'{"seconds":1.3,"answer":1}\n')
    write(pair[1], path, b'{"seconds":23.41,"answer":1}\n')
    assert compare_recordings(*pair)['passed']
    write(pair[1], path, b'{"seconds":23.41,"answer":2}\n')
    assert not compare_recordings(*pair)['passed']
    write(pair[1], path, b'{"seconds":23.41,"answer":1}\n')
    write(pair[0], Path('side/time.jsonl'), b'{"seconds":1}\n')
    write(pair[1], Path('side/time.jsonl'), b'{"seconds":2}\n')
    assert not compare_recordings(*pair)['passed']


def test_missing_probe_record_is_not_a_pass(tmp_path):
    pair = recordings(tmp_path)
    extra = [tmp_path / 'missing_off', tmp_path / 'missing_on']
    for folder in extra:
        for relative in required_paths():
            if relative.name.endswith('.probe.jsonl'):
                continue
            write(folder, relative, b'{"value":1}\n')
    with pytest.raises(AssertionError):
        compare_recordings(*extra)
