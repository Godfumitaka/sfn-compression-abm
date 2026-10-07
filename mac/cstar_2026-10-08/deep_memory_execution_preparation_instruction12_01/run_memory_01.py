"""固定した原版・観測・出力で一回だけ実行し、全記録を比較する。"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import hashlib, json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent.parent
PHASE = sys.argv[1]
assert PHASE in ('preflight20_01', 'full1740_01')
WORK = ROOT / PHASE
MEMORY = 1 if PHASE == 'preflight20_01' else 11
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0] = [str(BASE/'codex_cstar_2026-10-07'),
               str(BASE/'codex_sme_time_evict_2026-10-06'),
               str(BASE/'codex_logp_main_2026-10-06')]
from common_01 import conditions, now, save, ps, descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare


def deadline():
    assert datetime.now().astimezone().isoformat() < '2026-10-09T09:00:00+09:00', '期限以後に新しい模型を始めない'


def fixed_plan():
    plan = json.loads((ROOT/'execution_plan_01.json').read_text())
    prepared = json.loads((ROOT/'preparation_01.json').read_text())
    for name, sha in plan['scripts_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == sha, '固定した台本が変わった：'+name
    source = Path(prepared['source'])
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source).strip(), '汚れた原版。解決しない'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == prepared['source_commit']
    return plan, prepared, source


def structure_finished():
    root = BASE/'codex_cstar_structure_2026-10-08/full1740_01'
    complete = json.loads((root/'complete.json').read_text())
    assert complete['passed'] and set(complete['completed']) == {'off_A', 'off_L', 'off_Cstar', 'structure_Cstar'}
    assert not (root/'STOP.json').exists()
    for name in complete['completed']:
        result = json.loads((root/name/'comparison.json').read_text())
        assert result['passed'] and result['files'] and all(x['equal'] for x in result['files'])
    rows = ps()
    claim = json.loads((root/'claim.json').read_text())
    assert claim['pid'] not in rows or 'Z' in rows[claim['pid']]['stat'], '前の受付の終了が先'
    assert not any('codex_cstar_structure_2026-10-08/run_gates_01.py' in x['command']
                   and 'Z' not in x['stat'] for x in rows.values())


def memory_fit(plan):
    pre = ROOT/'preflight20_01'
    assert json.loads((pre/'complete.json').read_text())['passed']
    claim = json.loads((pre/'claim.json').read_text())
    rows = ps()
    assert claim['pid'] not in rows or 'Z' in rows[claim['pid']]['stat'], '20試行の受付終了が先'
    value = json.loads((ROOT/'full_memory_check_01.json').read_text())
    assert value['fits'] and value['estimated_full_peak_bytes'] <= 11*2**30
    assert value['bitmap_limit_bytes'] == plan['bitmap_limit_bytes']
    assert value['observer_margin_bytes'] == plan['observer_margin_bytes']
    for filename, sha in value['input_sha256'].items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == sha, '受付のメモリの根拠が変わった'


try:
    deadline()
    plan, prepared, source = fixed_plan()
    structure_finished()
    assert json.loads((ROOT/'checks_01.json').read_text())['passed']
    assert not (WORK/'started.json').exists(), '既存の観測を二重に始めない'
    if PHASE == 'full1740_01':
        memory_fit(plan)
    command = prepared['commands'][PHASE]
    configured = 20 if PHASE == 'preflight20_01' else 1740
    assert int(command[command.index('--trial-count')+1]) == configured
    assert command[3] == str(WORK/'output') and not (WORK/'output').exists()
    safe = conditions()
    assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
    assert cpu_reading([])['total_compute_count'] < 8
    deadline()
    save(WORK/'native_command.json', command)
    env = dict(os.environ, **prepared['env'])
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    invocation = [PY, str(ROOT/'observe_memory_01.py'), str(WORK/'native_command.json')]
    start = time.monotonic()
    paused, held, peak = 0., None, 0
    with (WORK/'run.log').open('x') as log:
        proc = subprocess.Popen(invocation, cwd=source, env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        save(WORK/'started.json', dict(at=now(), pid=os.getpid(), runner_pid=proc.pid,
             source_commit=prepared['source_commit'], command=invocation,
             native_command=command, memory_claim_gb=MEMORY, resources=safe))
        pending_file = BASE/'codex_cstar_pending_2026-10-06/pending_01.json'
        pending = json.loads(pending_file.read_text())
        pending.update(deep_memory_model_started=True, deep_memory_phase=PHASE,
                       deep_memory_controller_pid=os.getpid())
        save(pending_file, pending)
        while proc.poll() is None:
            time.sleep(2)
            safe = conditions()
            cpu = cpu_reading([{'child': SimpleNamespace(pid=proc.pid)}])
            rows = ps()
            rss = sum(rows[p]['rss'] for p in descendants(proc.pid, rows) if p in rows)
            peak = max(peak, rss)
            bad = (safe['free_bytes'] < 18.5*2**30 or safe['swap_grew'] or safe['thermal_warning']
                   or cpu['external_count'] + max(1, cpu['own_compute_count']) > 8)
            with (WORK/'resources.jsonl').open('a') as f:
                f.write(json.dumps(dict(at=now(), rss_bytes=rss, resources=safe, cpu=cpu,
                                       held=held is not None))+'\n')
            if bad and held is None:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid, signal.SIGSTOP)
                held = time.monotonic()
            elif held is not None and not bad and safe['free_bytes'] >= 20*2**30:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid, signal.SIGCONT)
                paused += time.monotonic()-held
                held = None
        code = proc.returncode
    save(WORK/'finished.json', dict(at=now(), exit=code, wall_seconds=time.monotonic()-start,
         paused_seconds=paused, maximum_observed_model_tree_rss_bytes=peak, sampling_seconds=2))
    assert code == 0, '観測の関門不通：'+(WORK/'run.log').read_text()[-3000:]
    fixed_plan()
    observations = json.loads((WORK/'observations_complete.json').read_text())
    samples = [json.loads(line) for line in (WORK/'memory_observations.jsonl').read_text().splitlines()]
    expected = ([('after_prediction', 19), ('first_engine_return_at_fixed_trial', 19),
                 ('first_snapshot_at_fixed_trial', 19), ('completion', 19)] if configured == 20 else
                [('after_prediction', 99), ('after_prediction', 999), ('after_prediction', 1739),
                 ('first_engine_return_at_fixed_trial', 1399), ('first_snapshot_at_fixed_trial', 1399), ('completion', 1739)])
    assert observations['observer_completed'] and observations['predictions'] == configured
    assert sorted((x['kind'], x['trial_index']) for x in samples) == sorted(expected), '固定した観測の件数が不完全'
    incomplete = [dict(kind=x['kind'], trial_index=x['trial_index'], reason=x['reason']) for x in samples if not x['complete']]
    save(WORK/'observation_check.json', dict(at=now(), samples=len(samples), complete=not incomplete,
         incomplete_count=len(incomplete), incomplete_examples=incomplete[:3], expected=expected))
    assert not incomplete, '参照の集計が不完全：'+json.dumps(incomplete[:3], ensure_ascii=False)
    assert all(x['observer_bitmap_limit_bytes'] == plan['bitmap_limit_bytes'] for x in samples)
    manifest = json.loads((WORK/'output/manifest.jsonl').read_text().splitlines()[-1])
    assert manifest['trial_count'] == manifest['smereplay']['predictions'] == manifest['smereplay']['updates'] == configured
    baseline = BASE/'codex_cstar_2026-10-07'/('native_preflight_02' if configured == 20 else 'native_full_01')/'on_own/output'
    comparison = compare(baseline, WORK/'output', WORK/'comparison.json', stop_first=True)
    assert len(comparison['files']) == 7
    save(WORK/'complete.json', dict(at=now(), passed=True, configured_trials=configured,
         model_bytes_identical=True, observation_complete=True, samples=len(samples),
         source_commit=prepared['source_commit'], observer_sha256=plan['scripts_sha256']['observe_memory_01.py']))
except Exception as error:
    WORK.mkdir(exist_ok=True)
    save(WORK/'STOP.json', dict(at=now(), passed=False, reason=str(error), remaining_not_started=True,
                              output_retained=True, repair_not_attempted=True))
    raise
