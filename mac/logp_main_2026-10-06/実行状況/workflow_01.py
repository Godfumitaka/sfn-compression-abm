"""関門後の160本を、条件順・種順・受付とCPU上限の中で実行する。"""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,signal,subprocess,sys,time,traceback
from common_01 import ROOT,PY,JOBS,save,now,conditions,cpu_reading,ps
PLAN=json.loads((ROOT/'sme.commands.json').read_text())
ORDER=list(dict.fromkeys(x['arm'] for x in PLAN));ACTIVE=[]
MAX_OWN=8 # 全体8コアと受付表の上限の中で、その時の空きを使う。
STOP=False;LAST_PROGRESS=time.monotonic()
class AdoptedProcess:
    def __init__(self,pid,marker):self.pid=pid;self.marker=marker
    def poll(self):
        rows=ps()
        if self.pid in rows and 'Z' not in rows[self.pid]['stat']:return None
        return 0 if self.marker.exists() else 1
    def wait(self):
        while self.poll() is None:time.sleep(15)
        return self.poll()
if (ROOT/'adopt_active.json').exists():
    for a in json.loads((ROOT/'adopt_active.json').read_text())['active']:
        f=Path(a['case']['folder']);marker=f/('run_complete.json' if a['mode']=='native' else 'analysis_complete.json')
        a['child']=AdoptedProcess(a.pop('claim_pid'),marker)
        a['log']=(f/(a['mode']+'_claim.log')).open('a')
        ACTIVE.append(a)
def record_job(x,mode):
    folder=Path(x['folder']);mem=2.0 if mode=='native' else 6.0
    # 同じ種類の完了済み実測に1.3倍を付ける。最初の解析は旧版4.94GBに余裕を付け6GB。
    values=[]
    for y in PLAN:
        f=Path(y['folder']);p=f/('run_complete.json' if mode=='native' else 'analysis_job/run_complete.json')
        if p.exists():
            v=json.loads(p.read_text());values.append(v['peak_rss_mb']/1000)
    if values:mem=max(2.0,math.ceil(max(values)*1.3*10)/10)
    mem=min(6.0,max(mem,2.0)) if mode=='native' else max(mem,2.0)
    path=folder/(mode+'_claim.log');assert not path.exists(),'二重に開始しない'
    cmd=[PY,JOBS,'run','--wait','--owner',f"SME logP主 {x['arm']} 種{x['seed']} {mode}",'--mem',str(mem),'--disk-path',str(folder),'--',PY,str(ROOT/'process_case_01.py'),str(folder),mode]
    log=path.open('x');child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
    item={'case':x,'mode':mode,'mem':mem,'child':child,'log':log,'paused':False}
    ACTIVE.append(item)
    save(folder/(mode+'_claim_pid.json'),{'pid':child.pid,'command':cmd,'at':now()})
def report(phase,text,proofs):
    (ROOT/(phase+'.md')).write_text(text);save(ROOT/(phase+'_proofs.json'),proofs)
    subprocess.run([PY,str(ROOT/'report_01.py'),phase],check=True)
def live_status(arm):
    return {'at':now(),'condition':arm,'total':160,'native_complete':sum((Path(x['folder'])/'run_complete.json').exists() for x in PLAN),'classified_complete':sum((Path(x['folder'])/'analysis_complete.json').exists() for x in PLAN),'active':[{'arm':a['case']['arm'],'seed':a['case']['seed'],'mode':a['mode'],'claim_pid':a['child'].pid,'mem':a['mem'],'cpu_paused':a['paused']} for a in ACTIVE],'resources':conditions()}
def monitor_cpu():
    reading=cpu_reading(ACTIVE)
    with (ROOT/'cpu.jsonl').open('a') as out:out.write(json.dumps(reading,ensure_ascii=False)+'\n')
    actual=reading['total_compute_count']
    for a in reversed(ACTIVE):
        folder=Path(a['case']['folder']);p=folder/('model_pid.json' if a['mode']=='native' else 'analysis_job/model_pid.json')
        if not p.exists():continue
        info=json.loads(p.read_text());pid=info['pid'];procs=ps()
        if pid not in procs or procs[pid]['pgid']!=pid:continue
        if actual>8 and not a['paused']:
            signal_group=signal.SIGSTOP;a['paused']=True;actual-=1
        elif actual<8 and a['paused']:
            signal_group=signal.SIGCONT;a['paused']=False;actual+=1
        else:continue
        __import__('os').killpg(pid,signal_group)
        with (folder/'cpu_pauses.jsonl').open('a') as out:out.write(json.dumps({'at':now(),'pgid':pid,'signal':signal_group.name,'reading':reading},ensure_ascii=False)+'\n')
    return reading
