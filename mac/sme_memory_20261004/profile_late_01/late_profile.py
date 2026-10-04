"""先頭から走らせ、人が数える1500〜1740試行だけを測る。入力は変えない。"""
from pathlib import Path
from dataclasses import fields, is_dataclass
import cProfile
import json
import os
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'source'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker


def deep_bytes(value):
    """控え単独の到達可能な対象を、共有した実体は一度だけ数える。"""
    seen, pending, total = set(), [value], 0
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        total += sys.getsizeof(item)
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (tuple, list, set, frozenset)):
            pending.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, field.name) for field in fields(item))
    return total


def worker(task):
    import sweep
    real_run_one = sweep.run_one
    profiler = cProfile.Profile()
    trace = (HERE / 'trials.jsonl').open('w')
    rng_log = (HERE / 'tie_rng.jsonl').open('w')
    deep_seconds = 0.0
    began = time.perf_counter()
    (HERE / 'worker_pid.json').write_text(json.dumps({'pid': os.getpid(), 'source': str(SOURCE)}) + '\n')

    def run_one(task):
        import abm.loop as loop
        import smeshared
        real_input, real_record = loop._agent_input, loop._ledger_record
        current = {}

        def agent_input(trial, before):
            if trial.trial == 1499:
                profiler.enable()
            current.update(trial=trial.trial, began=time.perf_counter())
            return real_input(trial, before)

        def ledger_record(agent_id, trial, *args, **kwargs):
            nonlocal deep_seconds
            result = real_record(agent_id, trial, *args, **kwargs)
            elapsed = time.perf_counter() - current['began']
            index = trial.trial
            profiler.disable()
            engine = smeshared.ENGINE
            row = {'trial': index, 'trial_number': index + 1, 'model_seconds': elapsed,
                   'profiled': 1499 <= index <= 1739,
                   'peak_rss_before_measure_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
            for name in ('cache', 'self_cache', 'cache_rng'):
                cache = getattr(engine, name)
                row[name + '_count'] = len(cache)
                row[name + '_shallow_bytes'] = sys.getsizeof(cache)
            rng_log.write(json.dumps({'trial': index, 'rng': engine.rng.getstate(),
                                      'cache_count': len(engine.cache), 'self_cache_count': len(engine.self_cache),
                                      'cache_rng_count': len(engine.cache_rng)}, ensure_ascii=False) + '\n')
            rng_log.flush()
            if index in (1499, 1619, 1739):
                measured = time.perf_counter()
                for name in ('cache', 'self_cache', 'cache_rng'):
                    row[name + '_deep_bytes'] = deep_bytes(getattr(engine, name))
                row['deep_measure_seconds'] = time.perf_counter() - measured
                deep_seconds += row['deep_measure_seconds']
                row['peak_rss_after_measure_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            trace.write(json.dumps(row, ensure_ascii=False) + '\n')
            trace.flush()
            if 1499 <= index < 1739:
                profiler.enable()
            return result

        loop._agent_input, loop._ledger_record = agent_input, ledger_record
        return real_run_one(task)

    sweep.run_one = run_one
    try:
        return REAL_WORKER(task)
    finally:
        profiler.disable()
        profiler.dump_stats(str(HERE / 'worker.pstats'))
        trace.close()
        rng_log.close()
        (HERE / 'profile.json').write_text(json.dumps({'wall_seconds': time.perf_counter() - began,
            'deep_measure_seconds': deep_seconds, 'human_trial_numbers': [1500, 1740],
            'ledger_trial_indexes': [1499, 1739], 'profile_scope': '後半241試行、模型と本体の記録、観測の書出しと大きさの測定を除く',
            'size_scope': '各控え単独の到達可能なPythonのバイト数、列を足すと共有を二重に数える',
            'rss_scope': '大きさの観測用に一時的に使ったメモリを含む'}, ensure_ascii=False, indent=2) + '\n')


def main():
    command = json.loads((HERE / 'command.json').read_text())
    if Path(command[3]).exists():
        raise SystemExit('出力を上書きしない')
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()


if __name__ == '__main__':
    main()
