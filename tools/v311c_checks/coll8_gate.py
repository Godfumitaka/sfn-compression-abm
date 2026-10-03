"""委任書2026-10-03：集団の種1〜3の配管関門だけ。最初の不成立で停止する。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import gzip, hashlib, json, os, re, signal, subprocess, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock, Event

SOURCE = Path(__file__).resolve().parents[2]
ROOT = SOURCE.parent
OUT = ROOT/'outputs'
EV = ROOT/'evidence'
PYTHON = '/opt/homebrew/opt/python@3.12/bin/python3.12'
PRICE = '0.01873710622997919'
FS = [0.1]*4+[0.9]*4
GROUPS = [0]*4+[1]*4
BASE = json.loads((EV/'reference.argv.json').read_text())['argv'][4:]
for flag in ('--v311c-f','--v311c-runs','--workers','--v311c-q','--v311c-recv','--trial-count','--v39-price','--e-price'):
    index = BASE.index(flag)
    del BASE[index:index+2]
BASE.remove('--v311c')
RESULT = (json.loads((EV/'gates.json').read_text()) if (EV/'gates.json').exists()
          else {'status':'running','checks':[], 'runs':[]})
MUTEX=RLock()
HALT=Event()
ACTIVE={}


def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def save(path, data): path.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
def checkpoint():
    with MUTEX:save(EV/'gates.json',RESULT)
def check(name, ok, **details):
    row={'name':name,'passed':bool(ok),**details}
    with MUTEX:RESULT['checks'].append(row);checkpoint()
    print(json.dumps(row,ensure_ascii=False),flush=True)
    if not ok:
        HALT.set()
        raise RuntimeError('関門不成立：'+name)


def parallel(function, values):
    # 最初の一本はこの関数を使わない。その後も今回の重い処理は最多2本。
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(function,v) for v in values]
        for future in as_completed(futures):
            try:future.result()
            except BaseException:
                HALT.set()
                for f in futures:f.cancel()
                raise


def health():
    h={'time':now(),'disk_free_bytes':__import__('shutil').disk_usage(ROOT).free}
    for name,cmd in [('memory',['vm_stat']),('swap',['sysctl','vm.swapusage']),('thermal',['pmset','-g','therm'])]:
        p=subprocess.run(cmd,capture_output=True,text=True)
        h[name]={'returncode':p.returncode,'output':p.stdout+p.stderr}
        if p.returncode: raise RuntimeError('機械状態の確認失敗：'+name)
    h['swap_mib']=float(re.search(r'used\s*=\s*([\d.]+)M',h['swap']['output'])[1])
    if 'No thermal warning level has been recorded' not in h['thermal']['output'] or 'No performance warning level has been recorded' not in h['thermal']['output']:
        raise RuntimeError('熱又は性能の警告：'+h['thermal']['output'])
    rows=[]
    for line in subprocess.check_output(['ps','-axo','pid=,ppid=,%cpu=,rss=,command='],text=True).splitlines():
        p=line.split(None,4)
        if len(p)==5: rows.append({'pid':int(p[0]),'ppid':int(p[1]),'cpu':float(p[2]),'rss_kib':int(p[3]),'command':p[4]})
    h['processes']=[r for r in rows if 'python' in r['command'].lower() or '/claude ' in r['command']]
    h['foreign_heavy']=[r for r in h['processes'] if str(ROOT) not in r['command'] and r['pid']!=os.getpid() and r['cpu']>=25 and ('Python -c from multiprocessing.spawn' in r['command'] or Path(r['command'].split()[0]).name.lower().startswith(('python','claude')))]
    return h,rows


def argv(name, count, *, fs=FS, groups=GROUPS, run=1, q=0.2, m=0.1, serial=True, shop=True, audit=True, lineage=True, no_tags=False, standalone_seed=None, solo_agent=None, source=SOURCE):
    a=[PYTHON,'tools/v3_run.py','config/sweep_shop_hide1_s1_2026-10-01.json',str(OUT/name),*BASE,
       '--trial-count',str(count),'--v39-price',PRICE,'--e-price',PRICE,'--workers','1','--seeds','1']
    if standalone_seed is None:
        a += ['--v311c','--v311c-f',','.join(map(str,fs)),'--v311c-groups',','.join(map(str,groups)),
              '--v311c-runs',str(run),'--v311c-q',str(q),'--v311c-m',str(m),'--v311c-recv','A','--v311c-b-n','8']
        a += [flag for flag,enabled in [('--v311c-serial',serial),('--v311c-probe-shop',shop),('--v311c-audit',audit),('--v311c-lineage',lineage),('--v311c-no-tags',no_tags)] if enabled]
    else:
        a[a.index('--seeds')+1]=str(standalone_seed)
        cfg=json.loads((source/'config/sweep_shop_hide1_s1_2026-10-01.json').read_text())
        cfg['seeds']={'start':standalone_seed,'count':1}
        config_path=EV/(name+'.config.json')
        save(config_path,cfg)
        a[2]=str(config_path)
    if solo_agent is not None:
        a[1]='tools/v311c_checks/coll8_solo.py'
    return a


def run_job(name, count, **kw):
    resource=EV/(name+'.resource.json')
    if resource.exists():
        measurement=json.loads(resource.read_text())
        if measurement['exitcode']!=0:raise RuntimeError('前の走行が不成立：'+name)
        path=OUT/name
        summaries=list((path/'comm').glob('*.summary.json'))
        if summaries:
            s=json.loads(summaries[0].read_text())
            check(name+' 完走',s['trials']==count and not s['errors'],trials=s['trials'],errors=s['errors'])
            check(name+' 受信の採点・名札費用',all(not a['v311c'][key] for a in s['agents'] for key in ('recv_score_changed','recv_merit_changed','dC_mismatch')))
            measurement['agent_peak_rss_mb_decimal']=[a['peak_rss_mb'] for a in s['agents']]
            save(resource,measurement)
        if not any(r['name']==name for r in RESULT['runs']):RESULT['runs'].append(measurement)
        checkpoint()
        return path
    if (OUT/name).exists(): raise RuntimeError('既存出力を上書きしない：'+name)
    own_cap=1 if kw.get('serial',True) else len(kw.get('fs',FS))
    while True:
        if HALT.is_set():raise RuntimeError('別の関門の不成立で停止')
        h,rows=health()
        with MUTEX:
            if len(h['foreign_heavy'])+sum(ACTIVE.values())+own_cap<=4:
                ACTIVE[name]=own_cap
                break
        print('他の重い処理の終了を待つ：'+name,flush=True);time.sleep(30)
    a=argv(name,count,**kw)
    environment=dict(os.environ)
    if kw.get('solo_agent') is not None:environment['COLL8_SOLO_AGENT']=str(kw['solo_agent'])
    job={'name':name,'argv':a,'cwd':str(kw.get('source',SOURCE)),'started':now(),'initial':h,
         'extra_env':({'COLL8_SOLO_AGENT':str(kw['solo_agent'])} if kw.get('solo_agent') is not None else {})}
    save(EV/(name+'.argv.json'),job)
    with (EV/'jobs.jsonl').open('a') as f:f.write(json.dumps({k:v for k,v in job.items() if k!='initial'},ensure_ascii=False)+'\n')
    print('開始 '+name,flush=True)
    start=time.monotonic();max_rss=0;observations=0
    with (OUT/(name+'.stdout.log')).open('w') as stdout,(OUT/(name+'.time.log')).open('w') as stderr:
        p=subprocess.Popen(['/usr/bin/time','-l',*a],cwd=job['cwd'],stdout=stdout,stderr=stderr,start_new_session=True,env=environment)
        job['pid']=p.pid
        try:
            while p.poll() is None:
                if HALT.is_set():raise RuntimeError('別の関門の不成立で停止')
                hh,rows=health()
                with MUTEX:active_cap=sum(ACTIVE.values())
                if len(hh['foreign_heavy'])+active_cap>4: raise RuntimeError('機械の並列上限：SME等を優先して今回の処理を停止')
                descendant={p.pid}
                for _ in range(5):
                    descendant.update(r['pid'] for r in rows if r['ppid'] in descendant)
                current=sum(r['rss_kib'] for r in rows if r['pid'] in descendant)*1024
                max_rss=max(max_rss,current);observations+=1
                hh.update(job=name,rss_sum_bytes=current,own_heavy_cap=active_cap)
                with MUTEX:
                    with (EV/'run-health.jsonl').open('a') as f:f.write(json.dumps(hh,ensure_ascii=False)+'\n')
                time.sleep(1)
        except BaseException:
            HALT.set()
            os.killpg(p.pid,signal.SIGTERM);p.wait();raise
        finally:
            with MUTEX:ACTIVE.pop(name,None)
    end,rows=health()
    measurement={'name':name,'elapsed_seconds':time.monotonic()-start,'exitcode':p.returncode,'finished':now(),
                 'rss_sum_peak_bytes':max_rss,'rss_sample_interval_seconds':1,'samples':observations,
                 'swap_start_mib':h['swap_mib'],'swap_end_mib':end['swap_mib']}
    save(EV/(name+'.resource.json'),measurement)
    if p.returncode: raise RuntimeError('走行失敗：'+name)
    path=OUT/name
    summaries=list((path/'comm').glob('*.summary.json'))
    if summaries:
        s=json.loads(summaries[0].read_text())
        check(name+' 完走',s['trials']==count and not s['errors'],trials=s['trials'],errors=s['errors'])
        check(name+' 受信の採点・名札費用',all(not a['v311c'][key] for a in s['agents'] for key in ('recv_score_changed','recv_merit_changed','dC_mismatch')))
        measurement['agent_peak_rss_mb_decimal']=[a['peak_rss_mb'] for a in s['agents']]
        save(EV/(name+'.resource.json'),measurement)
    RESULT['runs'].append(measurement);checkpoint()
    print('終了 '+name,flush=True)
    return path


def ledger_paths(path): return sorted((path/'ledgers/cells').glob('*/*.jsonl.gz'))
def body(path):
    digest=hashlib.sha256();count=0
    with gzip.open(path,'rb') as f:
        next(f)
        for line in f:digest.update(line);count+=1
    return {'sha256':digest.hexdigest(),'rows':count}

def event_hash(path):
    digest=hashlib.sha256();count=0
    for line in next((path/'comm').glob('run???.jsonl')).open('rb'):
        if json.loads(line)['kind']=='summary':continue
        digest.update(line);count+=1
    return {'sha256':digest.hexdigest(),'rows':count}

def compare(name, a, b, *, comm=False):
    aa={p.name:body(p) for p in ledger_paths(a)};bb={p.name:body(p) for p in ledger_paths(b)}
    check(name+' 台帳本体',aa==bb,left=aa,right=bb)
    if comm:check(name+' 通信事象',event_hash(a)==event_hash(b),left=event_hash(a),right=event_hash(b))


def minimal_rows(path):
    rows=[]
    with gzip.open(path,'rt') as f:
        next(f)
        for line in f:
            r=json.loads(line)
            rows.append({k:r[k] for k in ('f_realized','coin_t','f_fired','predicted_edge','prediction_kind','hit','outcome_category')})
    return rows


def inspect_population(name,path,fs,groups,count,q,m):
    ls=ledger_paths(path);check(name+' 個体数',len(ls)==len(fs))
    rr=[minimal_rows(p) for p in ls]
    check(name+' fの毎試行値',all(len(r)==count and all(x['f_realized']==f for x in r) for r,f in zip(rr,fs)),checked_rows=sum(map(len,rr)))
    correct=sum(bool(r['hit']) for rows in rr for r in rows)
    silence=sum(r['predicted_edge'] is None for rows in rr for r in rows)
    wrong=sum(r['predicted_edge'] is not None and not r['hit'] for rows in rr for r in rows)
    check(name+' 世界課題の分母',correct+silence+wrong==len(fs)*count,correct=correct,wrong=wrong,silence=silence,total=len(fs)*count)
    import csv
    answer_rows=[r for p in (path/'side').glob('*/*.answers.csv') for r in csv.DictReader(p.open())]
    sources=__import__('collections').Counter(r['source'].split('_')[0] for r in answer_rows if r['hit']=='0')
    check(name+' 答えの出どころの台帳照合',len(answer_rows)==correct+wrong and sum(sources.values())==wrong and set(sources)<=set('FHU'),answer_rows=len(answer_rows),wrong_sources=sources)
    comm=list(next((path/'comm').glob('run???.jsonl')).open())
    events=[json.loads(x) for x in comm]
    sent=[r for r in events if r['kind']=='bundle' and r.get('send')]
    recv=[r for r in events if r['kind']=='recv']
    check(name+' 送信配送受信・同試行・自己配送なし',len(sent)==len(recv) and sorted((r['bundle'],r['agent'],r['to'],r['t']) for r in sent)==sorted((r['bundle'],r['from'],r['agent'],r['t']) for r in recv) and all(r['agent']!=r['to'] for r in sent),sent=len(sent),recv=len(recv))
    spoken=[r for r in events if r['kind']=='bundle' and not r.get('empty')]
    check(name+' 黙りから送らない・答えは増やさない',all(rr[r['agent']][r['t']]['predicted_edge'] is not None and r['pred'][1:]==[rr[r['agent']][r['t']]['predicted_edge']['predicate'],rr[r['agent']][r['t']]['predicted_edge']['arguments']] for r in spoken),bundles=len(spoken))
    check(name+' 束の参照本数',all(r['final']==r['initial']-r['excluded']+r['added'] and len(r['relations'])==r['final'] for r in events if r['kind']=='bundle' and not r.get('empty')))
    if len(fs)>2:
        cross=sum(groups[r['agent']]!=groups[r['to']] for r in sent)
        if m==0:check(name+' m=0の組間配送',cross==0,cross=cross,total=len(sent))
        elif sent:
            # 事前固定99.9%中央二項範囲（両側の尾はそれぞれ0.0005）。
            import math
            n=len(sent)
            cdf=0.0;lo=None;hi=None
            for k in range(n+1):
                prob=math.exp(math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
                              + k*math.log(m)+(n-k)*math.log1p(-m))
                cdf+=prob
                if cdf>=0.0005 and lo is None:lo=k
                if cdf>=0.9995 and hi is None:hi=k;break
            check(name+' mの二項範囲',lo is not None and hi is not None and lo<=cross<=hi,cross=cross,total=n,ratio=cross/n,expected=m,central_999_range=[lo,hi])
    cats=['双方正解','同じ誤答','双方棄権','その他']
    items=next((e['items'] for e in events if e['kind']=='probe_items'),None)
    if items is not None:
        split={'within':{k:0 for k in cats},'cross':{k:0 for k in cats}}
        for e in events:
            if e['kind']!='probe':continue
            recalculated={k:0 for k in cats}
            for a in range(len(fs)):
                for b in range(a+1,len(fs)):
                    for k,it in enumerate(items):
                        x,y=e['answers'][a][k],e['answers'][b][k]
                        cat='双方正解' if x==it['held'] and y==it['held'] else '双方棄権' if x is None and y is None else '同じ誤答' if x is not None and x==y else 'その他'
                        recalculated[cat]+=1;split['within' if groups[a]==groups[b] else 'cross'][cat]+=1
            if recalculated!={k:e[k] for k in cats}:raise RuntimeError(name+' 試験四分類不一致')
        check(name+' 問い・対の再集計',len(items)==20 and sum(split['within'].values())+sum(split['cross'].values())==(count//100)*20*(len(fs)*(len(fs)-1)//2),split=split)
    births=[r for r in recv if r.get('result')=='誕生']
    check(name+' 報告の初期採点のsource',all(r.get('E',{}).get('source')=='報告' for r in births),births=len(births))
    check(name+' 未記載は反証・取消にしない',all(c[5]['取消']==1 for r in recv for c in (r.get('E') or {}).get('cands',[])))
    side_sources=[]
    no_learning_rows=0
    bad_no_learning_rows=[]
    for p in (path/'side').glob('*/*.jsonl'):
        for line in p.open():
            r=json.loads(line)
            if r.get('kind')=='v310be':
                if r.get('x')=='no_m1' and r.get('source') is None:
                    # 未学習の初期行はsourceの対象外。採点が0であることは別に確かめる。
                    no_learning_rows+=1
                    if r['R_B']!=0 or r['R_E']!=0:bad_no_learning_rows.append({'file':str(p),'trial':r['trial']})
                else:side_sources.append(r.get('source'))
    check(name+' 世界の学習のsource',side_sources and set(side_sources)=={'世界'} and not bad_no_learning_rows,
          world_learning_rows=len(side_sources),no_learning_rows=no_learning_rows,bad_no_learning_rows=bad_no_learning_rows)
    stats={'name':name,'q':q,'m':m,'sent':len(sent),'within':sum(groups[r['agent']]==groups[r['to']] for r in sent),
           'cross':sum(groups[r['agent']]!=groups[r['to']] for r in sent),'receive_results':__import__('collections').Counter(r.get('result') for r in recv),
           'world':{'total':len(fs)*count,'correct':correct,'wrong':wrong,'silence':silence,'wrong_sources':sources}}
    save(EV/(name+'.counts.json'),stats)
    return [[(r['coin_t'],r['f_fired'],r['f_realized']) for r in rows] for rows in rr]


def main():
    if RESULT['status']=='stopped':raise RuntimeError('関門不成立後は自動で再開しない')
    if RESULT['status']=='passed':return
    OUT.mkdir(exist_ok=True);EV.mkdir(exist_ok=True);checkpoint()
    # 同時実行は二体のみ。八体の最初の走行より前に直列の配管を検査する。
    p=run_job('serial2_simultaneous',100,fs=[0.1,0.9],groups=[0,1],serial=False)
    s=run_job('serial2_serial',100,fs=[0.1,0.9],groups=[0,1])
    compare('直列と同時（2体）',p,s,comm=True)
    first=run_job('no_comm_r1',1740,q=0,m=0)
    coins=inspect_population('no_comm_r1',first,FS,GROUPS,1740,0,0)
    old=run_job('default2_baseline',200,fs=[0.1,0.9],groups=[0,1],serial=False,shop=False,audit=False,lineage=False,source=ROOT/'baseline')
    new=run_job('default2_current',200,fs=[0.1,0.9],groups=[0,1],serial=False,shop=False,audit=False,lineage=False)
    compare('追加旗が全てオフと土台（2体）',old,new,comm=True)
    def solo1(i):
        solo=run_job(f'solo_r1_a{i}',1740,solo_agent=i,q=0,m=0)
        check(f'通信なし8体と単独：個体{i}',body(ledger_paths(first)[i])==body(ledger_paths(solo)[0]),collective=body(ledger_paths(first)[i]),solo=body(ledger_paths(solo)[0]))
    parallel(solo1,range(8))
    # 機能を全部切った8体と固定した個体版（短い配管の試行、全個体を比較）。
    off=run_job('off8',100,fs=[0.5]*8,groups=GROUPS,q=0,m=0,no_tags=True,shop=False,audit=False,lineage=False)
    for i in range(8):
        baseline=run_job(f'baseline_a{i}',100,standalone_seed=1+1000*i,source=ROOT/'baseline')
        check(f'集団化全部オフと固定個体版：個体{i}',body(ledger_paths(off)[i])==body(ledger_paths(baseline)[0]))
    # 記録の旗・新しい試験の旗が模型へ戻らないこと。受信・誕生もある腕で測る。
    plain=run_job('record8_plain',200,shop=False,audit=True,lineage=False)
    logged=run_job('record8_logged',200)
    compare('お店試験・系譜の非干渉（8体）',plain,logged)
    state_plain=next((plain/'comm').glob('*.state.jsonl')).read_bytes()
    state_logged=next((logged/'comm').glob('*.state.jsonl')).read_bytes()
    check('お店試験・系譜の本走行乱数',state_plain==state_logged)
    no_audit=run_job('record8_no_audit',200,audit=False)
    compare('状態指紋の非干渉（8体）',logged,no_audit,comm=True)
    for run in (1,2,3):
        if run==1:nocomm=first;ref=coins
        else:
            nocomm=run_job(f'no_comm_r{run}',1740,run=run,q=0,m=0)
            ref=inspect_population(f'no_comm_r{run}',nocomm,FS,GROUPS,1740,0,0)
            def solo_later(i):
                solo=run_job(f'solo_r{run}_a{i}',1740,run=run,solo_agent=i,q=0,m=0)
                check(f'通信なし8体と単独：種{run}個体{i}',body(ledger_paths(nocomm)[i])==body(ledger_paths(solo)[0]),
                      collective=body(ledger_paths(nocomm)[i]),solo=body(ledger_paths(solo)[0]))
            parallel(solo_later,range(8))
        def communication(m):
            name=f'comm_m{m}_r{run}'
            pop=run_job(name,1740,run=run,m=m)
            current=inspect_population(name,pop,FS,GROUPS,1740,0.2,m)
            check(name+' 開示の抽選の並び',current==ref,agents=8,trials_per_agent=1740)
        parallel(communication,(0,0.1,0.3))
    RESULT['status']='passed';RESULT['finished']=now();checkpoint()

if __name__=='__main__':
    try:main()
    except BaseException as e:
        RESULT.update(status='stopped',finished=now(),reason=str(e),traceback=traceback.format_exc());checkpoint()
        print(RESULT['traceback'],flush=True);sys.exit(1)
