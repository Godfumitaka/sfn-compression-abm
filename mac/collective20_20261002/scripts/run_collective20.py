"""Aの40集団を種順に実行。資源の観測と関門を通過した場合だけ次へ進む。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import gzip, hashlib, json, os, re, shutil, subprocess, time, traceback
import analyze_collective20 as analysis
import analyze_unselected as unselected
import report_collective20 as report

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source';OUT=ROOT/'outputs';AN=ROOT/'analysis'
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
    with (ROOT/'run_health.jsonl').open('a') as f: f.write(json.dumps(h,ensure_ascii=False)+'\n')
    LAST_HEALTH=time.monotonic()
    if h['thermal']['returncode']!=0 or h['swap']['returncode']!=0: STOP={'reason':'資源の状態を読めない','health':h}
    elif 'No thermal warning level has been recorded' not in h['thermal']['output']: STOP={'reason':'熱の警告','health':h}
    elif 'No performance warning level has been recorded' not in h['thermal']['output']: STOP={'reason':'性能の警告','health':h}
    elif h['disk_free_bytes']<15*1024**3+1024**3: STOP={'reason':'次の走行用1GiBを見込むと空き15GiB未満','health':h}
    elif h['swap_used_mib']>BASE_SWAP: STOP={'reason':'スワップの増加を観測したため、新しい走行を予防的に停止','baseline_swap_mib':BASE_SWAP,'health':h}
    if STOP: save(ROOT/'stopped.json',STOP)
    if time.monotonic()-LAST_PROGRESS>=1500:
        complete=len(list(AN.glob('*.unselected.json')))
        progress(f'Aの完了{complete}/40集団。実行中{active}。空き{h["disk_free_bytes"]/1024**3:.2f}GiB、スワップ{h["swap_used_mib"]:.2f}MiB。')
        LAST_PROGRESS=time.monotonic()
    return h

def analyze(name):
    run=OUT/name;dest=AN/(name+'.json');udest=AN/(name+'.unselected.json')
    if not dest.exists(): save(dest,analysis.one(run))
    p=json.loads(dest.read_text())
    if not udest.exists(): save(udest,unselected.one(run,p))
    report.publish_run(p)
    return p

def ledger_bodies(run):
    result={}
    for path in sorted((run/'ledgers/cells').glob('*/*.jsonl.gz')):
        b=report.body(path);result[path.name]=b['body_sha256']
    assert len(result)==2
    return result

def communication_body(run,seed):
    h=hashlib.sha256();n=0
    with (run/'comm'/f'run{seed:03d}.jsonl').open('rb') as f:
        for line in f:
            if json.loads(line)['kind']=='summary': continue
            h.update(line);n+=1
    return {'sha256':h.hexdigest(),'rows':n}

def gate():
    checks=[]
    for seed in range(1,4):
        for mode in ('no_comm','recvA'):
            name=f'pilot_w2_{mode}_g{seed:03d}'
            p=json.loads((AN/(name+'.json')).read_text())
            old=json.loads((OLD/'pilot_analysis_20261002'/(name+'.json')).read_text())
            for k in ('doors','exception_flow','abstain_reasons','common','prediction_bundle_mismatches'):
                assert p[k]==old[k],(name,k,p[k],old[k])
            bodies=ledger_bodies(OUT/name)
            assert bodies==ledger_bodies(OLDOUT/name),(name,'台帳本体')
            cb=communication_body(OUT/name,seed)
            assert cb==communication_body(OLDOUT/name,seed),(name,'通信の元記録')
            checks.append({'condition':name,'counts_match':True,'ledger_bodies':bodies,'communication':cb})
    save(ROOT/'gate_passed.json',{'time':now(),'populations':6,'ledgers':12,'checks':checks,
                                 'exception_door_errors':{'no_comm':43,'recvA':38}})
    progress('種1〜3の関門を通過。前の試しと6集団の全件数、12本の台帳本体、6集団の通信の元記録が一致。例外ドアの誤答：なし43・あり38。')

def start(seed,mode):
    name=f'pilot_w2_{mode}_g{seed:03d}'
    assert not (OUT/name).exists(),('既存の記録を上書きしない',name)
    argv=json.loads((OLDOUT/f'pilot_w2_{mode}_g001.argv.json').read_text())['argv']
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
        save(ROOT/'running.json',{'time':now(),'seed':seed,'active':[{'condition':j['name'],'pid':j['pid']} for j in active],'pending':queue,'foreign_roots':h['foreign_python_roots']})
        finished=[j for j in active if j['process'].poll() is not None]
        for job in finished:
            active.remove(job);finish(job)
        if finished: report.main()
        if not active and not queue: break
        time.sleep(10)
    if STOP: raise Halt(STOP['reason'])

def main():
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip();assert sha==EXPECTED
    assert not subprocess.check_output(['git','diff','--name-only'],cwd=SOURCE,text=True).strip()
    hs=[json.loads(l) for l in (ROOT/'first.health.jsonl').read_text().splitlines()]
    assert initial['exit_code']==0
    assert all(h['swap_used_mib']<=BASE_SWAP and 'No thermal warning level has been recorded' in h['thermal']['output'] for h in hs)
    save(OUT/'pilot_w2_no_comm_g001.resource.json',initial)
    first=analyze('pilot_w2_no_comm_g001')
    old=json.loads((OLD/'pilot_analysis_20261002/pilot_w2_no_comm_g001.json').read_text())
    assert first['doors']==old['doors'],('最初の一本',first['doors'],old['doors'])
    report.main()
    progress(f'最初の一本を並列1で完了：{initial["elapsed_seconds"]:.3f}秒、最大常駐{initial["time_maximum_resident_bytes"]}バイト。熱警告・スワップ増加なし。種1・通信なしのドア件数一致。')
    seed_pair(1,['recvA'])
    for seed in range(2,21):
        if seed==4:
            gate();report.main()
        seed_pair(seed,['no_comm','recvA'])
    result=report.main();assert result['complete'] and result['tasks']==139200,result
    save(ROOT/'finished.json',{'time':now(),**result})
    progress('A・世界2・種1〜20・通信あり/なしの40集団（80個体、139200課題）と数表の保存を完了。Cは実施せず、表を書いて終了。')

if __name__=='__main__':
    try: main()
    except BaseException as e:
        failure={'time':now(),'error':repr(e),'traceback':traceback.format_exc()}
        save(ROOT/'failure.json',failure)
        if not (ROOT/'stopped.json').exists(): save(ROOT/'stopped.json',failure)
        progress('停止：'+repr(e))
        try: report.main()
        except BaseException: pass
        raise
