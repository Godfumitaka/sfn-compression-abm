"""指示24でcProfileの種41待ちを外す。二模型は指示23の全四本完走後だけ再開する。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
STAGE = ROOT.parent
PAUSE_ROOT = STAGE / 'instruction23_pause_speed_gate'
spec = importlib.util.spec_from_file_location('unchanged_gate_guard', STAGE / 'instruction19_speed_gate/gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
PROFILE_PID = 63553
PAIR = (49468, 59619)
CASES = {
    41: (STAGE / 'instruction16_calibration_preview_seed41/birth_hu_on', 95408),
    42: (STAGE / 'instruction18_calibration/w2_seed042', 9073),
    43: (STAGE / 'instruction20_calibration_mac4344/w2_seed043', 47180),
    44: (STAGE / 'instruction20_calibration_mac4344/w2_seed044', 47210),
}


def write(name, data):
    p = ROOT / name
    tmp = Path(str(p) + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)


def alive(ps, pid):
    return pid in ps and 'Z' not in ps[pid][1]


def native_complete(root, receipt, ps):
    # 実完走の原記録を全部確認。引き継いだ受付の終了コードは作らない。
    names = ('measurement.json', 'worker_finished.json', 'worker_pid.json', 'run.log')
    if not all((root / n).exists() for n in names) or alive(ps, receipt):
        return False
    measure = json.loads((root / names[0]).read_text())
    finished = json.loads((root / names[1]).read_text())
    worker = json.loads((root / names[2]).read_text())
    if (measure.get('trials') != 1740 or not measure.get('native_loop_returned')
            or measure.get('pid') != worker.get('pid') or finished.get('pid') != worker.get('pid')
            or alive(ps, worker['pid'])):
        return False
    with (root / 'run.log').open('rb') as stream:
        stream.seek(max(0, (root / 'run.log').stat().st_size - 65536))
        return b'ALLDONE' in stream.read()


def identity(ps, pid, saved, paused=True):
    if not alive(ps, pid) or ps[pid][0] != saved[0] or ps[pid][4] != saved[4]:
        raise RuntimeError(('既存過程の実親子又は命令が違う', pid))
    if paused and 'T' not in ps[pid][1]:
        raise RuntimeError(('保留中の既存過程が一時停止状態でない', pid))


def fixed():
    G.source_ok()
    manifest = json.loads((PAUSE_ROOT / 'immutable_manifest.json').read_text())
    for filename, digest in manifest.items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('固定した道具・命令・停止記録が変わった', filename))


def warnings(m):
    return (not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
        or m['model_children'] > 8 or sum(r['mem_gb'] for r in m['registered']) > 24
        or m['disk_free_bytes'] < 18.5 * 2**30
        or any((STAGE / folder / name).exists()
            for folder in ('instruction20_calibration_mac4344', 'instruction21_parallel_speed_gate',
                           'instruction22_disclosure_profile')
            for name in ('warning.json', 'failure.json')))


def start_identity(pid, expected):
    actual = subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True).strip()
    if actual != expected:
        raise RuntimeError(('同じ番号の別過程を再開しない', pid, actual, expected))


def interval(stop, resume):
    lower = (resume['monotonic_before_ns'] - stop['monotonic_after_ns']) / 1e9
    upper = (resume['monotonic_after_ns'] - stop['monotonic_before_ns']) / 1e9
    return dict(pause_seconds=(lower + upper) / 2, pause_seconds_lower=lower,
                pause_seconds_upper=upper, method='SIGSTOP/SIGCONTの前後の単調時計の中央と上下界')


def main():
    with (ROOT / 'supervisor.lock').open('x') as lock:
        lock.write(str(os.getpid()) + '\n')
    if (ROOT / 'pair_resumed.json').exists():
        raise RuntimeError('再開済みの過程へ重ねてシグナルを送らない')
    before = json.loads((PAUSE_ROOT / 'before_pause.json').read_text())
    paused = json.loads((PAUSE_ROOT / 'pair_paused.json').read_text())
    released_profile = (PAUSE_ROOT / 'profile_controller_released.json').exists()
    try:
        while True:
            G.deadline()
            fixed()
            ps = G.G.processes()
            for pid in PAIR:
                info = before['identities'][str(pid)]
                identity(ps, pid, info['worker'])
                identity(ps, info['worker'][0], info['observer'], paused=False)
            m = G.machine()
            if warnings(m):
                write('warning.json', dict(at=G.stamp(), machine=m,
                    existing_models_remain_paused=True, automatic_retry=False))
                raise RuntimeError('資源確認不足。既存模型の再開を止めて報告する')
            completed = {seed: native_complete(root, receipt, ps)
                         for seed, (root, receipt) in CASES.items()}
            if not released_profile:
                identity(ps, PROFILE_PID, before['profile_controller'])
                start_identity(PROFILE_PID, before['profile_controller_lstart'])
                begin = time.monotonic_ns()
                os.kill(PROFILE_PID, signal.SIGCONT)
                end = time.monotonic_ns()
                write('profile_controller_released.json', dict(at=G.stamp(), pid=PROFILE_PID,
                    signal='SIGCONT', monotonic_before_ns=begin, monotonic_after_ns=end,
                    seed41_native_completed=completed[41], instruction24_priority=True, profile_not_duplicate_started=True,
                    existing_controller_enforces_jobs_resources=True))
                released_profile = True
            if all(completed.values()):
                for pid in PAIR:
                    start_identity(pid, before['identities'][str(pid)]['lstart'])
                fixed()
                # 二本とも同じ操作で再開。実際のシグナル前後の時刻を別々に残す。
                wall_before = G.stamp()
                events = []
                for pid in PAIR:
                    begin = time.monotonic_ns()
                    os.kill(pid, signal.SIGCONT)
                    end = time.monotonic_ns()
                    events.append(dict(pid=pid, signal='SIGCONT', monotonic_before_ns=begin,
                                       monotonic_after_ns=end))
                resumed = dict(at=G.stamp(), pair_wall_before=wall_before, events=events,
                    all_four_calibration_native_complete=completed,
                    pair_signal_gap_ns=events[1]['monotonic_before_ns']-events[0]['monotonic_after_ns'],
                    pause_intervals={str(e['pid']): interval(paused['events'][i], e)
                                     for i, e in enumerate(events)},
                    original_measurements_not_modified=True,
                    cpu_pause_not_added=True, wall_pause_to_subtract_only_in_separate_report=True)
                write('pair_resumed.json', resumed)
                write('status.json', dict(at=G.stamp(), pid=os.getpid(),
                    phase='existing_pair_resumed_report_pending', calibration_completed=completed,
                    new_models_started=0, production_started=False))
                return
            write('status.json', dict(at=G.stamp(), pid=os.getpid(),
                phase='instruction24_profile_prioritized_pair_waiting_all_calibration',
                calibration_completed=completed, profile_controller_released=released_profile,
                pair_model_pids=list(PAIR), machine=m, new_models_started=0,
                paused_models_in_global_count=True, automatic_retry=False))
            time.sleep(15)
    except Exception as exc:
        write('failure.json', dict(at=G.stamp(), error=repr(exc),
            phase='stopped_no_automatic_retry', existing_models_not_restarted=True,
            profile_controller_released=released_profile, models_not_terminated=True))
        write('status.json', dict(at=G.stamp(), pid=os.getpid(),
            phase='stopped_no_automatic_retry', error=repr(exc), automatic_retry=False))
        raise


if __name__ == '__main__':
    main()
