"""同じ受付・模型の資源監督を指示11に合わせる。模型を起動しない。"""
from pathlib import Path
from types import SimpleNamespace
import json, os, signal, sys, time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT.parent/'codex_sme_time_evict_2026-10-06'),
               str(ROOT.parent/'codex_logp_main_2026-10-06')]
from common_01 import conditions, now, save, ps
from cpu_guard_05 import cpu_reading

CASE = ROOT/'profile1740_01'
started = json.loads((CASE/'started.json').read_text())
PID = started['runner_pid']
CLAIM = json.loads((ROOT/'claim.json').read_text())['claim_pid']
assert PID == 65065 and CLAIM == 64925
assert (ROOT.parent/'codex_cstar_pending_2026-10-06/instruction11_received_01.json').exists()
assert not (ROOT/'guard_instruction11_started.json').exists(), '監督も二重起動しない'

def signal_own(sig, row):
    assert row['pgid'] == PID and row['ppid'] == 64929
    assert str(ROOT/'observe_cstar_01.py') in row['command']
    assert str(CASE/'native_command.json') in row['command']
    assert os.getpgid(PID) == PID
    os.killpg(PID, sig)

def append(name, value):
    with (ROOT/name).open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False)+'\n')

save(ROOT/'guard_instruction11_started.json', dict(at=now(), pid=os.getpid(),
     runner_pid=PID, claim_pid=CLAIM, model_not_restarted=True,
     policy='他係だけでは保留しない。機械全体8本・空き・熱・スワップは維持',
     legacy_controller_pause_seconds_is_upper_bound=True, sampling_seconds=2))
last = None
sampled_hold = 0.0
samples = 0
events = 0
try:
    while True:
        rows = ps()
        row = rows.get(PID)
        if row is None or 'Z' in row['stat']:
            break
        assert row['pgid'] == PID and row['ppid'] == 64929
        assert str(ROOT/'observe_cstar_01.py') in row['command']
        assert str(CASE/'native_command.json') in row['command']
        safe = conditions()
        cpu = cpu_reading([{'child': SimpleNamespace(pid=PID)}])
        stopped = 'T' in row['stat']
        reasons = []
        if safe['free_bytes'] < 18.5*2**30: reasons.append('空き18.5GiB未満')
        if safe['swap_grew']: reasons.append('スワップ増加')
        if safe['thermal_warning']: reasons.append('熱の警告')
        # 停止中の自分を含め、再開後の一本分も上限に含める。
        required_slots = max(1, cpu['own_compute_count'])
        if cpu['external_count'] + required_slots > 8: reasons.append('機械全体8本の上限')
        t = time.monotonic()
        if last is not None and last[1]: sampled_hold += t-last[0]
        last = (t, stopped)
        sample = dict(at=now(), runner_pid=PID, state=row['stat'], stopped=stopped,
                      resources=safe, external_model_count=cpu['external_count'],
                      own_model_count=cpu['own_compute_count'],
                      total_model_count=cpu['total_compute_count'], hold_reasons=reasons)
        append('guard_instruction11_resources.jsonl', sample)
        samples += 1
        if reasons and not stopped:
            signal_own(signal.SIGSTOP, row)
            append('guard_instruction11_events.jsonl', dict(at=now(), action='SIGSTOP', reasons=reasons))
            events += 1
        elif stopped and not reasons and safe['free_bytes'] >= 20*2**30:
            signal_own(signal.SIGCONT, row)
            append('guard_instruction11_events.jsonl', dict(at=now(), action='SIGCONT',
                   reason='指示11。同じ模型の続き。他係だけでは保留しない',
                   external_model_count=cpu['external_count']))
            events += 1
        time.sleep(2)
    save(ROOT/'guard_instruction11_complete.json', dict(at=now(), runner_pid=PID,
         model_not_restarted=True, samples=samples, events=events,
         sampled_stopped_seconds=sampled_hold, sampling_seconds=2,
         note='起動後の実際のT状態の標本。旧監督のpaused_secondsは別記の上限値'))
except Exception as exc:
    save(ROOT/'guard_instruction11_STOP.json', dict(at=now(), reason=str(exc),
         runner_pid=PID, model_not_restarted=True))
    raise
