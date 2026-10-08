"""台帳の追記後に時間を観察する。状態・乱数・台帳の内容は変えない。"""
from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

ST = {}


def install(path):
    import abm.ledger as ledger
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    ST.clear()
    ST.update(stream=dest.open("x"), start=start, previous=start, points=0)
    real = ledger.Ledger.append

    def append(self, record):
        result = real(self, record)
        n = int(record["prediction_order"]) + 1
        if n % 1000 == 0:
            now = time.perf_counter()
            usage = resource.getrusage(resource.RUSAGE_SELF)
            row = {"completed_trials": n, "epoch_seconds": time.time(),
                   "elapsed_seconds": now - start, "interval_seconds": now - ST["previous"],
                   "cumulative_max_rss_bytes": int(usage.ru_maxrss) * (1 if sys.platform == "darwin" else 1024),
                   "user_cpu_seconds": usage.ru_utime, "system_cpu_seconds": usage.ru_stime}
            ST["stream"].write(json.dumps(row) + "\n")
            ST["stream"].flush()
            ST["previous"] = now
            ST["points"] += 1
        return result

    ledger.Ledger.append = append


def close():
    ST["stream"].close()
    return {"checkpoints": ST["points"], "elapsed_seconds": time.perf_counter() - ST["start"]}
