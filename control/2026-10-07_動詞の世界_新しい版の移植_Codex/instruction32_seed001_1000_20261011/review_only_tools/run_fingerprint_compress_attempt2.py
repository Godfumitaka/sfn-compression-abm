"""受付・全資源条件を保ち、指紋/圧縮だけを一度起動する。"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
I = Path(__file__).resolve().parent
N = Path('$WORKSPACE/newport_2026-10-07')
RUNTIME = I / 'compression_runtime'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def status(state, **values):
    write(RUNTIME / 'status.json', dict(at=datetime.now().astimezone().isoformat(), state=state,
        instruction=32, model_starts=0, deleted_files=0, **values))


def admitted():
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    assert not (I / 'fingerprint_compress_completed.json').exists() and not (I / 'fingerprints').exists()
    sys.path.insert(0, str(N / 'instruction27'))
    from run_registered import start_counts
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    counts = start_counts(raw)
    limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True)) - 2
    thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
    thermal_ok = 'No thermal warning level has been recorded' in thermal and not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', thermal)
    free = shutil.disk_usage(I).free
    write(RUNTIME / 'before_start.json', dict(at=datetime.now().astimezone().isoformat(), processes=raw,
        counts=counts, cpu_budget=limit, read_cpu_slots=1, read_model_slots=0,
        reserved_memory_gib=0.3, memory_basis_previous_max_rss_bytes=58671104,
        thermal=thermal, free_disk_bytes=free,
        swap_original_rows=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-12:],
        admission_registry_original=(Path.home() / 'jobs/registry.tsv').read_text(),
        counting_rule=counts['counting_rule'], shared_classifier_unchanged=True))
    if not (counts['outside_heavy'] + 1 <= limit and counts['unknown_active_spawn'] == 0
            and counts['model_process_count'] <= 8 and thermal_ok and free >= 20 * 2**30):
        status('resource_conditions_not_ready', processing_started=False)
        return 2
    command = [PY, '-B', str(I / 'fingerprint_compress.py')]
    status('fingerprint_and_compress', processing_started=True, admitted_pid=os.getpid())
    start = time.time()
    with (RUNTIME / 'run.log').open('x') as log:
        done = subprocess.run(['/usr/bin/time', '-l', *command], stdout=log, stderr=subprocess.STDOUT)
    write(RUNTIME / 'result.json', dict(at=datetime.now().astimezone().isoformat(),
        exit_code=done.returncode, wall_seconds=time.time() - start, command=command,
        driver_sha256=hashlib.sha256((I / 'fingerprint_compress.py').read_bytes()).hexdigest(),
        model_starts=0, deleted_files=0))
    status('completed' if done.returncode == 0 else 'stopped', exit_code=done.returncode,
           completed_record_present=(I / 'fingerprint_compress_completed.json').exists(), automatic_retries=0)
    return done.returncode


if '--admitted' in sys.argv:
    raise SystemExit(admitted())

with (I / 'dispatch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = json.loads((I / 'archive_receipt_published.json').read_text())
    assert receipt['normal_push_succeeded'] and len(receipt['commit']) == 40
    assert not RUNTIME.exists(), '同じ監督/受付を重ねない'
    RUNTIME.mkdir()
    command = [PY, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner',
        '動詞・指示32・確定records指紋と削除なしgzip', '--mem', '0.3', '--disk-path', str(I),
        '--', PY, '-B', str(Path(__file__).resolve()), '--admitted']
    write(RUNTIME / 'launcher.json', dict(at=datetime.now().astimezone().isoformat(), pid=os.getpid(), command=command))
    status('submitted_once_to_jobs', processing_started=False)
    with (RUNTIME / 'jobs.log').open('x') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        write(RUNTIME / 'jobs_pid.json', dict(pid=process.pid))
        rc = process.wait()
    if not (RUNTIME / 'result.json').exists():
        write(RUNTIME / 'admission_result.json', dict(at=datetime.now().astimezone().isoformat(), exit_code=rc, processing_started=False))
    raise SystemExit(rc)
