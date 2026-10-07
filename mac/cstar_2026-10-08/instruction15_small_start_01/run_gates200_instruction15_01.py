"""指示15の200試行。原版と旗なし・GC・encode・両方を4GBの受付で直列に照らす。"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import hashlib, json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'gates200_instruction15_01'
BASE = ROOT.parent/'codex_cstar_2026-10-07'
MATCH = ROOT.parent/'codex_cstar_profile_2026-10-08/match_times_instruction10_01'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0] = [str(BASE), str(ROOT.parent/'codex_sme_time_evict_2026-10-06'),
               str(ROOT.parent/'codex_logp_main_2026-10-06')]
from common_01 import conditions, now, save, ps, descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare

PLAN = json.loads((ROOT/'gate_plan_instruction15_01.json').read_text())
OBSERVER = ROOT/'observe_cpu_01.py'

def before_deadline():
    assert datetime.now().astimezone() < datetime.fromisoformat('2026-10-09T09:00:00+09:00'), '期限以後に新しい模型を始めない'

def individual_running():
    assert not (MATCH/'STOP.json').exists(), '個別計測の停止。後続を始めない'
    if not (MATCH/'started.json').exists(): return False
    if (MATCH/'complete.json').exists():
        assert json.loads((MATCH/'complete.json').read_text())['passed']
        return False
    return True

def source_check(source, commit):
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source).strip(), '汚れた作業版。解決しない'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() == commit
    assert hashlib.sha256(OBSERVER.read_bytes()).hexdigest() == PLAN['observer_sha256']

def run(item):
    name, flags = item['name'], item['flags']
    source = Path(item['source'])
    case = WORK/name
    assert not case.exists(), '完了・途中の200試行を二重に始めない'
    while True:
        before_deadline()
        safe = conditions()
        assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
        if not individual_running() and cpu_reading([])['total_compute_count'] < 8: break
        save(WORK/'waiting.json',dict(at=now(),reason='自分の個別計測又は模型の8本上限で待機'))
        time.sleep(10)
    source_check(source,item['source_commit'])
    case.mkdir()
    command = list(PLAN['native_command'])
    command[0] = PY
    command[3] = str(case/'output')
    command[command.index('--trial-count')+1] = '200'
    command += flags
    assert command[command.index('--horizon')+1] == '1740'
    assert command[command.index('--seeds')+1] == '1'
    assert command[command.index('--shop-world')+1] == '2'
    save(case/'native_command.json',command)
    env = dict(os.environ,PYTHONHASHSEED='0',SME_EXACT_SOURCE=str(source))
    for key in ('LC_ALL','LANG','LC_CTYPE'): env.pop(key,None)
    invocation = [PY,str(OBSERVER),str(case/'native_command.json')]
    start, held, paused, peak = time.monotonic(), None, 0.0, 0
    with (case/'run.log').open('x') as log:
        proc = subprocess.Popen(invocation,cwd=source,env=env,stdout=log,
                                stderr=subprocess.STDOUT,start_new_session=True)
        save(case/'started.json',dict(at=now(),runner_pid=proc.pid,command=invocation,
             native_command=command,source=str(source),source_commit=item['source_commit'],
             memory_claim_gb=4,resources=safe,observer_sha256=PLAN['observer_sha256']))
        while proc.poll() is None:
            time.sleep(2)
            if proc.poll() is not None: break
            safe = conditions()
            cpu = cpu_reading([{'child':SimpleNamespace(pid=proc.pid)}])
            rows = ps()
            rss = sum(rows[p]['rss'] for p in descendants(proc.pid,rows) if p in rows)
            peak = max(peak,rss)
            timing_active = (MATCH/'started.json').exists() and not (MATCH/'complete.json').exists()
            reasons = []
            if safe['free_bytes'] < 18.5*2**30: reasons.append('空き容量の下限')
            if safe['swap_grew']: reasons.append('直近10分のスワップ増加')
            if safe['thermal_warning']: reasons.append('熱の警告')
            if cpu['external_count']+max(1,cpu['own_compute_count']) > 8: reasons.append('模型の8本上限')
            if timing_active: reasons.append('自分の個別時間の計測を優先')
            if rss > 4*2**30: reasons.append('200試行の実測常駐が受付見込み4GBを超えた')
            with (case/'resources.jsonl').open('a') as f:
                f.write(json.dumps(dict(at=now(),rss_bytes=rss,resources=safe,cpu=cpu,
                                       held=held is not None,reasons=reasons))+'\n')
            if reasons and held is None:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid,signal.SIGSTOP)
                held = time.monotonic()
                save(case/'resource_hold.json',dict(at=now(),reasons=reasons,runner_pid=proc.pid))
            elif held is not None and not reasons and safe['free_bytes'] >= 20*2**30:
                assert os.getpgid(proc.pid) == proc.pid
                os.killpg(proc.pid,signal.SIGCONT)
                paused += time.monotonic()-held
                held = None
            if (MATCH/'STOP.json').exists() or rss > 4*2**30:
                raise RuntimeError('自分の200試行だけを保留し停止を報告：'+str(reasons))
        code = proc.returncode
    save(case/'finished.json',dict(at=now(),exit=code,wall_seconds=time.monotonic()-start,
          paused_seconds=paused,maximum_observed_model_tree_rss_bytes=peak,sampling_seconds=2))
    if code: raise RuntimeError(name+'：関門の不通\n'+(case/'run.log').read_text()[-3000:])
    source_check(source,item['source_commit'])
    manifest = json.loads((case/'output/manifest.jsonl').read_text().splitlines()[-1])
    assert manifest['trial_count'] == 200
    assert manifest['smereplay']['predictions'] == manifest['smereplay']['updates'] == 200
    timing = json.loads((case/'whole_cpu.json').read_text())
    assert timing['configured_trials'] == 200
    if name != 'original_C':
        comparison = compare(WORK/'original_C/output',case/'output',case/'comparison.json',stop_first=True)
        assert comparison['passed'] and len(comparison['files']) == 7
    save(case/'complete.json',dict(at=now(),passed=True,configured_trials=200,flags=flags,
         compared_with_original=name!='original_C',cpu_observed=True))

try:
    before_deadline()
    assert json.loads((ROOT/'encode_checks_01.json').read_text())['passed']
    assert not (WORK/'started.json').exists(), '同じ監督を二重起動しない'
    save(WORK/'started.json',dict(at=now(),pid=os.getpid(),memory_claim_gb=4,
         plan_sha256=hashlib.sha256((ROOT/'gate_plan_instruction15_01.json').read_bytes()).hexdigest()))
    completed = []
    for item in PLAN['cases']:
        save(WORK/'current.json',dict(at=now(),case=item['name']))
        run(item)
        completed.append(item['name'])
    save(WORK/'complete.json',dict(at=now(),passed=True,completed=completed,
         configured_trials=200,comparisons=4,files_per_comparison=7,full1740_not_passed=True))
except Exception as error:
    WORK.mkdir(exist_ok=True)
    save(WORK/'STOP.json',dict(at=now(),passed=False,reason=str(error),remaining_not_started=True))
    raise
