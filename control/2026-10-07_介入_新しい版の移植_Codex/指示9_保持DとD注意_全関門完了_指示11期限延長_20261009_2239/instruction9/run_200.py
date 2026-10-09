"""指示9の限定200試行。受付内でCPU枠を確かめ、保存済み命令だけを実行する。"""
from pathlib import Path
import json,sys,subprocess,os,time,datetime,hashlib,resource
port=Path(__file__).resolve().parents[1];sys.path.insert(0,str(port))
from admission_guard import census
admitted_at_epoch=time.time()
label=sys.argv[1];spec=json.loads((port/'instruction9/commands.json').read_text())[label]
dest=port/'instruction9'/label;dest.mkdir(exist_ok=False)
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds')
def save(name,data):(dest/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
protected={}
for root in (port/'instruction5/gate_200_01',port/'instruction3/variants_tests_01',port/'instruction8/variants_tests_01'):
    protected[str(root)]=hashes(root)
for name in ('tools/intervention46_variants.py','tools/test_intervention46_variants.py','tools/useforget.py','tools/v39.py','tools/attnsme.py','tools/cstar_runtime.py'):
    p=port/'source_e9'/name;protected[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
save('protected_before.json',protected)
waiting=time.perf_counter()
while True:
    rows,active,paused=census();parents=set()
    for pid in active|paused:
        p=rows[pid]['parent'];seen=set()
        while p in rows and p not in seen:
            seen.add(p)
            if p in active|paused:parents.add(p)
            p=rows[p]['parent']
    active-=parents;paused-=parents
    if len(active)<8:break
    save('cpu_wait.json',dict(at_jst=now(),active=len(active),paused=len(paused)))
    time.sleep(15)
save('before_start.json',dict(at_jst=now(),active=len(active),paused=len(paused),processes=[dict(pid=p,**rows[p]) for p in sorted(active|paused)],excluded_parents=sorted(parents)))
status=dict(status='running',label=label,pid=os.getpid(),started_at_jst=now(),started_at_epoch=time.time(),admitted_at_epoch=admitted_at_epoch,admission_wait_seconds=admitted_at_epoch-float(os.environ['INTERVENTION_ADMISSION_SUBMITTED_EPOCH']) if 'INTERVENTION_ADMISSION_SUBMITTED_EPOCH' in os.environ else None,cpu_wait_seconds=time.perf_counter()-waiting,formal_3b_material=False,command=spec)
save('status.json',status);start=time.perf_counter()
env=dict(os.environ,**spec['environment'],PYTHONDONTWRITEBYTECODE='1')
with (dest/'model.log').open('xb') as log:
    p=subprocess.run(spec['argv'],cwd=spec['cwd'],env=env,stdout=log,stderr=subprocess.STDOUT)
after={}
for name,value in protected.items():
    path=Path(name);after[name]=hashes(path) if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
save('protected_after.json',after)
status.update(status='completed' if p.returncode==0 and after==protected else 'stopped',exit_code=p.returncode,seconds=time.perf_counter()-start,ended_at_jst=now(),protected_unchanged=after==protected,peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,children_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime)
save('status.json',status);print(json.dumps(status,ensure_ascii=False))
if p.returncode or after!=protected:sys.exit(p.returncode or 1)
