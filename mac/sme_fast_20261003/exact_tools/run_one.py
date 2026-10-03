"""空きと熱と既存の処理を確かめて、検証を一本実行する。"""
from pathlib import Path
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time


def resources(path):
    lines = subprocess.check_output(['ps', '-axo', 'pid,ppid,%cpu,rss,comm'], text=True).splitlines()[1:]
    heavy = []
    for line in lines:
        fields = line.split(None, 4)
        if len(fields) == 5 and Path(fields[4]).name in ('Python', 'python3.12', 'python3') and float(fields[2]) > 20:
            heavy.append({'pid': int(fields[0]), 'ppid': int(fields[1]), 'cpu': float(fields[2]), 'rss_kb': int(fields[3])})
    return {'time': datetime.datetime.now().astimezone().isoformat(), 'free_bytes': shutil.disk_usage(path).free,
            'thermal': subprocess.check_output(['pmset', '-g', 'therm'], text=True).strip(),
            'swap': subprocess.check_output(['sysctl', 'vm.swapusage'], text=True).strip(),
            'memory': subprocess.check_output(['vm_stat'], text=True), 'python_heavy': heavy}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', type=Path)
    ap.add_argument('source', type=Path)
    a = ap.parse_args()
    command = json.loads(a.command.read_text())
    out = Path(command[3]).parent
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'run.log').exists():
        raise SystemExit('既存のログを上書きしない')
    first = resources(out)
    if first['free_bytes'] < 18 * 2**30 or len(first['python_heavy']) >= 4 or 'No thermal warning level has been recorded' not in first['thermal']:
        raise SystemExit('開始する余裕が無い')
    (out / 'resources.jsonl').write_text(json.dumps(first, ensure_ascii=False) + '\n')
    env = dict(os.environ, SME_EXACT_SOURCE=str(a.source.resolve()), PYTHONHASHSEED='0')
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    began = time.perf_counter()
    with (out / 'run.log').open('w') as log:
        p = subprocess.Popen([command[0], str(Path(__file__).with_name('observe.py')), str(a.command.resolve())],
                             cwd=a.source, env=env, stdout=log, stderr=subprocess.STDOUT)
        while p.poll() is None:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                row = resources(out)
                with (out / 'resources.jsonl').open('a') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                if row['free_bytes'] < 18 * 2**30 or 'No thermal warning level has been recorded' not in row['thermal']:
                    (out / 'resource_stop.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
                    p.terminate()
                    break
    code = p.wait()
    result = {'exit': code, 'wall_seconds': time.perf_counter() - began,
              'source': str(a.source.resolve()), 'command': command}
    (out / 'run_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'exit': code, 'seconds': result['wall_seconds'], 'output': str(out)}, ensure_ascii=False), flush=True)
    if code:
        print((out / 'run.log').read_text()[-3000:], flush=True)
        raise SystemExit(code)


if __name__ == '__main__':
    main()
