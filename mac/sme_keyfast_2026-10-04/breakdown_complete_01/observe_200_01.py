"""元の6e93e0bの200試行を診断する。模型の枝は一切編集しない。"""
from pathlib import Path
import cProfile
import gzip
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'codex_sme_memory_2026-10-04/source_rng_share'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
FOLDER = Path(os.environ['SME_BREAKDOWN_FOLDER'])
import v3_run
REAL_WORKER = v3_run.worker


def worker(task):
    import sweep
    import sme2017
    import instrument_01 as meter
    meter.install(sme2017)
    real_run = sweep.run_one
    profiler = cProfile.Profile()
    stream = (FOLDER / 'trials.jsonl').open('w')
    (FOLDER / 'worker_pid.json').write_text(json.dumps({'pid': os.getpid(), 'ppid': os.getppid()}) + '\n')

    def run_one(task):
        import abm.loop as loop
        real_input, real_record = loop._agent_input, loop._ledger_record
        current = {}
        def agent_input(trial, before):
            meter.TRIAL = trial.trial
            meter.ROWS.clear()
            current['began'] = time.perf_counter()
            profiler.enable()
            return real_input(trial, before)
        def record(agent_id, trial, *args, **kwargs):
            result = real_record(agent_id, trial, *args, **kwargs)
            profiler.disable()
            stream.write(json.dumps({'trial': trial.trial, 'seconds_diagnostic': time.perf_counter() - current['began'],
                                     'callers': meter.aggregate(meter.ROWS)}, ensure_ascii=False) + '\n')
            stream.flush()
            return result
        loop._agent_input, loop._ledger_record = agent_input, record
        return real_run(task)
    sweep.run_one = run_one
    try:
        return REAL_WORKER(task)
    finally:
        profiler.disable()
        profiler.dump_stats(str(FOLDER / 'worker.pstats'))
        stream.close()
        with gzip.open(FOLDER / 'canonical_samples.jsonl.gz', 'wt') as output:
            for item in meter.FIRST + list(meter.SAMPLES):
                output.write(json.dumps(item, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    command = json.loads((FOLDER / 'command.json').read_text())
    assert not Path(command[3]).exists(), '記録を上書きしない'
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()
