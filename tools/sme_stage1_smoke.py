"""段1の採点の旗の接続と、全新旗オフの比較。出力を上書きしない。"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--trials", type=int, default=20)
    args = ap.parse_args()
    source = Path(__file__).resolve().parents[1]
    flags = ["--nohash", "--vt", "0.3842", "--extend-rule", "none", "--charge1", "d32", "--fast", "--no-public-history",
             "--dump-slot-history", "--fix2-full", "--fix-order2", "--proj-first", "--fill-norestate", "--no-charge2",
             "--own-evidence", "--v39", "--v39-budget", "inf", "--v39-decay", "actr", "--v310-be", "--hist-role",
             "--score-role", "--u-struct", "--relearn-init", "--tie-struct", "--amb-local", "--nsim", "0.7",
             "--ident-rho", "0.5", "--ident-argmax", "--ident-commons", "--cells", "f0.5000_th2.1000_first_order",
             "--dump-answers", "--dump-routing", "--answer-gap", "--strict-pc", "--e-price", "0.01873710622997919",
             "--v39-price", "0.01873710622997919", "--shop-world", "2", "--workers", "1", "--seeds", "1",
             "--trial-count", str(args.trials), "--no-compare"]
    env = dict(os.environ)
    for k in ("LC_CTYPE", "LC_ALL", "LANG"):
        env.pop(k, None)
    env["PYTHONHASHSEED"] = "0"
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [("baseline", args.baseline, []), ("all_off", source, []),
            ("order_only", source, ["--score-arg-order"]),
            ("order_diagnostics", source, ["--score-arg-order", "--cf-value", "--probe-world"])]
    for label, directory, extra in jobs:
        dest = args.output / label
        if dest.exists():
            raise RuntimeError(f"出力先が既にある：{dest}")
        command = [sys.executable, "tools/v3_run.py", "config/sweep_shop_hide1_s1_2026-10-01.json", str(dest), *flags, *extra]
        with (args.output / f"{label}.log").open("w") as log:
            result = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(label, result.returncode, flush=True)
        if result.returncode:
            raise RuntimeError(f"{label} の走行が止まった。ログを残した")
    def record(root):
        ledger = next((root / "ledgers").rglob("seed001.jsonl.gz"))
        with gzip.open(ledger, "rb") as f:
            header, body = f.readline(), f.read()
        files = {str(p.relative_to(root / "side")): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (root / "side").rglob("*") if p.is_file()}
        return {"body_sha256": hashlib.sha256(body).hexdigest(), "body_rows": len(body.splitlines()),
                "side": files, "header": json.loads(header)}
    records = {label: record(args.output / label) for label, _, _ in jobs}
    assert records["baseline"]["body_sha256"] == records["all_off"]["body_sha256"]
    assert records["baseline"]["side"] == records["all_off"]["side"]
    assert records["order_only"]["body_sha256"] == records["order_diagnostics"]["body_sha256"]
    common = records["order_only"]["side"]
    assert all(records["order_diagnostics"]["side"][p] == h for p, h in common.items())
    (args.output / "checks.json").write_text(json.dumps({"trials": args.trials, "seed": 1,
        "environment": {"PYTHONHASHSEED": "0", "locale_variables_removed": ["LC_CTYPE", "LC_ALL", "LANG"]},
        "all_off_body_equal": True, "all_off_side_equal": True,
        "diagnostics_body_equal": True, "diagnostics_common_side_equal": True, "records": records}, ensure_ascii=False, indent=2) + "\n")
    print("4本と比較完了", flush=True)


if __name__ == "__main__":
    main()
