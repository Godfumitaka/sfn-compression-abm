"""模型を呼ばず、指示37の範囲と未完了・他機械・GC使用の拒否を確認する。"""
from pathlib import Path
import copy
import json
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1] / 'report-results/control/動詞_クラウドの包み_2026-10-09/instruction33'
sys.path.insert(0, str(PACKAGE))
from prerequisites37 import accepted_structure_scope, gc_off, priority19_complete, sha, RECEIPT37
from run_structural import SERIAL, BIRTH
from run_extra_structural import EXTRA


def run(dest):
    dest = Path(dest)
    dest.mkdir(exist_ok=False)
    checked = []
    scope_path = PACKAGE / 'structural_scope37.json'
    scope = json.loads(scope_path.read_text())
    commit = scope['source_commit']
    accepted_structure_scope(scope_path, commit, SERIAL + EXTRA + BIRTH)
    checked.append('原結果0/0/1と169/46/19、GC4失敗の範囲を受け入れ')
    for flags in [[], ['--stage2-birth-gc-freeze', 'off']]:
        gc_off(flags)
        checked.append('GCoff許可:' + repr(flags))

    def rejects(name, call):
        try:
            call()
        except (AssertionError, KeyError, TypeError, FileNotFoundError):
            checked.append(name)
        else:
            raise AssertionError('拒否されなかった:' + name)

    for flags in [['--stage2-birth-gc-freeze', 'on'], ['--stage2-birth-gc-freeze=on'],
                  ['--stage2-birth-gc-freeze'], ['--stage2-birth-gc-freeze', 'off', '--stage2-birth-gc-freeze', 'off']]:
        rejects('GC使用/不完全/重複の拒否:' + repr(flags), lambda: gc_off(flags))
    normalized = copy.deepcopy(scope)
    for label in ('serial', 'extra', 'birth'):
        for prefix in ('result', 'log'):
            normalized[label][prefix + '_path'] = str(PACKAGE / normalized[label][prefix + '_path'])
    normalized['failure_summary_path'] = str(PACKAGE / normalized['failure_summary_path'])
    for key, value in [('passed', True), ('source_commit', 'bad'), ('failed_tests_preserved', 0)]:
        bad = copy.deepcopy(normalized)
        if key == 'failed_tests_preserved':
            bad['birth']['failed'] = value
        else:
            bad[key] = value
        path = dest / ('bad_scope_' + key + '.json')
        path.write_text(json.dumps(bad))
        rejects('原不合格や版の書換えの拒否:' + key, lambda: accepted_structure_scope(path, commit, SERIAL + EXTRA + BIRTH))
    # 以下は人工札だけ。実機械や模型の開始/完了札として使わない。
    def save(name, value):
        p = dest / (name + '.json')
        p.write_text(json.dumps(value))
        return p
    spec = save('synthetic_spec', dict(seed=3, source_commit='a'*40, machine='Google Cloud d3'))
    result = save('synthetic_result', dict(exit_code=0))
    marker = save('synthetic_marker', dict(completed_trials=1000, measurement_limit=1000,
                  configured_trial_count=5000, horizon=5000, full_5000_completed=False, source_commit='a'*40))
    start = save('synthetic_start', dict(machine_boot_sha256='synthetic_boot'))
    assignment = save('synthetic_assignment', dict(Claude_assignment_confirmed=True, all_assignments_finalized=True,
        machine='Google Cloud d3', published_commit='b'*40,
        assigned_19_cases=[dict(case_label='synthetic_only', arm='#19', seed=3, source_commit='a'*40, spec_sha256=sha(spec))]))
    entry = dict(case_label='synthetic_only')
    for label, path in [('spec', spec), ('result', result), ('partial_done', marker), ('start', start)]:
        entry[label + '_path'] = str(path)
        entry[label + '_sha256'] = sha(path)
    proof = dict(instruction=37, receipt_commit=RECEIPT37, machine='Google Cloud d3',
        machine_boot_sha256='synthetic_boot', normal_push_succeeded=True, published_commit='c'*40,
        assignment_path=str(assignment), assignment_sha256=sha(assignment), completed_cases=[entry])
    path = save('synthetic_priority', proof)
    priority19_complete(path, 'Google Cloud d3', 'synthetic_boot')
    checked.append('人工札だけで担当一覧・完了1000・同機械の接続を確認')
    rejects('他機械の完了拒否', lambda: priority19_complete(path, 'Google Cloud d2', 'synthetic_boot'))
    rejects('他boot拒否', lambda: priority19_complete(path, 'Google Cloud d3', 'other'))
    for label, patch in [('missing_seed', {'completed_cases': []}), ('unpublished', {'normal_push_succeeded': False})]:
        bad = {**proof, **patch}
        p = save('synthetic_bad_' + label, bad)
        rejects(label, lambda: priority19_complete(p, 'Google Cloud d3', 'synthetic_boot'))
    result.write_text(json.dumps(dict(exit_code=3)))
    proof['completed_cases'][0]['result_sha256'] = sha(result)
    path.write_text(json.dumps(proof))
    rejects('模型の原失敗3は完了扱いにしない', lambda: priority19_complete(path, 'Google Cloud d3', 'synthetic_boot'))
    marker.write_text(json.dumps(dict(completed_trials=900, measurement_limit=1000,
        configured_trial_count=5000, horizon=5000, full_5000_completed=False, source_commit='a'*40)))
    result.write_text(json.dumps(dict(exit_code=0)))
    proof['completed_cases'][0].update(partial_done_sha256=sha(marker), result_sha256=sha(result))
    path.write_text(json.dumps(proof))
    rejects('未完了900を1000へ補わない', lambda: priority19_complete(path, 'Google Cloud d3', 'synthetic_boot'))
    return dict(passed=True, count=len(checked), checks=checked, model_starts=0,
                actual_model_comparison=False, original_GC_tests_rerun=False, artificial_priority_is_not_production_evidence=True)
