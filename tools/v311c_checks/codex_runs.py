"""午後の委任書の検査と一対一。既存の出力を上書きせず、台帳をすべて残す。"""
from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

SOURCE = Path(__file__).resolve().parents[2]
ROOT = SOURCE.parent
BASE = ROOT / "baseline"
PY = "/opt/homebrew/opt/python@3.12/bin/python3.12"
CELL = "f0.5000_th2.1000_vt0.3842_first_order"
FLAGS = "--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v39-price 0.01873710622997919 --v310-be --hist-role --score-role --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --no-compare".split()
FLAGS += "--u-struct --relearn-init --tie-struct --amb-local".split()
COLLECTIVE = "--v311c --v311c-f 0.5,0.5 --v311c-runs 1 --workers 1".split()


def run_job(job):
    name, source, count, extra = job
    dest = ROOT / "outputs" / name
    if dest.exists():
        raise RuntimeError(f"既存の出力がある：{dest}")
    log = ROOT / "outputs" / (name + ".log")
    if log.exists():
        raise RuntimeError(f"既存の記録がある：{log}")
    cmd = [PY, "tools/v3_run.py", "config/sweep_b2_hide_s1_2026-09-22.json", str(dest), *FLAGS,
           "--trial-count", str(count), *extra]
    start = time.monotonic()
    with log.open("w") as f:
        p = subprocess.run(cmd, cwd=source, stdout=f, stderr=subprocess.STDOUT)
    summaries = [json.loads(p.read_text()) for p in sorted((dest / "comm").glob("*.summary.json"))]
    if p.returncode or any(s.get("errors") or s.get("trials") != count for s in summaries):
        raise RuntimeError(f"走行失敗：{name}（終了 {p.returncode}）：{summaries}")
    if "--v311c" in extra and not summaries:
        raise RuntimeError(f"集団の要約が無い：{name}")
    print(json.dumps({"job": name, "seconds": round(time.monotonic()-start, 2), "populations": len(summaries)}, ensure_ascii=False), flush=True)
    return name


def body(name, seed):
    p = ROOT / "outputs" / name / "ledgers" / "cells" / CELL / f"seed{seed:03d}.jsonl.gz"
    h = hashlib.sha256()
    n = 0
    with gzip.open(p, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            h.update(line.encode("utf-8"))
            n += 1
    return {"sha256": h.hexdigest(), "rows": n}


def checks():
    jobs = [
        ("off_base", BASE, 1740, ["--seeds", "1", "--workers", "1"]),
        ("off_port", SOURCE, 1740, ["--seeds", "1", "--workers", "1"]),
        ("notags", SOURCE, 300, COLLECTIVE + ["--v311c-no-tags"]),
        ("short_ind", SOURCE, 300, ["--seeds", "1", "--workers", "1"]),
        ("solo_notags", SOURCE, 300, ["--v311c", "--v311c-f", "0.5", "--v311c-no-tags", "--v311c-runs", "1001", "--workers", "1"]),
        ("q0", SOURCE, 300, COLLECTIVE + ["--v311c-q", "0"]),
        ("solo_q0", SOURCE, 300, ["--v311c", "--v311c-f", "0.5", "--v311c-q", "0", "--v311c-b-n", "2", "--v311c-runs", "1,1001", "--workers", "1"]),
        ("repeat1", SOURCE, 300, COLLECTIVE + ["--v311c-q", "0.5", "--v311c-recv", "B", "--v311c-probe-every", "10"]),
        ("repeat2", SOURCE, 300, COLLECTIVE + ["--v311c-q", "0.5", "--v311c-recv", "B", "--v311c-probe-every", "10"]),
        ("noprobe", SOURCE, 300, COLLECTIVE + ["--v311c-q", "0.5", "--v311c-recv", "B", "--v311c-probe-every", "0"]),
        ("recvA_check", SOURCE, 300, COLLECTIVE + ["--v311c-q", "0.5", "--v311c-recv", "A", "--v311c-probe-every", "10"]),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(run_job, jobs))
    pairs = [("off_base", "off_port", 1), ("short_ind", "notags", 1), ("solo_notags", "notags", 1001),
             ("q0", "solo_q0", 1), ("q0", "solo_q0", 1001), ("repeat1", "repeat2", 1),
             ("repeat1", "repeat2", 1001), ("repeat1", "noprobe", 1), ("repeat1", "noprobe", 1001)]
    report = []
    for a, b, seed in pairs:
        x, y = body(a, seed), body(b, seed)
        report.append({"a": a, "b": b, "seed": seed, "left": x, "right": y, "equal": x == y})
    def comm_hash(name):
        h = hashlib.sha256()
        for line in (ROOT / "outputs" / name / "comm" / "run001.jsonl").read_text().splitlines(True):
            if json.loads(line).get("kind") != "summary":
                h.update(line.encode())
        return h.hexdigest()
    out = {"body_pairs": report, "comm_repeat_equal": comm_hash("repeat1") == comm_hash("repeat2")}
    (ROOT / "outputs" / "checks_hashes.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
    assert all(x["equal"] for x in report), out
    assert out["comm_repeat_equal"], out
    print("台帳本体9組・通信1組の一致を確認", flush=True)


def main_runs():
    jobs = []
    for name, recv, q in (("recvA", "A", "0.2"), ("recvB", "B", "0.2"), ("no_comm", "B", "0")):
        extra = ["--v311c", "--v311c-f", "0.5,0.5", "--v311c-runs", "1,2,3", "--workers", "1",
                 "--v311c-q", q, "--v311c-recv", recv]
        jobs.append((name, SOURCE, 1740, extra))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(run_job, jobs))


if __name__ == "__main__":
    {"checks": checks, "main": main_runs}[sys.argv[1]]()
