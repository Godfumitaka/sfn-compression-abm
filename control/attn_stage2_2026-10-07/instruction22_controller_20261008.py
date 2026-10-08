"""指示22の一本だけ。較正と全長比較を優先し、警告後に再投入しない。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'profile_200'
spec = importlib.util.spec_from_file_location('original_gate_guard', ROOT.parent / 'instruction19_speed_gate' / 'gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
MEM_GB = 1
TRIALS = 200


def write(name, data):
    path = ROOT / name
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def fixed():
    G.source_ok()
    manifest = json.loads((ROOT / 'preparation_manifest.json').read_text())
    for filename, digest in manifest['immutable_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('計測の道具・命令が変わった', filename))


def prior_warning():
    return any((ROOT.parent / folder / name).exists()
        for folder in ('instruction20_calibration_mac4344', 'instruction21_parallel_speed_gate')
        for name in ('warning.json', 'failure.json'))


def warn(m):
    return (not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
        or m['model_children'] > 8 or m['disk_free_bytes'] < 18.5 * 2**30
        or sum(r['mem_gb'] for r in m['registered']) > 24 or prior_warning())


def start_ok(m):
    return (G.start_ok(m) and sum(r['mem_gb'] for r in m['registered']) + MEM_GB <= 24
        and not prior_warning())


def entry():
    if (ROOT / 'entry_started.json').exists() or (RUN / 'output').exists():
        raise RuntimeError('開始済みの計測を再投入しない')
    while True:
        G.deadline(); fixed(); m = G.machine()
        if prior_warning() or any((ROOT / n).exists() for n in ('warning.json', 'failure.json')):
            raise RuntimeError('警告又は停止済み。計測を新規開始しない')
        if G.start_ok(m) and sum(r['mem_gb'] for r in m['registered']) <= 24:
            break
        write('entry_waiting.json', dict(at=G.stamp(), machine=m))
        time.sleep(10)
    command = json.loads((RUN / 'native_command.json').read_text())
    write('entry_started.json', dict(at=G.stamp(), code=G.CODE, world=2, seed=41,
        trials=TRIALS, horizon=1740, mem_gb=MEM_GB, machine=m, actual_native_command=command,
        profiling_only=True, speed_implementation=False, production_started=False))
    os.execv(G.PY, [G.PY, str(ROOT / 'profile_worker.py'), str(RUN / 'native_command.json')])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'entry':
        return entry()
    proc = None
    try:
        with (ROOT / 'supervisor.lock').open('x') as f:
            f.write(str(os.getpid()) + '\n')
        if any((RUN / n).exists() for n in ('output', 'run.log', 'measurement.json')):
            raise RuntimeError('既存の計測・模型を再投入しない')
        fixed()
        write('launch.json', dict(at=G.stamp(), pid=os.getpid(), code=G.CODE, mem_gb=MEM_GB,
            trials=TRIALS, world=2, seed=41, priority='after_calibration_and_instruction21'))
        while True:
            G.deadline(); fixed(); m = G.machine()
            if prior_warning():
                raise RuntimeError('優先する較正又は全長比較の警告。計測を開始しない')
            if start_ok(m):
                break
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='waiting_before_receipt', machine=m))
            time.sleep(15)
        command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示22 開示cProfile200',
            '--mem', str(MEM_GB), '--disk-path', str(RUN), '--', G.PY, str(ROOT / 'controller.py'), 'entry']
        (RUN / 'receipt_command.json').write_text(json.dumps(command, ensure_ascii=False, indent=2) + '\n')
        env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(G.SOURCE))
        for key in ('LANG', 'LC_ALL', 'LC_CTYPE'):
            env.pop(key, None)
        with (RUN / 'run.log').open('x') as log:
            proc = subprocess.Popen(command, cwd=G.SOURCE, env=env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
            write('receipt_submitted.json', dict(at=G.stamp(), pid=proc.pid, mem_gb=MEM_GB,
                machine_before=m, command=command))
            warned = False
            while proc.poll() is None:
                m = G.machine()
                effective = sum(r['mem_gb'] for r in m['registered'])
                if proc.pid not in {r['pid'] for r in m['registered']}:
                    effective += MEM_GB
                if warn(m) or effective > 24:
                    if not warned:
                        write('warning.json', dict(at=G.stamp(), machine=m, effective_mem_gb=effective,
                            models_not_signaled=True, automatic_retry=False))
                    warned = True
                write('status.json', dict(at=G.stamp(), pid=os.getpid(), receipt_pid=proc.pid,
                    phase='no_new_submission_waiting_natural_end' if warned else 'profile_receipt_wait_or_running',
                    machine=m, effective_mem_gb=effective, models_not_signaled=True))
                time.sleep(15)
        write('receipt_ended.json', dict(at=G.stamp(), pid=proc.pid, exit_code=proc.returncode))
        if warned or proc.returncode:
            raise RuntimeError(('警告又は実受付終了コード', warned, proc.returncode))
        measurement = json.loads((RUN / 'measurement.json').read_text())
        finished = json.loads((RUN / 'worker_finished.json').read_text())
        profile = json.loads((RUN / 'disclosure_profile.json').read_text())
        if (measurement['trials'] != TRIALS or not measurement['native_loop_returned']
            or not profile['returned'] or not profile['stage2_wrapper_installed']
            or profile['disclosed_accounting_calls'] != measurement['disclosed_trials']
            or profile['pid'] != measurement['pid'] or finished['pid'] != measurement['pid']
            or 'ALLDONE' not in (RUN / 'run.log').read_text()[-65536:]):
            raise RuntimeError('計測の実完走又は開示区間の確認不足')
        write('completed.json', dict(at=G.stamp(), exit_code=0, trials=TRIALS,
            measurement=measurement, worker_finished=finished, profile_source=str(RUN / 'disclosure_profile.json'),
            formal_calibration=False, speed_implementation=False))
        write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='profile_completed_report_pending',
            speed_implementation=False, production_started=False))
    except Exception as exc:
        write('failure.json', dict(at=G.stamp(), error=repr(exc), automatic_retry=False, models_not_signaled=True))
        while proc is not None and proc.poll() is None:
            write('status.json', dict(at=G.stamp(), phase='no_new_submission_waiting_natural_end',
                receipt_pid=proc.pid, error=repr(exc), models_not_signaled=True))
            time.sleep(15)
        write('status.json', dict(at=G.stamp(), phase='stopped_no_automatic_retry', error=repr(exc)))
        raise


if __name__ == '__main__':
    main()
