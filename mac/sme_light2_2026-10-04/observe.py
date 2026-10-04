"""模型の外で同点用乱数・一試行の秒・純粋な鍵の控えを記録する。"""
from pathlib import Path
import cProfile
import json
import os
import resource
import sys
import time

SOURCE = Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker


def worker(task):
    import sweep
    real_run_one = sweep.run_one
    out = Path(task['out_root']).parent
    stream = (out / 'tie_rng.jsonl').open('w')
    timing = (out / 'performance.jsonl').open('w')
    profiler = cProfile.Profile() if os.environ.get('SME_LIGHT_PROFILE') == '1' else None

    def run_one(task):
        import abm.loop as loop
        import sme2017
        import smeshared
        real_record, real_input = loop._ledger_record, loop._agent_input
        current = {}
        counters = {'match_requests': 0, 'engine_computations': 0}
        real_match, real_engine = sme2017.Matcher.match, sme2017._Engine.run

        def match(self, *args, **kwargs):
            counters['match_requests'] += 1
            return real_match(self, *args, **kwargs)

        def engine(self):
            counters['engine_computations'] += 1
            return real_engine(self)

        def agent_input(trial, before):
            current['begin'] = time.perf_counter()
            if profiler is not None:
                profiler.enable()
            return real_input(trial, before)

        def record(agent_id, trial, *args, **kwargs):
            result = real_record(agent_id, trial, *args, **kwargs)
            elapsed = time.perf_counter() - current['begin']
            if profiler is not None:
                profiler.disable()
            stream.write(json.dumps({'trial': trial.trial, 'rng': smeshared.ENGINE.rng.getstate(),
                                     'cache_count': len(smeshared.ENGINE.cache),
                                     'self_cache_count': len(smeshared.ENGINE.self_cache),
                                     'cache_rng_count': len(smeshared.ENGINE.cache_rng)},
                                    ensure_ascii=False) + '\n')
            stream.flush()
            info = sme2017._canonical_cached.cache_info()
            timing.write(json.dumps({'trial': trial.trial, 'seconds': elapsed,
                                     'key_cache_hits': info.hits, 'key_cache_misses': info.misses,
                                     'key_cache_size': info.currsize, 'key_cache_limit': info.maxsize,
                                     'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                     **counters}, ensure_ascii=False) + '\n')
            timing.flush()
            return result

        loop._ledger_record, loop._agent_input = record, agent_input
        sme2017.Matcher.match, sme2017._Engine.run = match, engine
        return real_run_one(task)

    sweep.run_one = run_one
    try:
        return REAL_WORKER(task)
    finally:
        stream.close(); timing.close()
        if profiler is not None:
            profiler.disable()
            profiler.dump_stats(str(out / 'worker.pstats'))


def main():
    command = json.loads(Path(sys.argv[1]).read_text())
    output = Path(command[3])
    if output.exists():
        raise SystemExit('出力を上書きしない')
    output.parent.mkdir(parents=True, exist_ok=True)
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()


if __name__ == '__main__':
    main()
