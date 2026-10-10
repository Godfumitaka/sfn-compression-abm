"""指示31。固定比較器の結果だけを空の置き場へ出し、進行記録を分ける。"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NR = Path('$WORKSPACE/newport_2026-10-07')
ROOT = NR.parent
RUNTIME = HERE / 'compare_runtime'
RESULTS = NR / 'instruction31/results_attempt2'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
LEFT = NR / 'instruction23_production/19_seed001_score_e_off'
RIGHT = ROOT.parent / 'codex_cstar_pending_2026-10-06/queue19p_20261010/19_seed001_flags_on'
COMP = NR / 'instruction27/checkpoint_digest.py'
DEST = RESULTS / 'checkpoint_1000.json'
STATE = RUNTIME / 'status.json'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_inventory():
    folder = NR / 'instruction27_comparisons'
    return {p.name: sha(p) for p in folder.iterdir() if p.is_file()}


def status(state, **value):
    write(STATE, dict(at=datetime.now().astimezone().isoformat(), state=state,
                     instruction=27, model_starts=0, **value))


def admitted():
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    assert {p.name for p in RESULTS.iterdir()} == {'checkpoint_0500.json'}, '500の原合格以外を結果へ混ぜない'
    assert json.loads((RESULTS / 'checkpoint_0500.json').read_text())['passed']
    assert not DEST.exists(), '同じ1000比較を重ねない'
    assert sha(COMP) == 'f9dfd958bb14e6964df8aa503757939cd21009c2f3362f752de8d759f0642ced'
    fixed = json.loads((NR / 'instruction27/fixed_tools.json').read_text())
    for name in ['tools/instruction11_io.py', 'run_registered.py', 'birth_census.py']:
        assert sha(NR / 'instruction27' / name) == fixed[name]
    proofs = []
    for case, expected in [(LEFT, '8eb6c689a8c21749ed9b92353fbba930c68738c70ce249cc80d9d98eaf829f43'),
                           (RIGHT, 'c81d44f5511c9e6520d72110ce3ec97b1aa68b571b5ab56b0a905695bdd0394e')]:
        assert sha(case / 'spec.json') == expected
        spec = json.loads((case / 'spec.json').read_text())
        proof = Path(spec['output']) / 'comparison_checkpoints/completed_1000/confirmed.json'
        value = json.loads(proof.read_text())
        assert value['confirmed'] and value['completed_trials'] == 1000 and value['last_trial'] == 999
        proofs.append(dict(path=str(proof), sha256=sha(proof)))
    sys.path.insert(0, str(NR / 'instruction27'))
    from run_registered import start_counts
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    counts = start_counts(raw)
    limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True)) - 2
    therm = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
    thermal_ok = 'No thermal warning level has been recorded' in therm and not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', therm)
    free = shutil.disk_usage(RESULTS).free
    snapshot = dict(at=datetime.now().astimezone().isoformat(), processes=raw, counts=counts,
                    cpu_budget=limit, comparison_cpu_slots=1, comparison_model_slots=0,
                    reserved_memory_gib=0.3, memory_basis_previous_max_rss_bytes=58540032,
                    thermal=therm, free_disk_bytes=free,
                    swap_original_rows=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-12:],
                    admission_registry_original=(Path.home() / 'jobs/registry.tsv').read_text(),
                    original_confirmed=proofs, counting_rule=counts['counting_rule'],
                    unchanged_shared_classifier=True, results_folder_was_empty=True)
    write(RUNTIME / 'before_start.json', snapshot)
    if not (counts['outside_heavy'] + 1 <= limit and counts['unknown_active_spawn'] == 0
            and counts['model_process_count'] <= 8 and thermal_ok and free >= 20 * 2**30):
        status('resource_conditions_not_ready', admitted_pid=os.getpid(), comparison_started=False)
        return 2
    previous = old_inventory()
    write(RUNTIME / 'old_metadata_before_sha256.json', previous)
    status('comparing_confirmed_1000', admitted_pid=os.getpid(), comparison_started=True)
    command = [PY, '-B', str(COMP), str(LEFT), str(RIGHT), '1000', str(DEST)]
    start = time.time()
    with (RUNTIME / 'run.log').open('x') as log:
        done = subprocess.run(['/usr/bin/time', '-l', *command], stdout=log, stderr=subprocess.STDOUT)
    write(RUNTIME / 'result.json', dict(at=datetime.now().astimezone().isoformat(),
          exit_code=done.returncode, wall_seconds=time.time() - start, command=command,
          model_starts=0, comparator_sha256=sha(COMP)))
    after = old_inventory()
    write(RUNTIME / 'old_metadata_after_sha256.json', after)
    assert previous == after, '旧進行記録は変更/移動/削除しない'
    result = json.loads(DEST.read_text()) if DEST.exists() else None
    status('completed' if done.returncode == 0 else 'stopped', exit_code=done.returncode,
           comparison_present=DEST.exists(), passed=result['passed'] if result else None,
           old_metadata_unchanged=True, full_length_match=False, flagged_results_usable=False)
    return done.returncode


if '--admitted' in sys.argv:
    raise SystemExit(admitted())

with (HERE / 'dispatch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = json.loads((HERE / 'receipt_published.json').read_text())
    assert receipt['normal_push_succeeded'] and len(receipt['commit']) == 40
    assert not RUNTIME.exists() and not DEST.exists(), '同じ1000受付/比較を二重起動しない'
    RUNTIME.mkdir()
    status('submitted_once_to_jobs', launcher_pid=os.getpid(), comparison_started=False)
    command = [PY, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner',
               '動詞・指示27・確定1000境界の読取比較', '--mem', '0.3', '--disk-path', str(RESULTS),
               '--', PY, '-B', str(Path(__file__).resolve()), '--admitted']
    write(RUNTIME / 'launcher.json', dict(at=datetime.now().astimezone().isoformat(),
          pid=os.getpid(), command=command, model_starts=0, receipt_commit=receipt['commit']))
    with (RUNTIME / 'jobs.log').open('x') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        write(RUNTIME / 'jobs_pid.json', dict(pid=child.pid))
        rc = child.wait()
    if not (RUNTIME / 'result.json').exists():
        write(RUNTIME / 'admission_result.json', dict(at=datetime.now().astimezone().isoformat(),
              exit_code=rc, comparison_started=False))
    raise SystemExit(rc)
