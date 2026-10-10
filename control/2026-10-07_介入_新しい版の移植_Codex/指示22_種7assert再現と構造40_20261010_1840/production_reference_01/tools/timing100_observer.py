"""指示18：確定した台帳の追記後に、100ごとの原時間とworker常駐だけを控える。"""
from contextlib import contextmanager
from pathlib import Path
import json
import resource
import time


@contextmanager
def observe_timing(out, ledger):
    target = Path(out) / 'timing100.jsonl'
    assert not target.exists(), '100ごとの時間を同じ出力へ重ねない'
    native = ledger.append
    absent = object()
    previous = vars(ledger).get('append', absent)
    began = prior = time.perf_counter()
    completed = 0
    with target.open('x') as stream:
        def append(record):
            nonlocal prior, completed
            result = native(record)
            assert record['prediction_order'] == completed
            completed += 1
            if completed % 100 == 0:
                now = time.perf_counter()
                usage = resource.getrusage(resource.RUSAGE_SELF)
                stream.write(json.dumps(dict(completed_trials=completed, configured_trial_count=5000,
                    horizon=5000, wall_seconds=now-began, interval_seconds=now-prior,
                    user_cpu_seconds=usage.ru_utime, system_cpu_seconds=usage.ru_stime,
                    max_worker_rss_bytes=usage.ru_maxrss, epoch_seconds=time.time()))+'\n')
                stream.flush()
                prior = now
            return result
        ledger.append = append
        try:
            yield
        finally:
            if previous is absent:
                del ledger.append
            else:
                ledger.append = previous
