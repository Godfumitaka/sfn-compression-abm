"""開始前に実在した出生子の終了を待ち、一度だけ新しい読取受付へ渡す。"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, importlib.util, json, os, re, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RR = ROOT / 'report-results'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
PIDS = [89543, 89544, 89545, 89546]
STATE = HERE / 'resource_waiter_status.json'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def status(state, **fields):
    write(STATE, dict(at=datetime.now().astimezone().isoformat(), state=state,
                     pid=os.getpid(), observed_original_birth_pids=PIDS, model_starts=0, **fields))


with (HERE / 'resource_waiter.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert not STATE.exists() and not (HERE / 'runtime_attempt2').exists()
    status('waiting_for_recorded_birth_children_to_exit')
    while True:
        if datetime.now(timezone.utc) >= datetime.fromisoformat('2026-10-13T09:00:00+09:00'):
            status('deadline_no_new_processing')
            break
        ps = subprocess.run(['/bin/ps', '-p', ','.join(map(str, PIDS)), '-o', 'pid=,ppid=,pgid=,stat=,etime='],
                            text=True, capture_output=True)
        if ps.returncode not in (0, 1):
            status('scoped_pid_read_failed', returncode=ps.returncode)
            break
        if not ps.stdout.strip():
            write(HERE / 'recorded_birth_children_exited.json', dict(at=datetime.now().astimezone().isoformat(),
                  original_pids=PIDS, scoped_ps_output=ps.stdout, returncode=ps.returncode,
                  actual_resource_change=True, global_ps=0))
            module = importlib.util.spec_from_file_location('night32_wait', ROOT / 'source/tools/verb/night.py')
            night = importlib.util.module_from_spec(module)
            module.loader.exec_module(night)
            with (ROOT.parent / 'codex_sme_light_2026-10-04/control_writer_01.lock').open('a') as writer:
                fcntl.flock(writer, fcntl.LOCK_EX)
                night.fetch_report()
                text = (RR / 'control/受け箱/動詞の世界の係.md').read_text()
                parts = re.split(r'(?=^## 指示 \d+)', text, flags=re.M)[1:]
                latest = max(int(re.search(r'^## 指示 (\d+)', p).group(1)) for p in parts)
                missing = [p.splitlines()[0] for p in parts if not re.search(r'^受領（', p, re.M)]
            if latest != 32 or missing:
                status('held_for_new_instructions', latest_instruction=latest, unreceived=missing)
                break
            status('dispatching_attempt2_after_actual_resource_change')
            with (HERE / 'attempt2_dispatch.log').open('x') as output:
                process = subprocess.Popen([PY, '-B', str(HERE / 'run_fingerprint_compress_attempt2.py')],
                                           stdout=output, stderr=subprocess.STDOUT)
                write(HERE / 'attempt2_dispatch_pid.json', dict(pid=process.pid,
                      at=datetime.now().astimezone().isoformat()))
                code = process.wait()
            status('attempt2_finished', exit_code=code, automatic_retries=0)
            break
        time.sleep(30)
