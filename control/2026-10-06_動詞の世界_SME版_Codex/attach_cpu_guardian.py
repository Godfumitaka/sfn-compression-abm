"""同じ模型のPIDを保ち、停止中をCPU枠から除く監督へ引き継ぐ。模型・受付は再起動しない。"""
from pathlib import Path
import json
import os
import re
import shutil
import signal
import subprocess
import time

root=Path(__file__).resolve().parent
folder=root/'pilot_A_global_s01'
model=json.loads((folder/'pid.json').read_text())['pid']
assert model==json.loads((folder/'pid.json').read_text())['pgid']
limit=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.physicalcpu'],text=True))-2

def census():
    # commを末尾にして、空白を含む実行ファイル名も省略されない形で読む。
    executables={}
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,comm='],text=True).splitlines():
        at=line.strip().split(None,1)
        if len(at)==2:executables[int(at[0])]=at[1]
    rows={}
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,stat=,args='],text=True).splitlines():
        at=line.strip().split(None,5)
        if len(at)!=6:continue
        pid,parent,pgid,rss,state,command=at
        pid=int(pid);exe=executables.get(pid,'').lower()
        heavy=('python' in exe or 'pypy' in exe) and 'resource_tracker' not in command and 'jobs.py' not in command and (int(rss)>=102400 or 'spawn_main' in command)
        rows[pid]={'parent':int(parent),'pgid':int(pgid),'rss_bytes':int(rss)*1024,'state':state,'heavy':heavy,'command':command}
    return rows

rows=census();parent=rows[model]['parent']
assert str(root/'run_case.py') in rows[parent]['command'] and str(folder) in rows[parent]['command']
assert '/usr/bin/time' in rows[model]['command'] and str(folder/'output') in rows[model]['command']
assert os.getpgid(model)==model
worker_before=[pid for pid,r in rows.items() if r['pgid']==model and 'spawn_main' in r['command']]
assert len(worker_before)==1
attached=time.time()
# 自分の旧監督だけを待機させる。受付の親も模型のプロセス群も存続する。
os.kill(parent,signal.SIGSTOP)
(folder/'guardian_attachment.json').write_text(json.dumps({'attached_epoch':attached,'old_supervisor_pid':parent,
    'model_process_group_unchanged':model,'model_worker_pid_unchanged':worker_before[0],
    'CPU_policy':'重いPythonのうちSTAT T/ZをCPU枠から除く。RSSの予約は元のjobsのまま。'},ensure_ascii=False,indent=2)+'\n')
paused=any(r['state'].startswith('T') for r in rows.values() if r['pgid']==model)
with (folder/'resources_guardian.jsonl').open('x') as log:
    def record(event,**values):
        row={'event':event,'epoch_seconds':time.time(),'cpu_limit':limit,'census_policy':'stopped_and_zombie_excluded',**values}
        log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
    record('guardian_attached',old_supervisor_pid=parent,model_pid=model,worker_pid=worker_before[0])
    while True:
        rows=census()
        if model not in rows or rows[model]['state'].startswith('Z'):
            break
        outside=sum(r['heavy'] and not r['state'].startswith(('T','Z')) for pid,r in rows.items() if r['pgid']!=model and pid!=os.getpid())
        inside=sum(r['heavy'] and not r['state'].startswith('Z') for r in rows.values() if r['pgid']==model)
        thermal=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True)
        speed=re.search(r'CPU_Speed_Limit\s*=\s*(\d+)',thermal)
        warning=any('warning' in s.lower() and 'no ' not in s.lower() for s in thermal.splitlines()) or (speed is not None and speed.group(1)!='100')
        free=shutil.disk_usage(folder).free
        stop=outside+max(inside,1)>limit or warning or free<18.5*2**30
        values={'outside_heavy':outside,'inside_heavy':inside,'outside_stopped_heavy':sum(r['heavy'] and r['state'].startswith('T') for r in rows.values() if r['pgid']!=model),
                'own_rss_bytes':sum(r['rss_bytes'] for r in rows.values() if r['pgid']==model),
                'thermal_warning':warning,'free_disk_bytes':free}
        if stop!=paused:
            os.killpg(model,signal.SIGSTOP if stop else signal.SIGCONT)
            paused=stop;record('paused' if stop else 'resumed',**values)
        else:
            record('sample',own_paused=paused,**values)
        time.sleep(2)
    record('guardian_model_finished',model_pid=model)
# 元の親が子の終了コードとtime -lを回収する。模型はすでに終了している。
os.kill(parent,signal.SIGCONT)
for _ in range(300):
    if (folder/'result.json').exists():break
    time.sleep(.1)
assert (folder/'result.json').exists(),'元の監督の終了記録を待てなかった'
original=(folder/'resources.jsonl').read_text()
(folder/'resources_original_supervisor.jsonl').write_text(original)
oldrows=[json.loads(x) for x in original.splitlines()]
newrows=[json.loads(x) for x in (folder/'resources_guardian.jsonl').read_text().splitlines()]
merged=[r for r in oldrows if r.get('epoch_seconds',r.get('finished_epoch',float('inf')))<=attached]+newrows
start=None;paused_seconds=0
for row in merged:
    if row['event']=='paused':
        assert start is None
        start=row['epoch_seconds']
    elif row['event']=='resumed':
        assert start is not None
        paused_seconds+=row['epoch_seconds']-start;start=None
assert start is None
(folder/'resources.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in merged))
result=json.loads((folder/'result.json').read_text())
result['paused_seconds_original_supervisor']=result['paused_seconds']
result['paused_seconds']=paused_seconds
result['model_process_group_unchanged']=model
result['model_worker_pid_unchanged']=worker_before[0]
result['cpu_guardian_attachment_epoch']=attached
(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(folder/'guardian_complete.json').write_text(json.dumps({'completed':True,'paused_seconds':paused_seconds,'exit_code':result['exit_code']})+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
