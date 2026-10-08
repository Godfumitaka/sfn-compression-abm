"""原workerと原観測を呼び、JSON fallbackの件数だけを外に残す。"""
from pathlib import Path
import importlib.util
import json
import os
import resource
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
case = json.loads((ROOT / 'preparation_manifest.json').read_text())['cases'][os.environ['SME_JSON_CASE']]
SOURCE = Path(case['source'])
FOLDER = Path(case['folder'])
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
NATIVE_WORKER = v3_run.worker


def counted_worker(task):
    import smeshared as S
    original_keys, original_log = S._log_string_keys, S._log
    stack = []
    counts = {'attempted_records': 0, 'written_records': 0,
              'main_written': 0, 'diagnostic_written': 0, 'by_trial': {}}

    def keys(value):
        if stack:
            stack[-1]['used'] = True
        return original_keys(value)

    def log(record):
        item = {'used': False, 'diagnostic': bool(S.LOG.get('diagnostic') or S._diagnosing())}
        stack.append(item)
        try:
            result = original_log(record)
            if item['used']:
                counts['written_records'] += 1
                counts['diagnostic_written' if item['diagnostic'] else 'main_written'] += 1
                trial = str(S.CTX.get('trial'))
                counts['by_trial'][trial] = counts['by_trial'].get(trial, 0) + 1
            return result
        finally:
            if item['used']:
                counts['attempted_records'] += 1
            stack.pop()

    S._log_string_keys, S._log = keys, log
    try:
        return NATIVE_WORKER(task)
    except BaseException:
        with (FOLDER / 'worker_traceback.txt').open('x') as out:
            out.write(traceback.format_exc())
        raise
    finally:
        S._log_string_keys, S._log = original_keys, original_log
        with (FOLDER / 'json_fallback_counts.json').open('x') as out:
            out.write(json.dumps(counts, ensure_ascii=False, indent=2) + '\n')


def plain_worker(task):
    """2aは原の観測控えを増やさず、台帳の呼出し後に計測する。"""
    import sweep
    original = sweep.run_one
    with (FOLDER / 'worker_pid.json').open('x') as out:
        out.write(json.dumps({'pid': os.getpid(), 'ppid': os.getppid()}) + '\n')

    def one(task):
        import abm.loop as loop
        original_record = loop._ledger_record
        began = time.perf_counter()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        count = 0
        with (FOLDER / 'performance.jsonl').open('x') as perf:
            def record(agent, trial, *args, **kwargs):
                nonlocal count
                result = original_record(agent, trial, *args, **kwargs)
                count += 1
                perf.write(json.dumps({'trial': trial.trial, 'trials_completed': count,
                    'elapsed_seconds': time.perf_counter() - began,
                    'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}) + '\n')
                perf.flush()
                return result
            loop._ledger_record = record
            try:
                result = original(task)
            finally:
                loop._ledger_record = original_record
        final = resource.getrusage(resource.RUSAGE_SELF)
        with (FOLDER / 'measurement.json').open('x') as out:
            out.write(json.dumps({'pid': os.getpid(), 'trials': count,
                'native_loop_returned': True, 'wall_seconds': time.perf_counter() - began,
                'cpu_seconds': final.ru_utime + final.ru_stime - usage.ru_utime - usage.ru_stime,
                'peak_rss_bytes': final.ru_maxrss, 'scope': 'worker_model_and_observation'}, indent=2) + '\n')
        return result

    sweep.run_one = one
    try:
        return counted_worker(task)
    finally:
        sweep.run_one = original


def worker(task):
    if case['observer'] == 'ordered':
        import observe_ordered as O
        O.REAL_WORKER = counted_worker
        return O.worker(task)
    return plain_worker(task)


if __name__ == '__main__':
    command = case['native_command']
    assert not Path(command[3]).exists(), '既存成果へ再投入しない'
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()
