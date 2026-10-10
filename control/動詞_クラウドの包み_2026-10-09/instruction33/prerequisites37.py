"""指示37。GC不使用の構造範囲と、担当#19終了の原証拠を読むだけ。"""
from pathlib import Path
import hashlib
import json
import re

RECEIPT37 = '8e7bfbd30b8c973a446e798d4229efe93f8c9520'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_file(parent, entry, prefix):
    path = Path(entry[prefix + '_path'])
    if not path.is_absolute():
        path = Path(parent) / path
    assert sha(path) == entry[prefix + '_sha256'], '原証拠のSHA不一致'
    return path


def gc_off(flags):
    found = [i for i, value in enumerate(flags) if value == '--stage2-birth-gc-freeze']
    assert len(found) <= 1
    assert all(i + 1 < len(flags) and flags[i + 1] == 'off' for i in found), 'GC旗は指示37で保留不使用'
    assert not any(value.startswith('--stage2-birth-gc-freeze=') for value in flags)


def accepted_structure_scope(path, commit, required_files):
    path = Path(path)
    scope = read(path)
    assert scope['instruction'] == 37 and scope['receipt_commit'] == RECEIPT37
    assert scope['passed'] is False and scope['all_structural_tests_passed'] is False
    assert scope['gc_off_scope_accepted'] is True and scope['gc_flag_status'] == 'held_unused'
    assert scope['model_starts'] == 0 and scope['source_commit'] == commit
    checked = []
    for label, expected in (('serial', (0, 169, 0)), ('extra', (0, 46, 0)), ('birth', (1, 19, 4))):
        entry = scope[label]
        raw = read(checked_file(path.parent, entry, 'result'))
        log = checked_file(path.parent, entry, 'log').read_text()
        assert raw['source_commit'] == commit and raw['model_starts'] == 0
        assert (raw['exit_code'], entry['passed'], entry['failed']) == expected
        assert re.search(r'\b' + str(expected[1]) + r' passed\b', log)
        if expected[2]:
            assert '4 failed' in log and 'test_birth_gc_freeze_instruction35.py:40' in log
        else:
            assert not re.search(r'\d+ failed', log)
        checked.extend(raw['files'])
    summary = read(checked_file(path.parent, scope, 'failure_summary'))
    assert summary['structural_tests_passed'] is False and summary['source_commit'] == commit
    failures = summary['birth']['failures']
    assert len(failures) == 4
    assert {(f['hu'], f['workers']) for f in failures} == {(False, 1), (False, 4), (True, 1), (True, 4)}
    assert all(f['assert_line'] == 40 and f['expected'] == 0 and f['actual'] == 375
               and f['native_comparison_started'] is False for f in failures)
    assert {Path(f).name for f in required_files}.issubset({Path(f).name for f in checked})
    assert any(Path(f).name == 'test_compare100.py' for f in checked)
    return scope


def priority19_complete(path, machine, boot):
    """見込み時刻・空欄・他機械の完了を開始許可へ置き換えない。"""
    path = Path(path)
    proof = read(path)
    assert proof['instruction'] == 37 and proof['receipt_commit'] == RECEIPT37
    assert proof['machine'] == machine and proof['machine_boot_sha256'] == boot
    assert proof['normal_push_succeeded'] is True and len(proof['published_commit']) == 40
    assigned = read(checked_file(path.parent, proof, 'assignment'))
    assert assigned['Claude_assignment_confirmed'] is True and assigned['all_assignments_finalized'] is True
    assert assigned['machine'] == machine and len(assigned['published_commit']) == 40
    rows = assigned['assigned_19_cases']
    assert rows and len({r['case_label'] for r in rows}) == len(rows)
    completed = {row['case_label']: row for row in proof['completed_cases']}
    assert len(completed) == len(proof['completed_cases']) and set(completed) == {r['case_label'] for r in rows}
    for row in rows:
        assert row['arm'] == '#19' and type(row['seed']) is int and 1 <= row['seed'] <= 10
        entry = completed[row['case_label']]
        spec = read(checked_file(path.parent, entry, 'spec'))
        result = read(checked_file(path.parent, entry, 'result'))
        marker = read(checked_file(path.parent, entry, 'partial_done'))
        start = read(checked_file(path.parent, entry, 'start'))
        assert row['spec_sha256'] == entry['spec_sha256']
        assert spec['seed'] == row['seed'] and spec['source_commit'] == row['source_commit']
        assert spec['machine'] == machine and result['exit_code'] == 0
        assert start['machine_boot_sha256'] == boot
        assert marker['completed_trials'] == marker['measurement_limit'] == 1000
        assert marker['configured_trial_count'] == marker['horizon'] == 5000
        assert marker['full_5000_completed'] is False and marker['source_commit'] == spec['source_commit']
    return proof
