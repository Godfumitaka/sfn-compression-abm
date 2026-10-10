"""指示23の自然終了と同じ比較受付待ちだけを保存する。"""
from pathlib import Path
import datetime
import json

p = Path(__file__).resolve().parent.parent
h = p / 'instruction23/off100_completed_01'
h.mkdir(exist_ok=False)
now = datetime.datetime.now().astimezone().isoformat()
case = p / 'instruction22/candidate_off100_01'
s = json.loads((case / 'status.json').read_text())
assert s['state'] == 'completed' and s['exit_code'] == 0 and s['completed_trials'] == 100 and s['protected_unchanged']
for name in ['status.json', 'protected_before.json', 'protected_after.json', 'before_start.json']:
    (h / ('candidate_off100_' + name)).write_bytes((case / name).read_bytes())
assert (case / 'protected_before.json').read_bytes() == (case / 'protected_after.json').read_bytes()
log = p / 'instruction23/off100_comparison_admission_04.log'
raw = log.read_text()
assert 'スワップが直近 10 分で増えた' in raw
assert not (p / 'instruction22/candidate_off100_comparison_03.json').exists()
warning = dict(at_jst=now, owner='intervention-instruction23-verb-off100-comparison04',
    exec_session_id=97587, reservation_gb=0.3, state='admission_wait', comparison_started=False,
    resource_reference=str(p / 'instruction23/off100_comparison_before_admission_04.json'),
    admission_log=str(log), warning_original=raw, duplicate_registration=False,
    reservation_changed=False, policy_changed=False)
(h / 'admission_warning_01.json').write_text(json.dumps(warning, ensure_ascii=False, indent=2) + '\n')
model = dict(at_jst=now, natural_end=s,
    original_protected_file_count=sum(len(v) for v in json.loads((case / 'protected_after.json').read_text()).values()),
    comparison_passed=False, existing_B6_running=True, desktop_records_received=False,
    formal_material=False, production_changed=False)
(h / 'progress_01.json').write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n')
b = h / 'state_before'
b.mkdir()
for n in [12, 13, 14, 17, 20, 21, 22, 23]:
    f = p / f'instruction{n}_status.json'
    (b / f.name).write_bytes(f.read_bytes())
    d = json.loads(f.read_text())
    if n in [12, 13, 14, 17, 20, 21]:
        d.update(state='B5_a_passed_B6_structure39_passed_existing_off200_running',
            running_labels=['B6_off_on200_candidate03'], queued_labels=[])
    if n == 22:
        d.update(state='seed7_assert_identified_structure40_passed_candidate_off100_completed_comparison_admission_wait',
            running_labels=[], queued_labels=['candidate_off100_comparison_03'], off100_completed=True,
            off100_runtime={k:v for k,v in s.items() if k != 'command'},
            off100_comparison_session_id=97587, off100_comparison_reservation_gb=.3,
            off100_comparison_entry=str(p / 'instruction22/compare_candidate_off100_03.py'),
            off100_comparison_result=str(p / 'instruction22/candidate_off100_comparison_03.json'),
            off100_comparison_passed=False)
    if n == 23:
        d.update(state='candidate_off100_completed_reader_corrections_saved_comparison_admission_wait_B6_running',
            off100_completed=True, off100_comparison_session_id=97587, off100_comparison_reservation_gb=.3,
            off100_comparison_result=str(p / 'instruction22/candidate_off100_comparison_03.json'),
            additional_jobs_registered=3, reader_failures_before_actual_comparison_preserved=True,
            deferred_on_entry=str(p / 'instruction22/launch_candidate_on200_02.py'), desktop_records_received=False,
            next_steps=str(p / 'instruction23/NEXT_SAVED_STEPS_02.md'))
    d.update(last_update_at_jst=now, completed=False, progress_evidence=str(h))
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(at_jst=now, saved_state_updates=8, off_model_completed=True,
    comparison_pending=True), ensure_ascii=False))
