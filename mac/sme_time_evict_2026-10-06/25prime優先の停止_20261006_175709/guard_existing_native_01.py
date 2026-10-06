"""新しい本と再生を始めず、既存のnative一本だけを資源上限で完了させる。"""
from pathlib import Path
from datetime import datetime
import json,os,signal,sys,time
ROOT=Path(__file__).resolve().parent;MAIN=ROOT.parent/'codex_logp_main_2026-10-06'
sys.path.insert(0,str(MAIN));from common_01 import save,now,ps,descendants,conditions,cpu_reading
proof=json.loads((ROOT/'logp_hold_25prime_01.json').read_text());native=[a for a in proof['active'] if a['mode']=='native'];LAST=0
save(ROOT/'native_finish_guard_started.json',{'at':now(),'pid':os.getpid(),'new_jobs_started':False})
while native:
    rows=ps();alive=[]
    for a in native:
        pid=a['claim_pid'];folder=MAIN/'runs'/a['arm']/f"seed{a['seed']:03d}"
        if pid not in rows or 'Z' in rows[pid]['stat']:
            assert (folder/'run_complete.json').exists(),'既存のnativeが完了せず終了'
            continue
        assert str(MAIN/'process_case_01.py') in rows[pid]['command'];alive.append(a)
        cpu=cpu_reading([]);resource=conditions();model=a['pgid']
        if model in rows and model in descendants(pid,rows) and rows[model]['pgid']==model:
            paused='T' in rows[model]['stat']
            permitted=cpu['total_compute_count']<8 and resource['free_bytes']>=18.5*2**30 and not resource['swap_grew'] and not resource['thermal_warning']
            if paused and permitted:os.killpg(model,signal.SIGCONT);sent='SIGCONT'
            elif not paused and (cpu['total_compute_count']>8 or resource['free_bytes']<18.5*2**30 or resource['swap_grew'] or resource['thermal_warning']):os.killpg(model,signal.SIGSTOP);sent='SIGSTOP'
            else:sent=None
            if sent:
                with (folder/'user_hold_pauses.jsonl').open('a') as out:out.write(json.dumps({'at':now(),'signal':sent,'pgid':model,'reason':'既存のnativeのみ完了可。新しい開始なし。CPU・資源上限による待機','cpu':cpu,'resources':resource},ensure_ascii=False)+'\n')
    native=alive
    if time.monotonic()-LAST>=15:
        plan=json.loads((MAIN/'sme.commands.json').read_text())
        save(MAIN/'status.json',{'at':now(),'condition':'w2_A_L50','user_hold_25prime':True,'requires_human_resume':True,'total':160,'native_complete':sum((Path(x['folder'])/'run_complete.json').exists() for x in plan),'classified_complete':sum((Path(x['folder'])/'analysis_complete.json').exists() for x in plan),'active_native_allowed_to_finish':native,'paused_replay':[a for a in proof['active'] if a['mode']=='analysis'],'resources':conditions()});LAST=time.monotonic()
    if native:time.sleep(2)
save(ROOT/'existing_native_finish_complete.json',{'at':now(),'passed':True,'new_jobs_started':False,'replay_paused':True,'human_resume_required':True})
