"""52本の小検査の後だけ、四案を順に全1740試行で比較する。"""
from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys
import threading
import time

from compare_body import compare

ROOT = Path(__file__).resolve().parent
KEY = ROOT.parent / 'codex_sme_keyfast_2026-10-04'
ns = {'__file__': str(ROOT / 'resource_conditions.py')}
exec((KEY / 'run_profiles.py').read_text().split("for name in ('profile_A_01'")[0], ns)
conditions, guard, STOP = ns['conditions'], ns['guard'], ns['STOP']
small = json.loads((ROOT / 'small_complete_01.json').read_text())
assert small['passed'] and len(small['cases']) == 52
plan = json.loads((ROOT / 'full_plan_01.json').read_text())
completed = []


def load_observer(folder, stop):
    while not stop.wait(15):
        raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,rss=,%cpu=,command='], text=True)
        rows = []
        for line in raw.splitlines():
            fields = line.strip().split(None, 4)
            if len(fields) == 5 and ('Python' in fields[4] or 'pypy' in fields[4]):
                rows.append({'pid': int(fields[0]), 'ppid': int(fields[1]), 'rss_kib': int(fields[2]),
                             'cpu_percent': float(fields[3]), 'spawn': 'spawn_main' in fields[4]})
        with (folder / 'load_conditions.jsonl').open('a') as stream:
            stream.write(json.dumps({'at': datetime.now().astimezone().isoformat(), 'processes': rows}) + '\n')


for item in plan:
    folder = Path(item['folder'])
    folder.mkdir(parents=True, exist_ok=True)
    row = conditions()
    assert row['free_bytes'] >= 20 * 2**30 and not row['swap_grew'] and not row['thermal_warning'], row
    assert not (folder / 'run.log').exists(), '二重に走らせない'
    (folder / 'resources_start.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    env = dict(os.environ, SME_EXACT_SOURCE=item['source'], PYTHONHASHSEED='0')
    for k in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(k, None)
    STOP.clear()
    threads = [threading.Thread(target=guard, args=(folder,), daemon=True),
               threading.Thread(target=load_observer, args=(folder, STOP), daemon=True)]
    for thread in threads:
        thread.start()
    began = time.perf_counter()
    with (folder / 'run.log').open('w') as log:
        rc = subprocess.run([sys.executable, str(ROOT / 'observe.py'), str(folder / 'command.json')],
                            env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    STOP.set()
    for thread in threads:
        thread.join()
    result = {'exit': rc, 'wall_seconds': time.perf_counter() - began,
              'at': datetime.now().astimezone().isoformat(), 'cprofile': False}
    (folder / 'run_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(item['mode'], result, flush=True)
    if rc or (folder / 'resource_stop.json').exists():
        raise SystemExit(1)
    proof = compare(Path(item['reference']) / 'output', folder / 'output', folder / 'body_comparison.json')
    print(item['mode'], 'body', proof['passed'], flush=True)
    if not proof['passed']:
        raise SystemExit(2)
    completed.append({'mode': item['mode'], 'passed': True, 'run': result})
    (ROOT / 'full_progress_01.json').write_text(json.dumps(completed, indent=2) + '\n')
(ROOT / 'full_complete_01.json').write_text(json.dumps({'passed': True, 'modes': completed}, indent=2) + '\n')
