"""資源を確認して200試行の計測を一本だけ始める。記録を消さない。"""
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

def resource_snapshot():
    thermal = subprocess.check_output(['pmset', '-g', 'therm'], text=True)
    swap = subprocess.check_output(['sysctl', 'vm.swapusage'], text=True).strip()
    memory = subprocess.check_output(['vm_stat'], text=True)
    processes = subprocess.check_output(['ps', '-axo', 'pid,ppid,%cpu,rss,command'], text=True)
    python_heavy = []
    for line in processes.splitlines()[1:]:
        fields = line.split(None, 4)
        if len(fields) == 5 and float(fields[2]) > 20 and Path(fields[4].split()[0]).name in ('Python', 'python3.12', 'python3'):
            python_heavy.append({'pid': int(fields[0]), 'ppid': int(fields[1]), 'cpu': float(fields[2]), 'rss_kb': int(fields[3])})
    return {'time': datetime.datetime.now().astimezone().isoformat(),
            'free_bytes': shutil.disk_usage(HERE).free, 'thermal': thermal.strip(),
            'swap': swap, 'memory': memory, 'python_cpu20': python_heavy}

def safe(row):
    return (row['free_bytes'] >= 18 * 2**30
            and 'No thermal warning level has been recorded' in row['thermal']
            and 'No performance warning level has been recorded' in row['thermal'])

if __name__ == '__main__':
    if (HERE / 'run.log').exists():
        raise SystemExit('既存のログは上書きしない')
    first = resource_snapshot()
    (HERE / 'resources.jsonl').write_text(json.dumps(first, ensure_ascii=False) + '\n')
    if not safe(first) or len(first['python_cpu20']) >= 4:
        raise SystemExit('新しい走行を始める余裕が無い')
    env = dict(os.environ, PYTHONHASHSEED='0')
    for name in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(name, None)
    began = time.perf_counter()
    with (HERE / 'run.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(HERE / 'launch.py')], cwd=HERE.parent / 'source', env=env, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            time.sleep(30)
            row = resource_snapshot()
            with (HERE / 'resources.jsonl').open('a') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            if not safe(row):
                (HERE / 'resource_stop.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
                process.terminate()
                break
    code = process.wait()
    record = {'exit': code, 'seconds': time.perf_counter() - began}
    (HERE / 'run_result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    if code:
        raise SystemExit(code)
