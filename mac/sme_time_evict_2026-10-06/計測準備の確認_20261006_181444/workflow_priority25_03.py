"""25′の二本を優先し、log Pの新規走行と再生分類の停止を保つ。"""
from pathlib import Path
from datetime import datetime
import json,os,signal,subprocess,sys,time,traceback
ROOT=Path(__file__).resolve().parent
MAIN=ROOT.parent/'codex_logp_main_2026-10-06';sys.path.insert(0,str(MAIN))
from common_01 import PY,JOBS,save,now,ps,descendants,conditions,cpu_reading
PLAN=json.loads((ROOT/'profile_plan_02.json').read_text());LAST_REPORT=time.monotonic()
def report(phase,text,proofs):
    (ROOT/(phase+'.md')).write_text(text);save(ROOT/(phase+'_proofs.json'),proofs)
    subprocess.run([PY,str(ROOT/'report_02.py'),phase],check=True)
def progress_if_due():
    global LAST_REPORT
    if time.monotonic()-LAST_REPORT<1800:return
    phase='計測の進み_'+datetime.now().strftime('%Y%m%d_%H%M%S')
    status=json.loads((ROOT/'priority_status.json').read_text())
    save(ROOT/(phase+'.json'),status)
    report(phase,f"25′の{status.get('case','二本')}を計測または受付待機中。log Pの新規走行と再生分類は、再開の指示まで停止。確認した状態を添付。\n",[phase+'.json'])
    LAST_REPORT=time.monotonic()
def registered(args,folder,memory,owner,case):
    global LAST_REPORT
    while True:
        resource=conditions();reading=cpu_reading([])
        save(ROOT/'priority_status.json',{'at':now(),'state':'pending','case':case,'claim_pid':None,'resources':resource,'cpu':reading})
        assert not resource['swap_grew'] and not resource['thermal_warning'],resource
        progress_if_due()
        if resource['free_bytes']>=20*2**30 and reading['total_compute_count']<8:break
        time.sleep(15)
    cmd=[PY,JOBS,'run','--wait','--owner',owner,'--mem',str(memory),'--disk-path',str(folder),'--',*args]
    with (folder/'claim.log').open('x') as out:
        child=subprocess.Popen(cmd,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
        save(folder/'claim_pid.json',{'pid':child.pid,'command':cmd,'at':now()})
        paused=False;last_saved=0
        while child.poll() is None:
            resource=conditions();reading=cpu_reading([{'child':child}]);model=folder/'model_pid.json'
            if model.exists():
                pid=json.loads(model.read_text())['pid'];rows=ps()
                if pid in rows and pid in descendants(child.pid,rows) and rows[pid]['pgid']==pid:
                    if reading['total_compute_count']>8 and not paused:
                        os.killpg(pid,signal.SIGSTOP);paused=True
                        with (folder/'cpu_pauses.jsonl').open('a') as f:f.write(json.dumps({'at':now(),'signal':'SIGSTOP','pgid':pid,'cpu':reading})+'\n')
                    elif reading['total_compute_count']<8 and paused:
                        os.killpg(pid,signal.SIGCONT);paused=False
                        with (folder/'cpu_pauses.jsonl').open('a') as f:f.write(json.dumps({'at':now(),'signal':'SIGCONT','pgid':pid,'cpu':reading})+'\n')
            if time.monotonic()-last_saved>15:
                status={'at':now(),'state':'registered_or_waiting','case':case,'claim_pid':child.pid,'cpu_paused':paused,'resources':resource,'cpu':reading}
                save(ROOT/'priority_status.json',status)
                with (folder/'cpu.jsonl').open('a') as f:f.write(json.dumps(status,ensure_ascii=False)+'\n')
                last_saved=time.monotonic()
            assert not (folder/'resource_stop.json').exists(),'資源の停止。後続を開始しない'
            if resource['free_bytes']<18.5*2**30 or resource['swap_grew'] or resource['thermal_warning']:
                if model.exists():
                    rows=ps();pid=json.loads(model.read_text())['pid']
                    if pid in rows and pid in descendants(child.pid,rows) and rows[pid]['pgid']==pid:os.killpg(pid,signal.SIGSTOP)
                raise AssertionError(resource)
            progress_if_due()
            time.sleep(2)
    assert child.returncode==0,(owner,child.returncode)
try:
    save(ROOT/'workflow_priority25_started.json',{'at':now(),'pid':os.getpid(),'cases':[x['name'] for x in PLAN],'priority':25,'logp_new_runs_and_replay_held':True})
    for case in PLAN:
        folder=Path(case['folder'])
        registered([PY,str(ROOT/'run_case_02.py'),str(folder)],folder,case['memory_reservation_gb'],'SME25 '+case['name'],case['name'])
        assert (folder/'run_complete.json').exists()
        for name,script in (('compare_02','compare_profile_02.py'),('analyze_02','analyze_profile_02.py')):
            job=folder/name;job.mkdir(exist_ok=False)
            registered([PY,str(ROOT/script),case['name']],job,2.5,'SME25 '+case['name']+' '+name,case['name']+' '+name)
        subprocess.run([PY,str(ROOT/'finish_profile_02.py'),case['name']],check=True)
        report(case['name'],(ROOT/(case['name']+'.md')).read_text(),json.loads((ROOT/(case['name']+'_proofs.json')).read_text()))
    save(ROOT/'computation_complete.json',{'at':now(),'passed':True,'cases':[x['name'] for x in PLAN]})
    save(ROOT/'priority_status.json',{'at':now(),'state':'computation_complete','claim_pid':None})
    subprocess.run([PY,str(ROOT/'finish_proposals_02.py')],check=True)
    report('二本の内訳と案',(ROOT/'二本の内訳と案.md').read_text(),json.loads((ROOT/'二本の内訳と案_proofs.json').read_text()))
    save(ROOT/'all_complete_priority25.json',{'at':now(),'passed':True,'measured_trials':[1740,1000],'compared_native_records':True,'model_changed':False,'reported':json.loads((ROOT/'reported_二本の内訳と案.json').read_text())})
except Exception as e:
    save(ROOT/'workflow_priority25_stop.json',{'at':now(),'reason':str(e),'traceback':traceback.format_exc(),'model_changed':False})
    if not (ROOT/'report_stop.json').exists():
        try:report('計測停止_'+datetime.now().strftime('%Y%m%d_%H%M%S'),'25番の計測停止の事実。\n\n```json\n'+(ROOT/'workflow_priority25_stop.json').read_text()+'```\n',['workflow_priority25_stop.json'])
        except Exception:pass
    raise
