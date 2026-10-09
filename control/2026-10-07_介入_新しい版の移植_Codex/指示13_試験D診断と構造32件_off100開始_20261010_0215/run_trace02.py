"""指示12の指定先頭だけ。受付内で8本・容量・期限を確かめて一度走る。"""
from pathlib import Path
import datetime, hashlib, json, os, platform, resource, shutil, subprocess, sys, time
port = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(port))
from admission_guard import census
here = port/'instruction13'
admitted = time.time()
label = sys.argv[1]
spec = json.loads((here/'commands_trace02.json').read_text())[label]
dest = here/label
dest.mkdir(exist_ok=False)
def save(name, value):
    (dest/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
def now():
    return datetime.datetime.now().astimezone().isoformat()
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
source = Path(spec['cwd'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() == spec['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
assert sha(spec['argv'][1]) == spec['observer_sha256']
protected = json.loads((here/'protected_sources_before.json').read_text())
def fingerprints():
    return {root:{name:sha(Path(root)/name) for name in files} for root,files in protected.items()}
assert fingerprints() == protected
save('protected_before.json', protected)
waiting = time.perf_counter()
while True:
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    rows,active,paused = census();parents=set()
    for pid in active|paused:
        parent=rows[pid]['parent'];seen=set()
        while parent in rows and parent not in seen:
            seen.add(parent)
            if parent in active|paused:parents.add(parent)
            parent=rows[parent]['parent']
    active-=parents;paused-=parents
    if len(active)<8 and shutil.disk_usage(dest).free>=20*2**30:
        break
    save('before_start_wait.json',dict(at_jst=now(),active=len(active),paused=len(paused),free_disk_bytes=shutil.disk_usage(dest).free))
    time.sleep(15)
identity=platform.node()+subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True)
save('before_start.json',dict(at_jst=now(),active=len(active),paused=len(paused),
    processes=[dict(pid=p,**rows[p]) for p in sorted(active|paused)],excluded_parents=sorted(parents),
    free_disk_bytes=shutil.disk_usage(dest).free,machine_boot_sha256=hashlib.sha256(identity.encode()).hexdigest(),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True),swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True)))
status=dict(state='running',started_at_jst=now(),wrapper_pid=os.getpid(),command=spec,
    admission_wait_seconds=admitted-float(os.environ['INTERVENTION_ADMISSION_SUBMITTED_EPOCH']),
    cpu_wait_seconds=time.perf_counter()-waiting,completed_trials=None,production_started=False)
save('status.json',status)
env=dict(os.environ,**spec['environment'],PYTHONDONTWRITEBYTECODE='1')
for name in ('LC_ALL','LANG','LC_CTYPE'):
    env.pop(name,None)
began=time.perf_counter()
with (dest/'model.log').open('xb') as log:
    child=subprocess.Popen(spec['argv'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
    status['model_parent_pid']=child.pid;save('status.json',status)
    code=child.wait()
after=fingerprints();save('protected_after.json',after)
status.update(state='completed' if code==0 and after==protected else 'stopped',exit_code=code,
    ended_at_jst=now(),model_seconds=time.perf_counter()-began,protected_unchanged=after==protected,
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
if code==0:
    marker=json.loads((dest/'output/measurement/partial_done.json').read_text())
    assert marker['completed_trials']==spec['completed_trials']
    status['completed_trials']=marker['completed_trials']
save('status.json',status)
print(json.dumps(status,ensure_ascii=False),flush=True)
sys.exit(code or (0 if after==protected else 1))
