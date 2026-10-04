#!/usr/bin/env python3
"""ディスク条件を試しの受付表で確かめる。本物の表への書込・sampler開始・処理停止は行わない。"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("jobs.py")
    scratch = Path(tempfile.mkdtemp(prefix="jobs-disk-test-20261004-"))
    real_registry = Path.home() / "jobs" / "registry.tsv"
    before = digest(real_registry)
    os.environ["JOBS_DIR"] = str(scratch)
    os.environ["JOBS_SWAP"] = str(scratch / "swap.tsv")
    spec = importlib.util.spec_from_file_location("jobs_disk_test", source)
    jobs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jobs)
    assert Path(jobs.REG) == scratch / "registry.tsv"
    assert Path(jobs.SWAP) == scratch / "swap.tsv"
    assert jobs.ensure_sampler() is True
    t = time.time()
    (scratch / "swap.tsv").write_text("".join(f"{t - 600 + 60 * n}\t1024\ttest\tok\t100\n" for n in range(11)))
    # 現在の重い Python は試しの表だけに 0 GB として登録し、既存の四条件を通す。
    ps = jobs.procs()
    seeds = [{"pid": p, "owner": "試しの表の既存処理", "mem_gb": 0.0,
              "start": jobs.now(), "cmd": "試験用の登録"}
             for p, (_pp, rss, command) in ps.items()
             if jobs.heavy(command, rss) and p != os.getpid()]
    jobs.write_reg(seeds)
    target = scratch / "未作成の出力先" / "runs"
    args = SimpleNamespace(owner="ディスク条件の試験", mem=0.1, kind=None,
                           pid=os.getpid(), cmd="ディスク条件だけの試験", disk_path=str(target))
    Usage = namedtuple("usage", "total used free")
    records = []
    for free_gib, expected in [(20, 0), (19.5, 1)]:
        jobs.write_reg(seeds)
        baseline = Path(jobs.REG).read_bytes()
        output = io.StringIO()
        free = int(free_gib * 1024 ** 3)
        with patch.object(jobs.shutil, "disk_usage", return_value=Usage(100 * 1024 ** 3, 100 * 1024 ** 3 - free, free)) as measurement:
            with contextlib.redirect_stdout(output):
                rc = jobs.cmd_claim(args)
        text = output.getvalue()
        assert rc == expected, text
        assert measurement.call_args.args == (str(scratch.resolve()),), measurement.call_args
        rows = jobs.read_reg()
        if expected == 0:
            assert any(r["pid"] == os.getpid() for r in rows), rows
        else:
            assert Path(jobs.REG).read_bytes() == baseline
            assert "ディスクの空きが足りない" in text and "19.500 GiB" in text, text
            assert text.count("  -") == 1, text
        records.append({"free_gib": free_gib, "expected_rc": expected, "actual_rc": rc,
                        "output": text.strip(), "test_registry": jobs.REG,
                        "registry_unchanged_on_refusal": Path(jobs.REG).read_bytes() == baseline if expected == 1 else None})
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        jobs.cmd_status(SimpleNamespace(disk_path=str(scratch)))
    status = output.getvalue()
    assert "# ディスクの空き" in status and "GiB、下限 20 GiB" in status, status
    # run にも同じ出力先が渡り、拒否時に実行されないことを確かめる。
    marker = scratch / "実行されたら残るファイル"
    run_args = SimpleNamespace(owner=args.owner, mem=0.1, kind=None, wait=False,
                               disk_path=str(target), command=[sys.executable, "-c", "from pathlib import Path; Path(__import__('sys').argv[1]).touch()", str(marker)])
    with patch.object(jobs.shutil, "disk_usage", return_value=Usage(100 * 1024 ** 3, 81 * 1024 ** 3, 19 * 1024 ** 3)):
        with contextlib.redirect_stdout(io.StringIO()):
            assert jobs.cmd_run(run_args) == 1
    assert not marker.exists()
    after = digest(real_registry)
    result = {"source": str(source.resolve()), "scratch": str(scratch), "cases": records,
              "status_disk_line": next(line for line in status.splitlines() if "GiB、下限" in line),
              "run_refused_without_execution": True, "real_registry_sha256_before": before,
              "real_registry_sha256_after": after, "real_registry_unchanged_during_test": before == after,
              "mocked_value": "shutil.disk_usage の戻り値のみ。スワップは試験用の平らな10分記録。ps・熱・メモリは実測。",
              "sampler_started": False, "signals_sent": False}
    (scratch / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
