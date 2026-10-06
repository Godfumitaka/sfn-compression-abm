"""旧版と同じ条件へSMEの旗だけを足す。共有受付とCPU枠を併用する。"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT.parent
PYTHON = "/opt/homebrew/bin/python3.12"
CELL = "f0.5000_th2.1000_vt0.3842_first_order"
CONFIG = "config/sweep_shop_hide1_s1_2026-10-01.json"
LAMBDA = "0.01873710622997919"


def command(out, world, seed, retention="A", level=None, trials=1740):
    assert world in (1, 2) and 1 <= seed <= 5 and retention in ("A", "D")
    args = [PYTHON, "-B", "tools/v3_run.py", CONFIG, str(out),
        "--nohash", "--vt", "0.3842", "--extend-rule", "none", "--charge1", "d32",
        "--fast", "--no-public-history", "--dump-slot-history", "--fix2-full", "--fix-order2",
        "--proj-first", "--fill-norestate", "--no-charge2", "--own-evidence", "--v39",
        "--v39-budget", "inf", "--v39-decay", "actr", "--v310-be", "--hist-role", "--score-role",
        "--u-struct", "--relearn-init", "--tie-struct", "--amb-local", "--nsim", "0.7",
        "--ident-rho", "0.5", "--ident-argmax", "--ident-commons", "--dump-answers", "--dump-routing",
        "--answer-gap", "--strict-pc", "--cf-value", "--probe-world", "--e-price", LAMBDA,
        "--no-compare", "--cells", "f0.5000_th2.1000_first_order", "--workers", "1",
        "--seeds", str(seed), "--shop-world", str(world), "--v39-price", LAMBDA,
        "--sme2017", "--sme-call-seed", "--sme-tie-uniform", "--sme-intern-cache", "--sme-evict-trial-cache",
        "--trial-count", str(trials), "--horizon", "1740"]
    if retention == "D":args += ["--use-forget", "0.4"]
    if level is not None:
        assert level in ("skeleton", "current", "plus4", "plus8")
        args += ["--shop-deco", level]
    return args


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):h.update(block)
    return h.hexdigest()


def registered(args, out, tag, *, cwd=ROOT, mem=1.0, result_file=None):
    out = Path(out);out.mkdir(parents=True, exist_ok=True)
    if (out / "resources.json").exists():
        previous = json.loads((out / "resources.json").read_text())
        assert json.loads((out / "command.json").read_text())["command"] == args
        assert previous["exit_code"] == 0
        assert (out / (result_file or "manifest.jsonl")).is_file()
        if result_file is None:
            assert len(previous["manifest"]) == 1 and not previous["manifest"][0].get("error")
        return previous
    guarded = [PYTHON, "-B", str(ROOT / "control/shop_deco_sme_2026-10-06/cpu_guard.py"),
        "--cwd", str(cwd), "--log", str(out / "cpu.jsonl"), "--", *args]
    queue = ["/usr/bin/python3", "/Users/tatsu-admin/jobs/jobs.py", "run", "--wait", "--owner", tag,
        "--mem", str(mem), "--disk-path", str(out), "--", *guarded]
    (out / "command.json").write_text(json.dumps({"command": args, "cwd": str(cwd),
        "registered_command": queue, "environment": {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}},
        ensure_ascii=False, indent=2) + "\n")
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    started = time.monotonic();peak = 0
    with (out / "run.log").open("w") as log:
        process = subprocess.Popen(queue, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            lines = subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,rss="], text=True).splitlines()
            rows = {int(p): (int(parent), int(rss) * 1024) for p, parent, rss in (s.split() for s in lines)}
            chosen = {process.pid}
            while True:
                extra = {p for p, (parent, _rss) in rows.items() if parent in chosen}
                if extra <= chosen:break
                chosen |= extra
            peak = max(peak, sum(rows[p][1] for p in chosen if p in rows))
            time.sleep(0.5)
    manifests = [json.loads(s) for s in (out / "manifest.jsonl").read_text().splitlines()] if (out / "manifest.jsonl").exists() else []
    resources = {"tag": tag, "exit_code": process.returncode, "queue_and_run_sec": time.monotonic() - started,
        "peak_descendants_rss_bytes": peak, "memory_budget_gb": mem,
        "logical_output_bytes": sum(p.stat().st_size for p in out.rglob("*") if p.is_file()),
        "allocated_output_bytes": int(subprocess.check_output(["/usr/bin/du", "-sk", str(out)], text=True).split()[0]) * 1024,
        "manifest": manifests}
    (out / "resources.json").write_text(json.dumps(resources, ensure_ascii=False, indent=2) + "\n")
    assert process.returncode == 0, f"受付の実行が不通: {out}"
    assert peak <= mem * 1e9, f"受付の見込みを超えた: {out}"
    if result_file is None:assert len(manifests) == 1 and not manifests[0].get("error")
    else:assert (out / result_file).is_file()
    return resources
