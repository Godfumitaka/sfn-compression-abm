"""受付一枠の小走行。失敗・不一致なら続きの条件を始めない。"""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json,os,re,signal,subprocess,sys,time
ROOT = Path(__file__).resolve().parent
WORK = ROOT/'native_full_01'
NEW = ROOT/'source'
BASE = ROOT.parent/'codex_sme_evict_2026-10-06/source_logp'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path.insert(0,str(ROOT.parent/'codex_sme_time_evict_2026-10-06'))
from cpu_guard_05 import cpu_reading
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions

def now(): return datetime.now().astimezone().isoformat()
def save(name,x): (WORK/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
from compare_gate_01 import compare as compare_records
def compare(left,right,case):
    return compare_records(left,right,WORK/(case+'_comparison.json'))

try:
    assert not WORK.exists(), '完了済み・途中の関門を二重に起動しない'
    WORK.mkdir()
    resources = conditions()
    cpu = cpu_reading([])
    save('resources_start.json',{'at':now(),'resources':resources,'cpu':cpu})
    assert cpu['total_compute_count'] < 8
    assert resources['free_bytes'] >= 20*2**30 and not resources['swap_grew'] and not resources['thermal_warning']
    save('unit_previous.json',{'at':now(),'tests':23,'passed':True,'code':'7774b60','reused_existing_tests':True})
    sources = json.loads((ROOT.parent/'codex_sme_evict_2026-10-06/sources_and_commands.json').read_text())
    original = sources['cases'][0]['command']
    cases = [('base_A',BASE,[],False),('off_A',NEW,[],False),
             ('base_L',BASE,['--score-logp'],False),('off_L',NEW,['--score-logp'],False),
             ('on_own',NEW,['--score-logp','--match-cstar','--match-cstar-e','--match-eps','0','--h-dirichlet','1','--birth-score','seq','--logp-eps','0.01'],False),
             ('on_keep',NEW,['--score-logp','--match-cstar','--match-cstar-e','--match-eps','0','--h-dirichlet','1','--birth-score','seq','--logp-eps','0.01'],True)]
    all_done = []
    for name,source,added,keep in cases:
        assert cpu_reading([])['total_compute_count'] < 8
        safe = conditions()
        assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
        case = WORK/name
        case.mkdir()
        command = list(original)
        command[3] = str(case/'output')
        command[command.index('--trial-count')+1] = '1740'
        command += ['--sme-evict-trial-cache']+added
        if keep: command[1] = str(ROOT/'material_keep_driver_01.py')
        save('current.json',{'at':now(),'case':name,'command':command,'cwd':str(source),'env':{'PYTHONHASHSEED':'0'}})
        start = time.monotonic()
        with (case/'run.log').open('w') as log:
            proc = subprocess.Popen(command,cwd=source,env=dict(os.environ,PYTHONHASHSEED='0'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            held = False
            while proc.poll() is None:
                time.sleep(2)
                safe = conditions()
                count = cpu_reading([])['total_compute_count']
                bad = safe['free_bytes'] < 18.5*2**30 or safe['swap_grew'] or safe['thermal_warning'] or count > 8
                if bad and not held:
                    os.killpg(proc.pid,signal.SIGSTOP)
                    held = True
                    save('resource_hold.json',{'at':now(),'case':name,'pid':proc.pid,'resources':safe,'count':count})
                elif held and safe['free_bytes'] >= 20*2**30 and not bad and count < 8:
                    os.killpg(proc.pid,signal.SIGCONT)
                    held = False
            code = proc.returncode
        save(name+'.json',{'at':now(),'exit':code,'wall_seconds':time.monotonic()-start,'command':command,'source':str(source)})
        if code != 0:
            raise RuntimeError('小走行の不通：'+name+'\n'+(case/'run.log').read_text()[-2500:])
        all_done.append(name)
        if name == 'off_A': compare(WORK/'base_A/output',case/'output','off_A')
        if name == 'off_L': compare(WORK/'base_L/output',case/'output','off_L')
        if name == 'on_keep': compare(WORK/'on_own/output',case/'output','material_same_flags')
    save('complete.json',{'at':now(),'passed':True,'completed':all_done})
    print(json.dumps({'at':now(),'passed':True,'completed':all_done},ensure_ascii=False),flush=True)
except Exception as e:
    WORK.mkdir(exist_ok=True)
    save('STOP.json',{'at':now(),'reason':str(e),'passed':False,'remaining_runs_not_started':True})
    print(str(e),flush=True)
    raise
