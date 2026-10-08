"""受付の内側で自分の一走行だけを監督する。CPU枠と熱・容量を記録する。"""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
from inbox_snapshot import count_models

folder = Path(sys.argv[1]).resolve()
spec = json.loads((folder / 'spec.json').read_text())
limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True)) - 2
assert limit >= 1

def census():
    data = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    rows = {}
    for line in data.splitlines():
        p = line.split(None, 5)
        if len(p) != 6:
            continue
        pid, parent, pgid, rss, state, command = p
        executable = command.split(None, 1)[0].lower()
        heavy = not state.startswith(('T', 'Z')) and ('python' in executable or 'pypy' in executable) and 'resource_tracker' not in command and 'jobs.py' not in command and (int(rss) >= 102400 or 'spawn_main' in command)
        rows[int(pid)] = {'parent': int(parent), 'ppid': int(parent), 'pid':int(pid), 'pgid': int(pgid), 'rss_bytes': int(rss)*1024, 'heavy': heavy, 'state':state, 'command':command}
    own = {os.getpid()}
    while True:
        extra = {p for p, v in rows.items() if v['parent'] in own}
        if extra <= own:
            break
        own |= extra
    return rows, own

def observe():
    rows, own = census()
    thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
    m = re.search(r'CPU_Speed_Limit\s*=\s*(\d+)', thermal)
    warning = any('warning' in line.lower() and 'no ' not in line.lower() for line in thermal.splitlines())
    models,unknown,paused,paused_models=count_models(rows)
    return {'models':len(models),'unknown_active_spawn':len(unknown),'own_models':sum(m['pid'] in own for m in models),
            'epoch_seconds': time.time(), 'outside_heavy': sum(v['heavy'] for p, v in rows.items() if p not in own),
            'inside_heavy': sum(rows[p]['heavy'] for p in own if p in rows),
            'own_rss_bytes': sum(rows[p]['rss_bytes'] for p in own if p in rows),
            'free_disk_bytes': shutil.disk_usage(folder).free, 'thermal': thermal,
            'thermal_warning': warning or (m is not None and m.group(1) != '100')}

for repo, expected in spec.get('sources', {}).items():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == expected
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip()
with (folder / 'resources.jsonl').open('x') as samples:
    def record(event, row):
        samples.write(json.dumps({'event': event, 'cpu_limit': limit, **row})+'\n'); samples.flush()
    # 模型の親とworkerは二枠、単一プロセスの読み手は明示した一枠に収める。
    start_slots=int(spec.get('cpu_start_slots',2))
    assert 1 <= start_slots <= limit
    while True:
        # 期限後の新しい模型は始めない。開始済みの子の監督には期限を使わない。
        deadline = spec.get("start_deadline_jst", "2026-10-09T09:00:00+09:00")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(deadline):
            record("deadline_before_start", {"epoch_seconds": time.time(), "model_started": False})
            raise SystemExit("期限後なので新しい模型の開始をしない")
        row = observe()
        if row['models']+1 <= 8 and row['unknown_active_spawn']==0 and row['outside_heavy'] + start_slots <= limit and row['free_disk_bytes'] >= 20*2**30 and not row['thermal_warning']:
            break
        record('wait_before_start', row)
        time.sleep(10)
    env = dict(os.environ, PYTHONHASHSEED='0')
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    began = time.perf_counter(); epoch = time.time()
    with (folder / 'run.log').open('x') as log:
        child = subprocess.Popen(['/usr/bin/time', '-l', *spec['command']], cwd=spec['cwd'], env=env,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (folder / 'pid.json').write_text(json.dumps({'pid': child.pid, 'pgid': child.pid})+'\n')
        record('started', {**row, 'model_pid': child.pid})
        paused = False; pause_start = None; paused_seconds = 0
        while child.poll() is None:
            row = observe()
            stop = row['models']>8 or row['unknown_active_spawn']>0 or row['outside_heavy'] + max(row['inside_heavy'], 1) > limit or row['thermal_warning'] or row['free_disk_bytes'] < 18.5*2**30
            if stop != paused:
                try:
                    os.killpg(child.pid, signal.SIGSTOP if stop else signal.SIGCONT)
                except ProcessLookupError:
                    break
                paused = stop
                if stop:
                    pause_start = time.perf_counter()
                else:
                    paused_seconds += time.perf_counter() - pause_start
                record('paused' if stop else 'resumed', row)
            else:
                record('sample', row)
            time.sleep(5)
        rc = child.wait()
    result = {'exit_code': rc, 'started_epoch': epoch, 'finished_epoch': time.time(),
              'wall_seconds': time.perf_counter()-began, 'paused_seconds': paused_seconds,
              'cpu_limit': limit, 'output_bytes': sum(p.stat().st_size for p in Path(spec['output']).rglob('*') if p.is_file())}
    record('finished', result)
(folder / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
raise SystemExit(rc)
