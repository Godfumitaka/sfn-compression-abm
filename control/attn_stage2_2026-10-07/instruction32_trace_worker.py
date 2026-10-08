"""指示32。元workerを同じ過程で呼び、例外を握りつぶす前に保存する。"""
from pathlib import Path
from concurrent.futures import Future
from datetime import datetime
import json, os, resource, sys, time, traceback

ROOT = Path(__file__).resolve().parent
version = sys.argv[1]
case = json.loads((ROOT/'preparation_manifest.json').read_text())['cases'][version]
SOURCE = Path(case['source'])
FOLDER = Path(case['folder'])
sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker

def stamp(): return datetime.now().astimezone().isoformat()

def write(name, value):
    with (FOLDER/name).open('x') as out:
        out.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def worker(task):
    write('worker_pid.json', dict(at=stamp(), pid=os.getpid(), ppid=os.getppid(), same_process_worker=True))
    import sweep
    original = sweep.run_one
    began = time.perf_counter()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    count = 0
    returned = False
    error = None
    def one(task):
        import abm.loop as loop
        original_record = loop._ledger_record
        with (FOLDER/'performance.jsonl').open('x') as out:
            def record(agent, trial, *args, **kwargs):
                nonlocal count
                result = original_record(agent, trial, *args, **kwargs)
                count += 1
                out.write(json.dumps(dict(at=stamp(), trial=trial.trial, trials_completed=count,
                    elapsed_seconds=time.perf_counter()-began,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))+'\n')
                out.flush()
                return result
            loop._ledger_record = record
            try: return original(task)
            finally: loop._ledger_record = original_record
    sweep.run_one = one
    try:
        result = REAL_WORKER(task)
        returned = True
        return result
    except BaseException as exc:
        error = repr(exc)
        trace = traceback.format_exc()
        with (FOLDER/'worker_traceback.txt').open('x') as out: out.write(trace)
        write('worker_failure.json', dict(at=stamp(), exception_type=type(exc).__name__, error=error,
            trials_completed=count, native_loop_returned=False, automatic_retry=False,
            traceback_captured_inside_worker=True))
        sys.stderr.write(trace)
        sys.stderr.flush()
        raise
    finally:
        sweep.run_one = original
        final = resource.getrusage(resource.RUSAGE_SELF)
        write('diagnostic_worker_ended.json', dict(at=stamp(), pid=os.getpid(), trials_completed=count,
            worker_returned=returned, error=error, wall_seconds=time.perf_counter()-began,
            cpu_seconds=final.ru_utime+final.ru_stime-usage.ru_utime-usage.ru_stime,
            peak_rss_bytes=final.ru_maxrss, scope='same_process_worker_model_and_trace_observation',
            production_started=False, model_signals=0))

class InlineExecutor:
    """元の一workerとFuture結果を維持し、管理threadを診断の範囲から外す。"""
    def __init__(self, **kwargs):
        assert kwargs['max_workers'] == 1 and kwargs['max_tasks_per_child'] == 1
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def submit(self, function, task):
        future = Future()
        try: future.set_result(function(task))
        except BaseException as exc: future.set_exception(exc)
        return future
    def shutdown(self, **kwargs): pass

if __name__ == '__main__':
    command = case['native_command']
    assert not Path(command[3]).exists(), '既存成果へ再投入しない'
    v3_run.ProcessPoolExecutor = InlineExecutor
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()
