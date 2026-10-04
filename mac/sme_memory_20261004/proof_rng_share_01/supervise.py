"""一本だけ測り、30秒ごとに全セッションの余裕を記録する。"""
from pathlib import Path
import importlib.util
import json
import os
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
spec = importlib.util.spec_from_file_location('resource_check', WORKSPACE / 'codex_sme_fast_2026-10-03/exact_tools/run_one.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def safe(row, paused=False):
    return (row['free_bytes'] >= 18 * 2**30 and len(row['python_heavy']) < (4 if paused else 5)
            and 'No thermal warning level has been recorded' in row['thermal'])


def main():
    first = module.resources(HERE)
    if not safe(first, paused=True):
        raise SystemExit('開始する余裕が無い')
    if (HERE / 'run.log').exists():
        raise SystemExit('記録を上書きしない')
    (HERE / 'resources.jsonl').write_text(json.dumps(first, ensure_ascii=False) + '\n')
    env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(HERE.parent / 'source_rng_share'))
    for name in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(name, None)
    began, paused = time.perf_counter(), False
    with (HERE / 'run.log').open('w') as stream:
        process = subprocess.Popen(['/opt/homebrew/opt/python@3.12/bin/python3.12', str(HERE / 'observe.py'), str(HERE / 'command.json')],
                                   cwd=HERE.parent / 'source_rng_share', env=env, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        while process.poll() is None:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                row = module.resources(HERE)
                row['measurement_paused'] = paused
                with (HERE / 'resources.jsonl').open('a') as out:
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                good = safe(row, paused=paused)
                if not good and not paused:
                    os.killpg(process.pid, signal.SIGSTOP)
                    paused = True
                elif good and paused:
                    os.killpg(process.pid, signal.SIGCONT)
                    paused = False
    result = {'exit': process.returncode, 'wall_seconds': time.perf_counter() - began}
    (HERE / 'run_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    if process.returncode:
        print((HERE / 'run.log').read_text()[-2500:], flush=True)
        raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