try:
    assert json.loads((ROOT/'gate.json').read_text())['passed']
    assert (ROOT/'reported_関門.json').exists()
    save(ROOT/'workflow_pid.json',{'pid':__import__('os').getpid(),'started':now()})
    # 対話中に始めた種1の読み取りを引き継ぐ。CPU上限に当たったときの受付は維持する。
    bootstrap=ROOT/'bootstrap_cpu_pause.json'
    if bootstrap.exists() and not (ROOT/'runs/w2_A_L50/seed001/analysis_complete.json').exists():
        boot=json.loads(bootstrap.read_text());pid=boot['own_pid'];paused=True
        while True:
            rows=ps()
            if pid not in rows or rows[pid]['ppid']!=boot['ppid'] or str(ROOT/'summarize_01.py') not in rows[pid]['command']:
                assert (ROOT/'runs/w2_A_L50/seed001/analysis_complete.json').exists(),'種1の読み取り集計が完了せず終了'
                break
            reading=cpu_reading([])
            own_present=pid in reading['external_compute_processes']
            external=reading['external_count']-int(own_present)
            permit=external<8
            resource=conditions()
            assert resource['free_bytes']>=18.5*2**30 and not resource['swap_grew'] and not resource['thermal_warning'],resource
            if permit and paused:
                __import__('os').kill(pid,signal.SIGCONT);paused=False
                with (ROOT/'bootstrap_cpu_events.jsonl').open('a') as out:out.write(json.dumps({'at':now(),'pid':pid,'signal':'SIGCONT','reading':reading})+'\n')
            elif not permit and not paused:
                __import__('os').kill(pid,signal.SIGSTOP);paused=True
                with (ROOT/'bootstrap_cpu_events.jsonl').open('a') as out:out.write(json.dumps({'at':now(),'pid':pid,'signal':'SIGSTOP','reading':reading})+'\n')
            save(ROOT/'status.json',{'at':now(),'condition':'w2_A_L50','native_complete':1,'classified_complete':0,'bootstrap_cpu_paused':paused,'resources':resource,'cpu':reading})
            if time.monotonic()-LAST_PROGRESS>=1800:
                phase='進み_'+datetime.now().strftime('%Y%m%d_%H%M%S');save(ROOT/(phase+'.json'),json.loads((ROOT/'status.json').read_text()))
                report(phase,'関門通過済み。種1は走行済み、読み取り集計中。全体8コアの上限でCPUの空きを待つ。残りの本は始めていない。\n',[phase+'.json']);LAST_PROGRESS=time.monotonic()
            time.sleep(15)
        save(ROOT/'bootstrap_complete.json',{'at':now(),'passed':True})
    for arm in ORDER:
        cases=[x for x in PLAN if x['arm']==arm]
        while not all((Path(x['folder'])/'analysis_complete.json').exists() for x in cases):
            assert not (ROOT/'report_stop.json').exists(),'報告のpushで停止'
            for a in list(ACTIVE):
                rc=a['child'].poll()
                if rc is None:continue
                a['log'].close();ACTIVE.remove(a)
                assert rc==0,(a['case']['arm'],a['case']['seed'],a['mode'],rc)
                folder=Path(a['case']['folder']);expected='run_complete.json' if a['mode']=='native' else 'analysis_complete.json'
                assert (folder/expected).exists(),(folder,expected)
                if a['mode']=='analysis':save(folder/'managed_complete.json',{'at':now(),'passed':True})
            assert not list(ROOT.glob('runs/*/*/resource_stop.json')) and not list(ROOT.glob('runs/*/*/analysis_job/resource_stop.json')),'資源の停止。後続を始めない'
            resources=conditions();assert resources['free_bytes']>=18.5*2**30 and not resources['swap_grew'] and not resources['thermal_warning'],resources
            reading=monitor_cpu()
            if len(ACTIVE)<MAX_OWN and reading['total_reserved_slots']<8 and resources['free_bytes']>=20*2**30:
                busy={(a['case']['arm'],a['case']['seed']) for a in ACTIVE}
                # 終わった本の分類を先に。解析は最初一本、実測が得られれば空きに二本まで。
                analyses=[x for x in cases if (Path(x['folder'])/'run_complete.json').exists() and not (Path(x['folder'])/'analysis_complete.json').exists() and (x['arm'],x['seed']) not in busy]
                native=[x for x in cases if not (Path(x['folder'])/'run_complete.json').exists() and (x['arm'],x['seed']) not in busy]
                n_analysis=sum(a['mode']=='analysis' for a in ACTIVE)
                if analyses and n_analysis<8:record_job(analyses[0],'analysis')
                elif native:record_job(native[0],'native')
            status=live_status(arm);save(ROOT/'status.json',status)
            if time.monotonic()-LAST_PROGRESS>=1800:
                phase='進み_'+datetime.now().strftime('%Y%m%d_%H%M%S')
                proof=phase+'.json';save(ROOT/proof,status)
                report(phase,f"条件{arm}。完了した走行{status['native_complete']}/160本、分類・再生・集計{status['classified_complete']}/160本。空き{status['resources']['free_bytes']/2**30:.3f}GiB。受付・CPUの記録は自分の出力先に保持。\n",[proof]);LAST_PROGRESS=time.monotonic()
            time.sleep(15)
        # 最後の解析の子の終了・releaseを待つ。次の条件を重ねない。
        for a in list(ACTIVE):
            rc=a['child'].wait();a['log'].close();assert rc==0;ACTIVE.remove(a)
        subprocess.run([PY,JOBS,'run','--wait','--owner','SME logP主 '+arm+' 条件の集計とSHA','--mem','2','--disk-path',str(ROOT/'runs'/arm),'--',PY,str(ROOT/'condition_summary_01.py'),arm],check=True)
        proofs=[]
        for x in cases:
            rel=Path(x['folder']).relative_to(ROOT)
            for name in ('command.json','run_complete.json','summary.json','births.json','trials.csv','artifacts_sha256.json','analysis_complete.json','all_files_sha256.json'):
                proofs.append(str(rel/name))
        proofs.append(arm+'_summary.json')
        report(arm,(ROOT/(arm+'.md')).read_text(),proofs)
    save(ROOT/'all_complete.json',{'passed':True,'at':now(),'runs':160,'seed_range':[1,20],'conditions':ORDER,'classification_and_replay_complete':160,'source_commit':'1838256b3fa9f81737d8b210e6ccb59c9d638a25'})
    report('全条件完了','8条件×種1〜20の160本、各1740試行。全本の台帳・side・保存状態を保持。全本の試行表・全ファイルsha256・選び間違い／区別の喪失・誕生のシールF/H/U・記憶総ビット・定義数を作成。保存状態の再解析は全件一致。結果の良し悪しは書かない。25番の控えを捨てる版での測定へ移る。\n',['all_complete.json'])
except Exception as e:
    save(ROOT/'workflow_stop.json',{'at':now(),'reason':str(e),'traceback':traceback.format_exc(),'active_claims':[a['child'].pid for a in ACTIVE]})
    # 不一致が出たら、自分の既に始まった本も保存したまま止める。外の処理は触らない。
    for a in ACTIVE:
        folder=Path(a['case']['folder']);p=folder/('model_pid.json' if a['mode']=='native' else 'analysis_job/model_pid.json')
        if p.exists():
            pid=json.loads(p.read_text())['pid']
            rows=ps()
            if pid in rows and rows[pid]['pgid']==pid and pid in __import__('common_01').descendants(a['child'].pid,rows):
                try:__import__('os').killpg(pid,signal.SIGSTOP)
                except ProcessLookupError:pass
    if not (ROOT/'report_stop.json').exists():
        try:report('停止_'+datetime.now().strftime('%Y%m%d_%H%M%S'),'停止の具体的な記録。\n\n```json\n'+(ROOT/'workflow_stop.json').read_text()+'```\n',['workflow_stop.json'])
        except Exception:pass
    raise
