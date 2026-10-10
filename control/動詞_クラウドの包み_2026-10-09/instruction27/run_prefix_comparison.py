"""指示34。既存受付の内側で、同機械100の読取比較を一度だけ行う。"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from run_registered import start_counts
from prefix_gate_compare import compare


def admitted_compare(original, candidate, destination, clearance):
    original, candidate, destination = map(Path, (original, candidate, destination))
    assert not destination.exists(), '同じ比較を再投入しない'
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    proof = json.loads(Path(clearance).read_text())
    assert sys.platform.startswith('linux') and 0 <= time.time()-proof['checked_epoch'] <= 60
    assert proof['memory_reservation_gb'] == 0.3 and proof['memory_admission_ok']
    assert proof['swap_stable_10min'] and proof['thermal_ok'] and proof['warning'] is False
    boot = hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
    assert proof['machine_boot_sha256'] == boot
    for case in (original, candidate):
        assert json.loads((case/'machine_before_start.json').read_text())['machine_boot_sha256'] == boot
    limit = proof['cpu_budget']
    assert limit == proof['physical_cpu_count']-2 and len(os.sched_getaffinity(0)) >= 1
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    counts = start_counts(raw)
    model_limit = limit if proof.get('dedicated_google_cloud_gate_and_production_machine') is True else 8
    assert counts['model_process_count'] <= model_limit and counts['unknown_active_spawn'] == 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert counts['outside_heavy']+1 <= limit and shutil.disk_usage(destination.parent).free >= 20*2**30
    # 進行・資源の札を結果のglobへ混ぜない。原psは別の非公開runtimeへ残す。
    runtime = candidate/'prefix_comparison_runtime'
    runtime.mkdir(exist_ok=False)
    (runtime/'before_start.json').write_text(json.dumps(dict(checked_epoch=time.time(), processes=raw, **counts))+'\n')
    return compare(original, candidate, destination)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('original'); p.add_argument('candidate'); p.add_argument('destination')
    p.add_argument('--clearance', required=True)
    a = p.parse_args()
    raise SystemExit(admitted_compare(a.original, a.candidate, a.destination, a.clearance))
