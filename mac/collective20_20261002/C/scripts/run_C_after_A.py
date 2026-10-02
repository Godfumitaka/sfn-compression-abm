"""Aの完了を確認してからCの40集団を種順に実行。資源の観測と関門を通過した場合だけ次へ進む。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import gzip, hashlib, json, os, re, shutil, subprocess, time, traceback
import analyze_collective20 as analysis
import analyze_unselected as unselected
import report_collective_C as report
import verify_A_ready

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source';OUT=ROOT/'outputs_C';AN=ROOT/'analysis_C'
OLD=ROOT.parent/'codex_holes_collective_2026-10-01/collective'
OLDOUT=OLD/'outputs_recheck_2026-10-02'
OUT.mkdir(exist_ok=True);AN.mkdir(exist_ok=True)
EXPECTED='34667a55a4e68d7cda64614ead95e84a361b0118'

class Halt(Exception): pass
def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n')
def progress(message):
    with report.PROGRESS.open('a') as f: f.write(f'\n- {now()} 集団化拡張：{message}\n')
    print(message,flush=True)

def health():
    h={'time':now(),'disk_free_bytes':shutil.disk_usage(ROOT).free}
    for k,cmd in [('thermal',['/usr/bin/pmset','-g','therm']),('swap',['/usr/sbin/sysctl','vm.swapusage'])]:
        p=subprocess.run(cmd,capture_output=True,text=True)
        h[k]={'returncode':p.returncode,'output':p.stdout+p.stderr}
    m=re.search(r'used\s*=\s*([\d.]+)M',h['swap']['output']);h['swap_used_mib']=float(m[1]) if m else None
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,%cpu=,rss=,command='],capture_output=True,text=True,check=True)
    python={}
    for line in ps.stdout.splitlines():
        p=line.strip().split(None,4)
        if len(p)!=5: continue
        executable=Path(p[4].split()[0]).name.lower()
        if not executable.startswith(('python','pypy')): continue
        if str(ROOT) in p[4] or int(p[0])==os.getpid(): continue
        python[int(p[0])]={'pid':int(p[0]),'parent':int(p[1]),'cpu':float(p[2]),'rss_kib':int(p[3]),'command':p[4]}
    h['foreign_python_roots']=[p for p in python.values() if p['parent'] not in python]
    return h

initial=json.loads((ROOT/'first.measurement.json').read_text())
BASE_SWAP=initial['initial']['swap_used_mib']
LAST_PROGRESS=time.monotonic()
LAST_HEALTH=0
STOP=None

def observe(active,force=False):
    global LAST_HEALTH,LAST_PROGRESS,STOP
    if not force and time.monotonic()-LAST_HEALTH<10: return None
    h=health();h['active_populations']=active
    with (ROOT/'C_run_health.jsonl').open('a') as f: f.write(json.dumps(h,ensure_ascii=False)+'\n')
    LAST_HEALTH=time.monotonic()
    if h['thermal']['returncode']!=0 or h['swap']['returncode']!=0: STOP={'reason':'資源の状態を読めない','health':h}
    elif 'No thermal warning level has been recorded' not in h['thermal']['output']: STOP={'reason':'熱の警告','health':h}
    elif 'No performance warning level has been recorded' not in h['thermal']['output']: STOP={'reason':'性能の警告','health':h}
    elif h['disk_free_bytes']<15*1024**3+1024**3: STOP={'reason':'次の走行用1GiBを見込むと空き15GiB未満','health':h}
    elif h['swap_used_mib']>BASE_SWAP: STOP={'reason':'スワップの増加を観測したため、新しい走行を予防的に停止','baseline_swap_mib':BASE_SWAP,'health':h}
    if STOP: save(ROOT/'C_stopped.json',STOP)
    if time.monotonic()-LAST_PROGRESS>=1500:
        complete=len(list(AN.glob('*.unselected.json')))
        progress(f'Cの完了{complete}/40集団。実行中{active}。空き{h["disk_free_bytes"]/1024**3:.2f}GiB、スワップ{h["swap_used_mib"]:.2f}MiB。')
        LAST_PROGRESS=time.monotonic()
    return h

def analyze(name):
    run=OUT/name;dest=AN/(name+'.json');udest=AN/(name+'.unselected.json')
    if not dest.exists(): save(dest,analysis.one(run))
    p=json.loads(dest.read_text())
    if not udest.exists(): save(udest,unselected.one(run,p))
    report.publish_run(p)
    return p

def start(seed,mode):
    name=f'pilot_w2_{mode}_g{seed:03d}'
    assert not (OUT/name).exists(),('既存の記録を上書きしない',name)
    argv=json.loads((ROOT/'outputs'/(name+'.argv.json')).read_text())['argv']
    assert '--cf-learn' not in argv
    argv.append('--cf-learn')
    argv[3]=str(OUT/name);argv[argv.index('--v311c-runs')+1]=str(seed)
    save(OUT/(name+'.argv.json'),{'argv':argv,'cwd':str(SOURCE),'start':now()})
    stdout=(OUT/(name+'.stdout.log')).open('w');stderr=(OUT/(name+'.time_and_stderr.log')).open('w')
    p=subprocess.Popen(['/usr/bin/time','-l',*argv],cwd=SOURCE,stdout=stdout,stderr=stderr,start_new_session=True)
    print(json.dumps({'start':now(),'condition':name,'pid':p.pid},ensure_ascii=False),flush=True)
    return {'name':name,'pid':p.pid,'process':p,'stdout':stdout,'stderr':stderr,'start':time.monotonic()}

def finish(job):
    p=job['process'];job['stdout'].close();job['stderr'].close()
    stderr=(OUT/(job['name']+'.time_and_stderr.log')).read_text()
    m=re.search(r'(\d+)\s+maximum resident set size',stderr)
    save(OUT/(job['name']+'.resource.json'),{'elapsed_seconds':time.monotonic()-job['start'],
         'exit_code':p.returncode,'time_maximum_resident_bytes':int(m[1]) if m else None,'finished':now()})
    assert p.returncode==0,(job['name'],p.returncode,stderr[-2000:])
    value=analyze(job['name'])
    print(json.dumps({'finished':now(),'condition':job['name'],'doors':value['doors']},ensure_ascii=False),flush=True)

def seed_pair(seed,modes):
    active=[];queue=list(modes)
    while queue or active:
        h=observe(len(active),force=True)
        cap=min(2,max(0,3-len(h['foreign_python_roots'])))
        if STOP: queue=[]
        while queue and len(active)<cap and not STOP:
            active.append(start(seed,queue.pop(0)))
        save(ROOT/'C_running.json',{'time':now(),'seed':seed,'active':[{'condition':j['name'],'pid':j['pid']} for j in active],'pending':queue,'foreign_roots':h['foreign_python_roots']})
        finished=[j for j in active if j['process'].poll() is not None]
        for job in finished:
            active.remove(job);finish(job)
        if finished: report.main()
        if not active and not queue: break
        time.sleep(10)
    if STOP: raise Halt(STOP['reason'])

def processes():
    return subprocess.check_output(['/bin/ps','-axo','command='],text=True).splitlines()

def own_alive(filename):
    return any(Path(cmd.split()[0]).name.lower().startswith('python') and cmd.endswith(str(ROOT/filename)) for cmd in processes() if cmd.split())

def wait_A():
    announced=False
    last=time.monotonic()
    while True:
        if (ROOT/'failure.json').exists() or (ROOT/'stopped.json').exists():
            raise Halt('Aが停止したため、Cは開始しない。'+str(ROOT/'failure.json'))
        if (ROOT/'finished.json').exists() and not own_alive('run_collective20.py') and not own_alive('publish_when_finished.py'):
            ready=verify_A_ready.check()
            ready['verified_at']=now()
            save(ROOT/'A_ready_for_C.json',ready)
            report.save(report.DEST/'A_ready_for_C.json',ready)
            progress('Aの40集団・80本の台帳・139200課題と全件数の照合を確認。種1〜3の関門も一致。C開始の条件を満たした。')
            return
        if not announced:
            progress('C（--cf-learn）はAの40集団と関門・全数表の完了待ち。まだCの世界走行は開始していない。')
            announced=True
        if time.monotonic()-last>=1500:
            done=len(list((ROOT/'analysis').glob('*.unselected.json')))
            progress(f'Cは待機中。Aの完了{done}/40集団。')
            last=time.monotonic()
        save(ROOT/'C_queue.json',{'time':now(),'status':'Aの完了と全件数の照合待ち','arm':'C','group_seeds':list(range(1,21)),'modes':['no_comm','recvA'],'cf_learn':True})
        time.sleep(10)

def helper(filename,log):
    fo=(ROOT/log).open('w')
    p=subprocess.Popen(['/opt/homebrew/opt/python@3.12/bin/python3.12',str(ROOT/filename)],stdout=fo,stderr=subprocess.STDOUT,start_new_session=True)
    fo.close()
    return p

def main():
    global initial,BASE_SWAP,LAST_PROGRESS
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip();assert sha==EXPECTED
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=SOURCE,text=True).strip()
    wait_A()
    guard=helper('combined_parallel_C.py','combined_parallel_C.log')
    publisher=helper('publish_C_when_finished.py','publish_C.log')
    save(ROOT/'C_helpers.json',{'guard_pid':guard.pid,'publisher_pid':publisher.pid})
    # Cの最初の一本も並列1で測る。Aの実際の引数にcf-learnだけを加える。
    while True:
        h=observe(0,force=True)
        if STOP: raise Halt(STOP['reason'])
        if len(h['foreign_python_roots'])<3: break
        time.sleep(10)
    p=helper('measure_C_first.py','C_measure.log')
    while p.poll() is None:
        observe(1,force=True)
        time.sleep(10)
    assert p.returncode==0,('Cの最初の一本',p.returncode)
    initial=json.loads((ROOT/'C_first.measurement.json').read_text())
    BASE_SWAP=initial['initial']['swap_used_mib']
    hs=[json.loads(l) for l in (ROOT/'C_first.health.jsonl').read_text().splitlines()]
    assert initial['exit_code']==0
    if any(h['swap_used_mib']>BASE_SWAP or 'No thermal warning level has been recorded' not in h['thermal']['output'] for h in hs):
        save(ROOT/'C_stopped.json',{'reason':'Cの最初の一本で熱の警告またはスワップ増加','initial':initial,'health':hs})
        raise Halt('Cの最初の一本で熱の警告またはスワップ増加。新しい走行は開始しない。')
    save(OUT/'pilot_w2_no_comm_g001.resource.json',initial)
    analyze('pilot_w2_no_comm_g001');report.main()
    progress(f'Cの最初の一本を並列1で完了：{initial["elapsed_seconds"]:.3f}秒、最大常駐{initial["time_maximum_resident_bytes"]}バイト。')
    if STOP: raise Halt(STOP['reason'])
    LAST_PROGRESS=time.monotonic()
    seed_pair(1,['recvA'])
    for seed in range(2,21): seed_pair(seed,['no_comm','recvA'])
    result=report.main();assert result['complete'] and result['tasks']==139200,result
    save(ROOT/'C_finished.json',{'time':now(),**result})
    progress('C・世界2・種1〜20・通信あり/なしの40集団（80個体、139200課題）と数表の保存を完了。AとCの表を書いて終了。')

if __name__=='__main__':
    try: main()
    except BaseException as e:
        failure={'time':now(),'error':repr(e),'traceback':traceback.format_exc()}
        save(ROOT/'C_failure.json',failure)
        if not (ROOT/'C_stopped.json').exists(): save(ROOT/'C_stopped.json',failure)
        progress('停止：'+repr(e))
        try: report.main()
        except BaseException: pass
        raise
