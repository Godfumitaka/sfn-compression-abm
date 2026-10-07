"""指示9のC*単独計測。20試行の計測の一致を確認してから後半を測る。"""
from pathlib import Path
from types import SimpleNamespace
import json,os,signal,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'codex_cstar_2026-10-07'
SOURCE=BASE/'source'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0]=[str(BASE),str(ROOT.parent/'codex_sme_time_evict_2026-10-06'),str(ROOT.parent/'codex_logp_main_2026-10-06')]
from common_01 import conditions,now,save,ps,descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare


def run(name,baseline,ranges):
    folder=ROOT/name
    assert not folder.exists(), '完了・途中の本を二重に始めない'
    folder.mkdir()
    source_command=json.loads((baseline.parent/(baseline.name+'.json')).read_text())['command']
    command=list(source_command);command[3]=str(folder/'output')
    configured=int(command[command.index('--trial-count')+1])
    save(folder/'native_command.json',command)
    safe=conditions()
    assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
    while cpu_reading([])['total_compute_count']:
        save(folder/'waiting_for_single_model.json',dict(at=now(),cpu=cpu_reading([])))
        time.sleep(10)
        safe=conditions()
        assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
    env=dict(os.environ,PYTHONHASHSEED='0',SME_EXACT_SOURCE=str(SOURCE),
             SME_PROFILE_TRIAL_LIMIT=str(configured),SME_PROFILE_TRIAL_RANGES=json.dumps(ranges))
    for key in ('LC_ALL','LANG','LC_CTYPE'):env.pop(key,None)
    args=[PY,str(ROOT/'observe_cstar_01.py'),str(folder/'native_command.json')]
    start=time.monotonic();held=None;paused=0.;peak=0
    with (folder/'run.log').open('x') as log:
        proc=subprocess.Popen(args,cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(folder/'started.json',dict(at=now(),runner_pid=proc.pid,command=args,native_command=command,
            env={'PYTHONHASHSEED':'0'},profile_ranges=ranges,memory_claim_gb=11,resources=safe))
        while proc.poll() is None:
            time.sleep(2)
            safe=conditions();cpu=cpu_reading([{'child':SimpleNamespace(pid=proc.pid)}])
            rows=ps();rss=sum(rows[p]['rss'] for p in descendants(proc.pid,rows) if p in rows);peak=max(peak,rss)
            bad=(safe['free_bytes']<18.5*2**30 or safe['swap_grew'] or safe['thermal_warning'] or cpu['external_count']>0)
            with (folder/'resources.jsonl').open('a') as f:
                f.write(json.dumps({**safe,'at':now(),'rss_bytes':rss,'own_model_count':cpu['own_compute_count'],
                                   'external_model_count':cpu['external_count'],'held':held is not None})+'\n')
            if bad and held is None:
                os.killpg(proc.pid,signal.SIGSTOP);held=time.monotonic()
                save(folder/'resource_hold.json',dict(at=now(),resources=safe,cpu=cpu,reason='単独の計測・資源の条件を守る'))
            elif held is not None and not bad and safe['free_bytes']>=20*2**30:
                os.killpg(proc.pid,signal.SIGCONT);paused+=time.monotonic()-held;held=None
        code=proc.returncode
    save(folder/'finished.json',dict(at=now(),exit=code,wall_seconds=time.monotonic()-start,paused_seconds=paused,
         maximum_observed_model_tree_rss_bytes=peak,sampling_seconds=2))
    if code:raise RuntimeError(name+'：計測の不通\n'+(folder/'run.log').read_text()[-4000:])
    manifest=json.loads((folder/'output/manifest.jsonl').read_text().splitlines()[-1])
    assert manifest['trial_count']==configured and manifest['smereplay']['predictions']==manifest['smereplay']['updates']==configured
    timing=json.loads((folder/'timing_complete.json').read_text())
    assert [r['trial'] for r in timing['rows']]==[i for begin,end in ranges for i in range(begin,min(end,configured))]
    compare(baseline/'output',folder/'output',folder/'comparison.json',stop_first=True)
    save(folder/'complete.json',dict(at=now(),passed=True,configured_trials=configured,measured_trials=timing['trials'],
        model_bytes_identical=True,peak_rss_mb=manifest['peak_rss_mb']))


try:
    assert not (ROOT/'started.json').exists()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip().startswith('7774b60')
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE).strip()
    save(ROOT/'started.json',dict(at=now(),pid=os.getpid(),memory_claim_gb=11,source='7774b60',instruction=9))
    run('preflight20_01',BASE/'native_preflight_02/on_own',[[0,20]])
    run('profile1740_01',BASE/'native_full_01/on_own',[[0,300],[1400,1600]])
    save(ROOT/'complete.json',dict(at=now(),passed=True,configured_trials=1740,measured_trials=500,model_bytes_identical=True))
except Exception as e:
    save(ROOT/'STOP.json',dict(at=now(),passed=False,reason=str(e),remaining_not_started=True))
    raise
