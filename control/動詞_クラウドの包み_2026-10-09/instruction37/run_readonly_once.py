"""指示37。CPU1・模型0の新規読取を元の受付と資源条件へ一度だけ通す。"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NR = HERE.parent
RUNTIME = HERE / 'readonly_runtime'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def admitted():
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    assert not (HERE / 'readonly1000').exists() and not (RUNTIME / 'result.json').exists()
    sys.path.insert(0, str(NR / 'instruction27'))
    from run_registered import start_counts
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    counts = start_counts(raw)
    limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True)) - 2
    therm = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
    heat = 'No thermal warning level has been recorded' in therm and not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', therm)
    free = shutil.disk_usage(HERE).free
    write(RUNTIME / 'before_start.json', dict(at=datetime.now().astimezone().isoformat(), processes=raw,
          counts=counts, cpu_budget=limit, required_cpu_slots=1, model_start_slots=0, reserved_memory_gib=0.3,
          memory_basis='既存読取比較の実最大58671104B。1行ずつのJSON読取と小さい表',
          thermal=therm, free_disk_bytes=free,
          swap_original_rows=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-12:],
          admission_registry_original=(Path.home() / 'jobs/registry.tsv').read_text(), unchanged_shared_classifier=True))
    if not (counts['model_process_count'] <= 8 and counts['unknown_active_spawn'] == 0
            and counts['outside_heavy'] + 1 <= limit and heat and free >= 20*2**30):
        write(RUNTIME / 'status.json', dict(state='resource_conditions_not_ready', processing_started=False, model_starts=0))
        return 2
    write(RUNTIME / 'status.json', dict(state='reading_confirmed1000', processing_started=True, model_starts=0))
    command = [PY, '-B', str(__file__), '--work']
    begin = time.time()
    with (RUNTIME / 'run.log').open('x') as log:
        done = subprocess.run(['/usr/bin/time', '-l', *command], stdout=log, stderr=subprocess.STDOUT)
    write(RUNTIME / 'result.json', dict(exit_code=done.returncode, wall_seconds=time.time()-begin,
          command=command, model_starts=0, actual100_gate_started=False))
    write(RUNTIME / 'status.json', dict(state='completed' if done.returncode == 0 else 'stopped_without_retry',
          exit_code=done.returncode, model_starts=0, original_GC_tests_rerun=False))
    return done.returncode


if '--work' in sys.argv:
    from check_prerequisites import run as check
    write(RUNTIME / 'prerequisites_checked.json', check(RUNTIME / 'synthetic_only_tests'))
    from read_sme1000 import run
    run()
    raise SystemExit(0)
if '--admitted' in sys.argv:
    raise SystemExit(admitted())
with (HERE / 'readonly_dispatch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = json.loads((HERE / 'received.json').read_text())
    assert receipt['normal_push_succeeded'] and receipt['instructions'] == [37] and len(receipt['commit']) == 40
    assert not RUNTIME.exists(), '同じ受付・集計を二重起動しない'
    RUNTIME.mkdir()
    write(RUNTIME / 'status.json', dict(state='submitted_once_to_jobs', processing_started=False, model_starts=0))
    command = [PY, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner', '動詞・指示37・既存1000の読取表',
        '--mem', '0.3', '--disk-path', str(HERE), '--', PY, '-B', str(Path(__file__).resolve()), '--admitted']
    write(RUNTIME / 'launcher.json', dict(pid=os.getpid(), command=command, receipt_commit=receipt['commit'], model_starts=0))
    with (RUNTIME / 'jobs.log').open('x') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        write(RUNTIME / 'jobs_pid.json', dict(pid=child.pid))
        rc = child.wait()
    if not (RUNTIME / 'result.json').exists():
        write(RUNTIME / 'admission_result.json', dict(exit_code=rc, processing_started=False, model_starts=0))
    raise SystemExit(rc)
