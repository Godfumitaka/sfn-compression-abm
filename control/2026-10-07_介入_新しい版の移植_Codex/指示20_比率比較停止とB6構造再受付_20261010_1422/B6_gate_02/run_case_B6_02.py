"""指示12B5の指定関門を通常受付の中で一度だけ始める。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import platform
import resource
import re
import shutil
import subprocess
import sys
import time

here = Path(__file__).resolve().parent
port = here.parents[1]
sys.path.insert(0, str(port))
def census():
    # 受付後にも低RSSを含む全psの親子を読む。待つ親・受付・trackerは二重計数しない。
    text=subprocess.check_output(['ps','-axo','pid=,ppid=,stat=,rss=,command='],text=True)
    raw={}
    for line in text.splitlines():
        values=line.strip().split(None,4)
        if len(values)==5:
            pid,parent,state,rss,command=values
            raw[int(pid)]=dict(parent=int(parent),state=state,rss_kib=int(rss),command=command)
    selected={p for p,r in raw.items() if p!=os.getpid() and re.search(r'(^|/)python[^/]*$', r['command'].split()[0], re.I)
              and 'jobs.py' not in r['command'] and 'resource_tracker' not in r['command'] and 'ps -axo' not in r['command']}
    ancestors=set()
    for pid in selected:
        parent=raw[pid]['parent'];seen=set()
        while parent in raw and parent not in seen:
            seen.add(parent)
            if parent in selected:ancestors.add(parent)
            parent=raw[parent]['parent']
    leaves=selected-ancestors
    active={p for p in leaves if 'T' not in raw[p]['state'] and not raw[p]['state'].startswith('Z')}
    paused={p for p in leaves if 'T' in raw[p]['state']}
    return raw,active,paused
admitted = time.time()
label = sys.argv[1]
spec = json.loads((here / 'commands_B6_02.json').read_text())[label]
dest = here / label
dest.mkdir(exist_ok=False)

def now():
    return datetime.datetime.now().astimezone().isoformat()

def save(name, value):
    (dest / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

hand = json.loads((port/'instruction20/B6_preparation_02/hand_gate_02.json').read_text())
assert hand['exit_code']==0 and hand['protected_unchanged'], 'B6構造関門未完了'
comparison = json.loads((port/'instruction20/comparison_01/comparison_01.json').read_text())
assert comparison['passed'] and comparison['protected_unchanged'], 'B5(a)保存二本の関門未完了'
source = Path(spec['cwd'])
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == spec['commit']
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip()
assert sha(spec['config']) == spec['config_sha256']
assert sha(here / 'observe.py') == spec['observer_sha256']
protected = json.loads((here / 'protected_B6_02.json').read_text())
def fingerprints():
    return {root: {name: sha(Path(root) / name) for name in files} for root, files in protected.items()}
assert fingerprints() == protected
save('protected_before.json', protected)
waiting = time.perf_counter()
while True:
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    rows, active, paused = census()
    parents = set()
    for pid in active | paused:
        parent = rows[pid]['parent']; seen = set()
        while parent in rows and parent not in seen:
            seen.add(parent)
            if parent in active | paused:
                parents.add(parent)
            parent = rows[parent]['parent']
    active -= parents; paused -= parents
    free = shutil.disk_usage(dest).free
    if len(active) + spec['models'] <= 8 and free >= 20 * 2**30:
        break
    save('before_start_wait.json', dict(at_jst=now(), active=len(active), paused=len(paused), free_disk_bytes=free))
    time.sleep(15)
identity = platform.node() + subprocess.check_output(['/usr/sbin/sysctl', '-n', 'kern.boottime'], text=True)
save('before_start.json', dict(at_jst=now(), active=len(active), paused=len(paused),
    processes=[dict(pid=p, **rows[p]) for p in sorted(active | paused)], excluded_parents=sorted(parents),
    free_disk_bytes=free, machine_boot_sha256=hashlib.sha256(identity.encode()).hexdigest(),
    thermal=subprocess.check_output(['pmset', '-g', 'therm'], text=True),
    swap=subprocess.check_output(['sysctl', 'vm.swapusage'], text=True)))
runtime = dict(spec, evidence=str(dest), argv=[sys.executable, *spec['model_argv']])
save('runtime.json', runtime)
status = dict(state='running', started_at_jst=now(), wrapper_pid=os.getpid(), command=spec,
    admission_wait_seconds=admitted-float(os.environ['INTERVENTION_ADMISSION_SUBMITTED_EPOCH']),
    cpu_wait_seconds=time.perf_counter()-waiting, production_started=False)
save('status.json', status)
env = dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
for name in ('LC_ALL', 'LANG', 'LC_CTYPE'):
    env.pop(name, None)
start = time.perf_counter()
with (dest / 'model.log').open('xb') as log:
    child = subprocess.Popen([sys.executable, str(here / 'observe.py'), str(dest / 'runtime.json')],
                             cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
    status['model_parent_pid'] = child.pid
    save('status.json', status)
    code = child.wait()
after = fingerprints()
save('protected_after.json', after)
status.update(state='completed' if code == 0 and after == protected else 'stopped', exit_code=code,
    ended_at_jst=now(), model_seconds=time.perf_counter()-start, protected_unchanged=after == protected,
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
save('status.json', status)
print(json.dumps(status, ensure_ascii=False), flush=True)
sys.exit(code or (0 if after == protected else 1))
