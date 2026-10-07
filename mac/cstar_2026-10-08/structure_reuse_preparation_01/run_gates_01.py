"""指示12の図の索引・高さだけの旗を、原版へ全バイト比較する。"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
PHASE = sys.argv[1]
assert PHASE in ('preflight20_01','full1740_01')
WORK = ROOT/PHASE
MEMORY = 1 if PHASE == 'preflight20_01' else 11
SOURCE = ROOT/'source'
BASE = ROOT.parent/'codex_cstar_2026-10-07'
PROFILE = ROOT.parent/'codex_cstar_profile_2026-10-08'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0] = [str(BASE), str(ROOT.parent/'codex_sme_time_evict_2026-10-06'),
               str(ROOT.parent/'codex_logp_main_2026-10-06')]
from common_01 import conditions, now, save, ps, descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare

def before_deadline():
    assert datetime.now().astimezone().isoformat() < '2026-10-09T09:00:00+09:00', '期限以後に新しい模型を始めない'

def run(name, baseline, flags):
    before_deadline()
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE).strip(), '汚れた作業版'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip() == json.loads((ROOT/'gate_plan_01.json').read_text())['source_commit']
    case = WORK/name
    assert not case.exists(), '完了・途中の関門を二重に始めない'
    safe = conditions()
    assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
    while cpu_reading([])['total_compute_count'] >= 8:
        time.sleep(10)
        before_deadline()
        safe = conditions()
        assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
    case.mkdir()
    command = list(json.loads((baseline.parent/(baseline.name+'.json')).read_text())['command'])
    assert command[1] == 'tools/v3_run.py' and command[command.index('--seeds')+1] == '1'
    command[3] = str(case/'output')
    command += flags
    save(case/'native_command.json', command)
    env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(SOURCE))
    for key in ('LC_ALL','LANG','LC_CTYPE'): env.pop(key, None)
    invocation = [PY, str(ROOT/'observe_cpu_01.py'), str(case/'native_command.json')]
    start = time.monotonic()
    held = None
    paused = 0.0
    peak = 0
    with (case/'run.log').open('x') as log:
        proc = subprocess.Popen(invocation, cwd=SOURCE, env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        save(case/'started.json', dict(at=now(), runner_pid=proc.pid, command=invocation,
             native_command=command, source=str(SOURCE), memory_claim_gb=MEMORY, resources=safe))
        while proc.poll() is None:
            time.sleep(2)
            safe = conditions()
            cpu = cpu_reading([{'child':SimpleNamespace(pid=proc.pid)}])
            rows = ps()
            rss = sum(rows[p]['rss'] for p in descendants(proc.pid, rows) if p in rows)
            peak = max(peak, rss)
            bad = (safe['free_bytes'] < 18.5*2**30 or safe['swap_grew'] or safe['thermal_warning']
                   or cpu['external_count'] + max(1,cpu['own_compute_count']) > 8)
            with (case/'resources.jsonl').open('a') as f:
                f.write(json.dumps(dict(at=now(), rss_bytes=rss, resources=safe, cpu=cpu,
                                       held=held is not None))+'\n')
            if bad and held is None:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid,signal.SIGSTOP)
                held = time.monotonic()
            elif held is not None and not bad and safe['free_bytes'] >= 20*2**30:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid,signal.SIGCONT)
                paused += time.monotonic()-held
                held = None
        code = proc.returncode
    save(case/'finished.json', dict(at=now(), exit=code, wall_seconds=time.monotonic()-start,
          paused_seconds=paused, maximum_observed_model_tree_rss_bytes=peak, sampling_seconds=2))
    if code:
        raise RuntimeError(name+'：関門の不通\n'+(case/'run.log').read_text()[-3000:])
    configured = int(command[command.index('--trial-count')+1])
    manifest = json.loads((case/'output/manifest.jsonl').read_text().splitlines()[-1])
    assert manifest['trial_count'] == configured
    assert manifest['smereplay']['predictions'] == manifest['smereplay']['updates'] == configured
    timing = json.loads((case/'whole_cpu.json').read_text())
    assert timing['configured_trials'] == configured
    compare(baseline/'output',case/'output',case/'comparison.json',stop_first=True)
    save(case/'complete.json',dict(at=now(),passed=True,configured_trials=configured,
         model_bytes_identical=True,flags=flags,cpu_observed=True))

try:
    before_deadline()
    assert json.loads((PROFILE/'match_times_instruction10_01/complete.json').read_text())['passed'], '自分の個別計測の完了が先'
    assert (PROFILE/'match_times_instruction10_01/full1740_01/analysis.json').exists(), '個別計測の集計が先'
    assert json.loads((ROOT/'checks_01.json').read_text())['passed']
    if PHASE == 'full1740_01':
        assert json.loads((ROOT/'preflight20_01/complete.json').read_text())['passed'], '小関門が先'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE).strip(), '汚れた作業版'
    plan = json.loads((ROOT/'gate_plan_01.json').read_text())
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
    assert commit == plan['source_commit'], '準備した版のまま検証する'
    assert not (WORK/'started.json').exists(), '同じ監督を二重起動しない'
    WORK.mkdir(exist_ok=True)
    save(WORK/'started.json',dict(at=now(),pid=os.getpid(),source_commit=commit,memory_claim_gb=MEMORY))
    completed = []
    for item in plan['cases']:
        if item['phase'] != PHASE:
            continue
        save(WORK/'current.json',dict(at=now(),case=item['name']))
        run(item['name'],Path(item['baseline']),item['flags'])
        completed.append(item['name'])
    save(WORK/'complete.json',dict(at=now(),passed=True,completed=completed,model_bytes_identical=True))
except Exception as error:
    WORK.mkdir(exist_ok=True)
    save(WORK/'STOP.json',dict(at=now(),passed=False,reason=str(error),remaining_not_started=True))
    raise
