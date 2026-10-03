"""既存workerの外から時間と控えの大きさだけを計る。模型の入力・出力は変えない。"""
from pathlib import Path
from collections import Counter
from dataclasses import fields, is_dataclass
import cProfile
import json
import os
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker


def deep_bytes(value):
    """同じ対象を一回だけ数える、その控え単独の到達可能なPythonのバイト数。"""
    seen = set()
    pending = [value]
    total = 0
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
            pending.extend(getattr(item, f.name) for f in fields(item))
    return total


def worker(task):
    import sweep
    import sme2017
    profiler = cProfile.Profile()
    stats = Counter()
    details = {}
    ordered = sme2017._Engine._ordered
    key = sme2017._Engine._key
    snapshot = sme2017.Matcher.snapshot
    restore = sme2017.Matcher.restore

    def counted_key(self, members):
        caller = sys._getframe(1).f_code.co_name
        stats['key_calls:' + caller] += 1
        stats['key_miss:' + caller] += members not in self.key_cache
        return key(self, members)

    def counted_ordered(self, values, scorer, phase):
        previous = set(self.key_cache)
        points = {}
        def measured_scorer(value):
            score = scorer(value)
            points[value] = score
            return score
        result = ordered(self, values, measured_scorer, phase)
        frequencies = Counter(points.values())
        stats['ordered_calls:' + phase] += 1
        stats['ordered_values:' + phase] += len(points)
        stats['ordered_unique_score_values:' + phase] += sum(frequencies[s] == 1 for s in points.values())
        stats['ordered_unique_score_key_miss:' + phase] += sum(frequencies[s] == 1 and v not in previous for v, s in points.items())
        return result

    def counted_snapshot(self):
        stats['snapshot_calls'] += 1
        stats['snapshot_cache_entries'] += len(self.cache)
        stats['snapshot_self_cache_entries'] += len(self.self_cache)
        stats['snapshot_cache_rng_entries'] += len(self.cache_rng)
        return snapshot(self)

    def counted_restore(self, snap):
        stats['restore_calls'] += 1
        return restore(self, snap)

    sme2017._Engine._key = counted_key
    sme2017._Engine._ordered = counted_ordered
    sme2017.Matcher.snapshot = counted_snapshot
    sme2017.Matcher.restore = counted_restore
    run_one = sweep.run_one
    out = Path(task['out_root']).parent
    (out / 'worker_pid.json').write_text(json.dumps({'pid': os.getpid(), 'ppid': os.getppid(), 'source': str(SOURCE)}) + '\n')
    trace = (out / 'trials.jsonl').open('w')
    deep_seconds = 0.0
    deep_samples = 0

    def measured_run_one(task):
        import abm.loop as loop
        import smeshared
        agent_input = loop._agent_input
        record = loop._ledger_record
        start = {'time': None, 'trial': None}

        def timed_input(trial, before):
            start.update(time=time.perf_counter(), trial=trial.trial)
            return agent_input(trial, before)

        def timed_record(*args, **kwargs):
            nonlocal deep_seconds, deep_samples
            result = record(*args, **kwargs)
            elapsed = time.perf_counter() - start['time']
            trial = start['trial']
            row = {'trial': trial, 'model_seconds': elapsed,
                   'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
            for name in ('cache', 'self_cache', 'cache_rng'):
                cache = getattr(smeshared.ENGINE, name)
                row[name + '_count'] = len(cache)
                row[name + '_shallow_bytes'] = sys.getsizeof(cache)
            if trial in (0, 1, 9) or (trial + 1) % 20 == 0:
                t = time.perf_counter()
                for name in ('cache', 'self_cache', 'cache_rng'):
                    row[name + '_deep_bytes'] = deep_bytes(getattr(smeshared.ENGINE, name))
                row['deep_measure_seconds'] = time.perf_counter() - t
                deep_seconds += row['deep_measure_seconds']
                deep_samples += 1
            trace.write(json.dumps(row, ensure_ascii=False) + '\n')
            trace.flush()
            return result

        loop._agent_input = timed_input
        loop._ledger_record = timed_record
        return run_one(task)

    sweep.run_one = measured_run_one
    began = time.perf_counter()
    profiler.enable()
    try:
        return REAL_WORKER(task)
    finally:
        profiler.disable()
        profiler.dump_stats(str(out / 'worker.pstats'))
        trace.close()
        details.update(counters=dict(stats), wall_seconds=time.perf_counter() - began,
                       deep_measure_seconds=deep_seconds, deep_samples=deep_samples,
                       profiler_scope='実際に模型を計算するworker、初期化と終了処理を含む',
                       per_trial_scope='本人への入力の作成から試行の記録関数の終了まで、控えの大きさの測定を含まない',
                       size_scope='各控え単独の到達可能なPythonの大きさ、三控えを足すと共有する対象を二重に数える')
        (out / 'profile.json').write_text(json.dumps(details, ensure_ascii=False, indent=2) + '\n')
