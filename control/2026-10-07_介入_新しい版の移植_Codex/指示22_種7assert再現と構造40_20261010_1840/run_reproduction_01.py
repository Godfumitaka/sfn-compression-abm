"""指示22の同じ種7命令を通常受付内で一度走らせる。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from resource_census_01 import census

here = Path(__file__).resolve().parent
spec = json.loads((here/'reproduction_spec_01.json').read_text())
dest = Path(spec['destination'])
dest.mkdir(exist_ok=False)


def now():
    return datetime.datetime.now().astimezone().isoformat()


def save(name, value):
    (dest/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def fingerprints():
    return {root: {name: hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()
                   for name in files} for root, files in spec['files'].items()}


admitted = time.time()
source = Path(spec['source'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==spec['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
before = fingerprints()
assert before == spec['files']
save('protected_before.json', before)
waiting = time.perf_counter()
while True:
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    rows, active, paused = census()
    free = shutil.disk_usage(dest).free
    if len(active)+1 <= 8 and free >= 20*2**30:
        break
    save('before_start_wait.json',dict(at_jst=now(),active=len(active),paused=len(paused),free_disk_bytes=free))
    time.sleep(15)
save('before_start.json',dict(at_jst=now(),active=len(active),paused=len(paused),free_disk_bytes=free,
    ps=rows,active_pids=sorted(active),paused_pids=sorted(paused),
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True)))
env=dict(os.environ,**spec['environment'])
for name in ('LC_ALL','LANG','LC_CTYPE'):
    env.pop(name,None)
# 例外の監視口自身を小さい合成assertで確認する。模型の種や世界は使わない。
check=dest/'trace_wiring_check';check.mkdir()
check_env=dict(env,INTERVENTION22_ASSERT_DEST=str(check))
program="code=compile('left=1\\nright=2\\nassert left==right\\n',"+repr(str(Path(spec['argv'][1]).parent/'trace_wiring_check.py'))+",'exec')\ntry: exec(code)\nexcept AssertionError: pass\n"
result=subprocess.run([sys.executable,'-c',program],env=check_env,capture_output=True,text=True)
save('trace_wiring_check.json',dict(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,
    evidence=[p.name for p in check.glob('assert_pid*.json')]))
assert result.returncode==0 and len(list(check.glob('assert_pid*.json')))==1, '例外の観察口が未確認'
status=dict(state='running',started_at_jst=now(),wrapper_pid=os.getpid(),source_commit=spec['source_commit'],
    admission_wait_seconds=admitted-float(os.environ['INTERVENTION22_SUBMITTED_EPOCH']),
    cpu_wait_seconds=time.perf_counter()-waiting,argv=spec['argv'],production_changed=False)
save('status.json',status)
began=time.perf_counter()
with (dest/'model.log').open('xb') as log:
    child=subprocess.Popen(spec['argv'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
    status['model_parent_pid']=child.pid;save('status.json',status)
    code=child.wait()
after=fingerprints();save('protected_after.json',after)
status.update(state='completed' if code==0 else 'stopped',ended_at_jst=now(),exit_code=code,
    model_seconds=time.perf_counter()-began,protected_unchanged=after==before,
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    assertion_records=[p.name for p in dest.glob('assert_pid*.json')])
save('status.json',status)
print(json.dumps({k:v for k,v in status.items() if k!='argv'},ensure_ascii=False),flush=True)
sys.exit(code or (0 if after==before else 1))
