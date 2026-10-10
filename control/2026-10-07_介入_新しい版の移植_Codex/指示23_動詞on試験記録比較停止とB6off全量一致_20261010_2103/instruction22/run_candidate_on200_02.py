"""指示22：旗off関門後の指定先頭200の修正on一本だけを受付後に走らせる。"""
from pathlib import Path
import datetime,hashlib,json,os,platform,resource,shutil,subprocess,sys,time
from resource_census_02 import census
here=Path(__file__).resolve().parent
label=sys.argv[1]
spec=json.loads((here/'candidate_on200_commands_02.json').read_text())[label]
assert label in ('candidate_on_D_04_200_01','candidate_on_D_015_200_01')
off=json.loads(Path(spec['requires_off_comparison']).read_text())
assert off['passed'] and off['actual_files_excluded']==off['probe_rows_excluded']==0
assert spec['new_flag']=='on' and spec['reservation_gb']==.6
assert '--attn-probe-name-receipts' in spec['argv']
dest=Path(spec['destination']);dest.mkdir(exist_ok=False)
def now():return datetime.datetime.now().astimezone().isoformat()
def save(name,value):
    (dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
admitted=time.time()
gate=json.loads(Path(spec['requires_structure']).read_text())
assert gate['passed'] and gate['protected_unchanged'] and gate['exit_code']==0
source=Path(spec['cwd'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==spec['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
assert hashlib.sha256(Path(spec['argv'][1]).read_bytes()).hexdigest()==spec['observer_sha256']
protected=json.loads((here/'candidate_protected_01.json').read_text())
def fingerprints():
    return {root:{name:hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()
                  for name in files} for root,files in protected.items()}
assert fingerprints()==protected
save('protected_before.json',protected)
waiting=time.perf_counter()
while True:
    assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    rows,active,paused=census();free=shutil.disk_usage(dest).free
    if len(active)+1<=8 and free>=20*2**30:break
    save('before_start_wait.json',dict(at_jst=now(),active=len(active),paused=len(paused),free_disk_bytes=free))
    time.sleep(15)
identity=platform.node()+subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True)
save('before_start.json',dict(at_jst=now(),active=len(active),paused=len(paused),ps=rows,
    active_pids=sorted(active),paused_pids=sorted(paused),free_disk_bytes=free,
    machine_boot_sha256=hashlib.sha256(identity.encode()).hexdigest(),
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True)))
status=dict(state='running',started_at_jst=now(),wrapper_pid=os.getpid(),command=spec,
    admission_wait_seconds=admitted-float(os.environ['INTERVENTION22_ON_SUBMITTED_EPOCH']),
    cpu_wait_seconds=time.perf_counter()-waiting,production_started=False)
save('status.json',status)
env=dict(os.environ,**spec['environment'],PYTHONDONTWRITEBYTECODE='1')
for name in ('LC_ALL','LANG','LC_CTYPE'):env.pop(name,None)
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
    assert marker['completed_trials']==200 and marker['source_commit']==spec['source_commit']
    status['completed_trials']=200
save('status.json',status)
print(json.dumps({k:v for k,v in status.items() if k!='command'},ensure_ascii=False),flush=True)
sys.exit(code or int(after!=protected))
