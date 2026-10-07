"""一つの関門だけを受付内で走らせる。模型・命令・出力形式は変えない。"""
from pathlib import Path
import json, os, signal, subprocess, sys, time

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'native_full_01'
PAR = ROOT/'parallel_instruction7_01'
sys.path.insert(0,str(ROOT.parent/'codex_sme_time_evict_2026-10-06'))
from cpu_guard_05 import cpu_reading
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions, descendants, now, ps, save

name = sys.argv[1]
assert name in ('on_own','on_keep')
spec = json.loads((PAR/(name+'_spec.json')).read_text())
case = WORK/name
marker = PAR/(name+'_started.json')
try:
    assert case.is_dir() and (case/'instruction7_reserved.json').exists()
    assert not marker.exists() and not (case/'output').exists() and not (WORK/(name+'.json')).exists(), '同じ関門を二重起動しない'
    while True:
        assert not (PAR/'STOP.json').exists(), '他方の関門が停止したため開始しない'
        resources = conditions()
        count = cpu_reading([])['total_compute_count']
        if resources['free_bytes'] >= 20*2**30 and not resources['swap_grew'] and not resources['thermal_warning'] and count < 8:
            break
        save(PAR/(name+'_waiting.json'),{'at':now(),'resources':resources,'count':count})
        time.sleep(2)
    save(marker,{'at':now(),'runner_pid':os.getpid(),'claim_pid':os.getppid(),'resources':resources,'count':count,'spec':spec})
    started=time.monotonic()
    peak=0
    paused_seconds=0.0
    pause_start=None
    with (case/'run.log').open('x') as log, (PAR/(name+'_resident.jsonl')).open('x') as observations:
        proc=subprocess.Popen(spec['command'],cwd=spec['cwd'],env=dict(os.environ,PYTHONHASHSEED='0'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        held=False
        while proc.poll() is None:
            time.sleep(2)
            resources=conditions()
            rows=ps()
            rss=sum(rows[p]['rss'] for p in descendants(proc.pid,rows) if p in rows)
            peak=max(peak,rss)
            count=cpu_reading([])['total_compute_count']
            peer_stop=(PAR/'STOP.json').exists()
            bad=resources['free_bytes'] < 18.5*2**30 or resources['swap_grew'] or resources['thermal_warning'] or count > 8 or peer_stop
            observations.write(json.dumps({'at':now(),'elapsed_seconds':time.monotonic()-started,'rss_bytes':rss,'count':count,'held':held,'resources':resources},ensure_ascii=False)+'\n')
            observations.flush()
            if bad and not held:
                os.killpg(proc.pid,signal.SIGSTOP)
                held=True
                pause_start=time.monotonic()
                save(PAR/(name+'_resource_hold.json'),{'at':now(),'model_pid':proc.pid,'resources':resources,'count':count,'peer_stop':peer_stop})
            elif held and resources['free_bytes'] >= 20*2**30 and not bad and count < 8:
                os.killpg(proc.pid,signal.SIGCONT)
                held=False
                paused_seconds+=time.monotonic()-pause_start
                pause_start=None
        if pause_start is not None: paused_seconds+=time.monotonic()-pause_start
    result={'at':now(),'exit':proc.returncode,'wall_seconds':time.monotonic()-started,'paused_seconds':paused_seconds,'command':spec['command'],'source':spec['cwd'],'env':{'PYTHONHASHSEED':'0'},'maximum_observed_model_tree_rss_bytes':peak,'rss_sampling_seconds':2,'parallel_gate_time_not_used_for_instruction4':True}
    save(WORK/(name+'.json'),result)
    if proc.returncode:
        raise RuntimeError('関門の走行の不通：'+name+'\n'+(case/'run.log').read_text()[-3000:])
    print(json.dumps(result,ensure_ascii=False),flush=True)
except Exception as e:
    save(PAR/(name+'_STOP.json'),{'at':now(),'case':name,'reason':str(e)})
    if not (PAR/'STOP.json').exists(): save(PAR/'STOP.json',{'at':now(),'case':name,'reason':str(e)})
    raise
