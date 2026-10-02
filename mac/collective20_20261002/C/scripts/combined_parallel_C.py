"""他のPython処理を含む上限に合わせ、自分の処理だけを一時待機する。模型を編集しない。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, os, re, shutil, signal, subprocess, time

ROOT=Path(__file__).resolve().parent
DEST=ROOT.parent/'codex_worldv4_2026-10-01/results/mac/collective20_20261002/C'
DEST.mkdir(parents=True,exist_ok=True)
(DEST/'scripts').mkdir(exist_ok=True)
shutil.copyfile(__file__,DEST/'scripts/combined_parallel_C.py')
paused=set()

def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def snapshot():
    rows={}
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,stat=,%cpu=,command='],text=True).splitlines():
        p=line.strip().split(None,5)
        if len(p)!=6: continue
        rows[int(p[0])]={'pid':int(p[0]),'parent':int(p[1]),'pgid':int(p[2]),'stat':p[3],'cpu':float(p[4]),'command':p[5]}
    foreign={p:r for p,r in rows.items() if Path(r['command'].split()[0]).name.lower().startswith('python') and str(ROOT) not in r['command']}
    foreign_roots=[r for r in foreign.values() if r['parent'] not in foreign]
    groups={}
    for r in rows.values():
        executable=Path(r['command'].split()[0]).name.lower()
        if not (executable.startswith('python') or executable=='time'): continue
        if str(ROOT) not in r['command'] or 'tools/v3_run.py' not in r['command']: continue
        name=re.search(r'pilot_w2_(?:no_comm|recvA)_g\d{3}',r['command'])
        if name: groups[('group',r['pgid'])]={'key':('group',r['pgid']),'name':name[0]}
    controller=[r for r in rows.values() if Path(r['command'].split()[0]).name.lower().startswith('python') and r['command'].endswith(str(ROOT/'run_C_after_A.py'))]
    assert len(controller)<=1
    jobs=list(groups.values())
    if controller:
        r=controller[0];key=('pid',r['pid'])
        # 集計中のまとめ役も重い処理として数える。低いCPU使用率の間は待機・監視だけ。
        if r['cpu']>=20 or key in paused:
            jobs.insert(0,{'key':key,'name':'記録の集計','cpu':r['cpu']})
    return foreign_roots,groups,controller,jobs

def set_wait(job,wait):
    key=job['key'];kind,ident=key
    sig=signal.SIGSTOP if wait else signal.SIGCONT
    try:
        if kind=='group': os.killpg(ident,sig)
        else: os.kill(ident,sig)
    except ProcessLookupError:
        paused.discard(key);return
    if wait: paused.add(key)
    else: paused.discard(key)
    with (DEST/'combined_parallel.jsonl').open('a') as f:
        f.write(json.dumps({'time':now(),'event':'待機' if wait else '再開','name':job['name'],'target':key},ensure_ascii=False)+'\n')

last=0
try:
    while True:
        foreign,groups,controller,jobs=snapshot()
        live=set(groups)|{('pid',r['pid']) for r in controller}
        paused.intersection_update(live)
        if not controller and not groups: break
        capacity=max(0,3-len(foreign))
        for index,job in enumerate(jobs):
            wait=index>=capacity
            if wait!=(job['key'] in paused): set_wait(job,wait)
        if time.monotonic()-last>=10:
            record={'time':now(),'foreign_python_jobs':len(foreign),
                    'own_running_jobs':sum(j['key'] not in paused for j in jobs),
                    'own_model_populations':len(groups),'paused':[list(k) for k in sorted(paused)]}
            with (DEST/'combined_parallel.jsonl').open('a') as f: f.write(json.dumps(record,ensure_ascii=False)+'\n')
            last=time.monotonic()
        time.sleep(2)
finally:
    # 自分の監視だけが終了した場合にも、待機中の自分の処理を置き去りにしない。
    for kind,ident in list(paused):
        try:
            if kind=='group': os.killpg(ident,signal.SIGCONT)
            else: os.kill(ident,signal.SIGCONT)
        except ProcessLookupError: pass
