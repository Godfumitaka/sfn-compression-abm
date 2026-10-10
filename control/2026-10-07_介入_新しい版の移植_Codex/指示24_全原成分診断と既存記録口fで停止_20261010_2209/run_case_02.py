"""指示24：受付後、固定模型の同じ200試行を成分観察器で一度だけ診断する。"""
from pathlib import Path
import datetime, hashlib, json, os, platform, resource, shutil, subprocess, sys, time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE/'instruction22'))
from resource_census_02 import census

label = sys.argv[1]
spec = json.loads((HERE/'commands_02.json').read_text())[label]
dest = Path(spec['destination'])
dest.mkdir(exist_ok=False)
admitted = time.time()

def now():
    return datetime.datetime.now().astimezone().isoformat()

def save(name, value):
    (dest/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

protected = json.loads((BASE/'instruction22/candidate_protected_01.json').read_text())

def fingerprints():
    result = {}
    for root, files in protected.items():
        result[root] = {}
        for name in files:
            h = hashlib.sha256()
            with (Path(root)/name).open('rb') as stream:
                for block in iter(lambda: stream.read(1024*1024), b''):
                    h.update(block)
            result[root][name] = h.hexdigest()
    return result

source = Path(spec['cwd'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() == spec['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
assert hashlib.sha256(Path(spec['argv'][1]).read_bytes()).hexdigest() == spec['observer_sha256']
assert hashlib.sha256((BASE/'instruction12/observer_200.py').read_bytes()).hexdigest() == spec['native_observer_sha256']
assert fingerprints() == protected
save('protected_before.json', protected)
waiting = time.perf_counter()
while True:
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    rows, active, paused = census()
    free = shutil.disk_usage(dest).free
    if len(active)+1 <= 8 and free >= 20*2**30:
        break
    save('before_start_wait.json', dict(at_jst=now(), active=len(active), paused=len(paused), free_disk_bytes=free))
    time.sleep(15)
identity = platform.node()+subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True)
save('before_start.json',dict(at_jst=now(),active=len(active),paused=len(paused),ps=rows,
    active_pids=sorted(active),paused_pids=sorted(paused),free_disk_bytes=free,
    machine_boot_sha256=hashlib.sha256(identity.encode()).hexdigest(),
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True)))
status = dict(state='running',started_at_jst=now(),wrapper_pid=os.getpid(),command=spec,
    admission_wait_seconds=admitted-float(os.environ['INTERVENTION24_SUBMITTED_EPOCH']),
    cpu_wait_seconds=time.perf_counter()-waiting,production_started=False)
save('status.json',status)
env = dict(os.environ,**spec['environment'],PYTHONDONTWRITEBYTECODE='1')
for name in ('LC_ALL','LANG','LC_CTYPE'):
    env.pop(name,None)
began = time.perf_counter()
with (dest/'model.log').open('xb') as log:
    child = subprocess.Popen(spec['argv'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
    status['model_parent_pid'] = child.pid
    save('status.json',status)
    code = child.wait()
after = fingerprints()
save('protected_after.json',after)
status.update(state='completed' if code==0 and after==protected else 'stopped',exit_code=code,
    ended_at_jst=now(),model_seconds=time.perf_counter()-began,protected_unchanged=after==protected,
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
if code == 0:
    marker=json.loads((dest/'output/measurement/partial_done.json').read_text())
    assert marker['completed_trials']==200 and marker['source_commit']==spec['source_commit']
    status['completed_trials']=200
save('status.json',status)
print(json.dumps({k:v for k,v in status.items() if k!='command'},ensure_ascii=False),flush=True)
sys.exit(code or int(after!=protected))
