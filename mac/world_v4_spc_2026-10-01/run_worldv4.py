"""指定された世界 v4 の走行だけを、Codex の場所と Python 3.12.13 で開始する。"""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "source"
PYTHON = "/opt/homebrew/opt/python@3.12/bin/python3.12"
CELL = "f0.5000_th2.1000_vt0.3842_first_order"
CONFIG = "config/sweep_b2_hide_s1_2026-09-22.json"
COMMON = "--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap --strict-pc --cf-value --probe-world --workers 1 --no-compare --e-price 0.01873710622997919".split()
PRICES = [("lam000", "0"), ("L50", "0.0187371"), ("L90", "0.0990004"), ("lam020", "0.2"), ("lam030", "0.3")]
ARMS = {f"v4spc_{condition}_{label}": dict(condition=condition, price=price, world_cue=0.8)
        for condition in ("A", "C") for label, price in PRICES if condition == "A" or price != "0"}
ARMS["gate_plain_A_lam020"] = dict(condition="A", price="0.2", world_cue=None)

def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")

def run_root(arm, seed):
    if not 1 <= seed <= 20:
        raise ValueError("指定の種 1〜20 のみ")
    return ROOT / "runs" / arm / f"seed{seed:03d}"

def completed(arm, seed):
    root = run_root(arm, seed)
    path = root / "manifest.jsonl"
    if not path.exists():
        return False
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return len(rows) == 1 and not rows[0].get("error") and (root / "ledgers/cells" / CELL / f"seed{seed:03d}.done").exists()

def directory_bytes(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())

def event(**values):
    with (ROOT / "run_events.jsonl").open("a") as out:
        out.write(json.dumps(dict(time=now(), **values), ensure_ascii=False) + "\n")

def run_one(arm, seed, reserve_bytes=2_000_000_000):
    root = run_root(arm, seed)
    if (ROOT / "STOP_NEW_RUNS").exists():
        raise RuntimeError("新しい走行を止める記録がある: STOP_NEW_RUNS")
    if completed(arm, seed):
        return dict(arm=arm, seed=seed, reused=True, bytes=directory_bytes(root))
    if root.exists():
        raise RuntimeError(f"途中の出力は上書きしない: {root}")
    free = shutil.disk_usage(ROOT).free
    if free - reserve_bytes < 15_000_000_000:
        raise RuntimeError(f"空き容量の関門: 空き {free} バイト、見込み {reserve_bytes} バイト")
    info = ARMS[arm]
    argv = [PYTHON, "tools/v3_run.py", CONFIG, str(root), *COMMON, "--v39-price", info["price"], "--seeds", str(seed)]
    if info["world_cue"] is not None:
        argv += ["--world-cue", "--world-cue-p", str(info["world_cue"])]
    if info["condition"] == "C":
        argv += ["--cf-learn"]
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    (logs / f"{arm}_seed{seed:03d}.argv.json").write_text(json.dumps(argv, ensure_ascii=False, indent=1) + "\n")
    event(kind="start", arm=arm, seed=seed, free_bytes=free, reserve_bytes=reserve_bytes)
    with (logs / f"{arm}_seed{seed:03d}.log").open("x") as log:
        rc = subprocess.run(argv, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc or not completed(arm, seed):
        event(kind="failed", arm=arm, seed=seed, returncode=rc)
        raise RuntimeError(f"走行の失敗: {arm} seed{seed:03d}, returncode={rc}")
    result = dict(arm=arm, seed=seed, returncode=rc, bytes=directory_bytes(root))
    event(kind="finished", **result)
    return result

def production(workers):
    if not (ROOT / "gate1_passed.json").exists():
        raise RuntimeError("関門1の検証記録がない")
    jobs = [(arm, seed) for arm in ARMS if arm.startswith("v4spc_") for seed in range(1, 21)]
    sizes = [directory_bytes(run_root(a, s)) for a, s in jobs if completed(a, s)]
    estimate = max([2_000_000_000, *sizes])
    done = sum(completed(a, s) for a, s in jobs)
    print(f"{now()} 本番 {done}/180 完了、並列 {workers}", flush=True)
    pending = iter((a, s) for a, s in jobs if not completed(a, s))
    active = {}
    last_progress = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            while len(active) < workers:
                if (ROOT / "STOP_NEW_RUNS").exists():
                    raise RuntimeError("新しい走行を止める記録がある: STOP_NEW_RUNS")
                job = next(pending, None)
                if job is None:
                    break
                reserve = estimate * (len(active) + 1)
                free = shutil.disk_usage(ROOT).free
                if free - reserve < 15_000_000_000:
                    event(kind="disk_stop", free_bytes=free, reserve_bytes=reserve, completed=done)
                    raise RuntimeError(f"空き容量の関門で停止: {done}/180")
                active[pool.submit(run_one, *job, reserve)] = job
            if not active:
                break
            finished, _ = concurrent.futures.wait(active, timeout=30, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                active.pop(future)
                result = future.result()
                estimate = max(estimate, result["bytes"])
                done += 1
                print(f"{now()} {done}/180 {result['arm']} seed{result['seed']:03d} {result['bytes']/1e9:.3f}GB", flush=True)
            if time.monotonic() - last_progress >= 1800:
                free = shutil.disk_usage(ROOT).free
                message = f"- {now()} 世界v4の取り直し：本番 {done}/180 本完了、進行中 {len(active)} 本、空き {free/1e9:.3f}GB。\n"
                with (ROOT / "results/control/2026-09-30_Codex_進み具合.md").open("a") as out:
                    out.write(message)
                last_progress = time.monotonic()
    return dict(completed=done, total=180)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--one", nargs=2, metavar=("ARM", "SEED"))
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2, 4))
    args = parser.parse_args()
    print(json.dumps(run_one(args.one[0], int(args.one[1])) if args.one else production(args.workers), ensure_ascii=False), flush=True)
