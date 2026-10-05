"""下見と関門の共通条件。重い走行を一本ずつ共有受付へ渡す。"""
from pathlib import Path
import gzip
import hashlib
import json
import os
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT.parent
PYTHON = "/opt/homebrew/bin/python3.12"
JOBS = "/Users/tatsu-admin/jobs/jobs.py"
LAMBDA = "0.01873710622997919"
CELL = "f0.5000_th2.1000_vt0.3842_first_order"
CONFIG = ROOT / "config/sweep_shop_hide1_s1_2026-10-01.json"


def command(config, out, selection, retention, world, seed, level):
    assert selection in ("N3", "support") and retention in ("A", "D")
    assert world in (1, 2) and 1 <= seed <= 20
    args = [PYTHON, "-B", "tools/v3_run.py", str(config), str(out),
        "--nohash", "--vt", "0.3842", "--extend-rule", "none", "--charge1", "d32",
        "--fast", "--no-public-history", "--dump-slot-history", "--fix2-full", "--fix-order2",
        "--proj-first", "--fill-norestate", "--no-charge2", "--own-evidence", "--v39",
        "--v39-budget", "inf", "--v39-decay", "actr", "--v310-be", "--hist-role", "--score-role",
        "--u-struct", "--relearn-init", "--tie-struct", "--amb-local", "--nsim", "0.7",
        "--ident-rho", "0.5", "--ident-argmax", "--ident-commons", "--dump-answers", "--dump-routing",
        "--answer-gap", "--strict-pc", "--cf-value", "--probe-world", "--e-price", LAMBDA,
        "--no-compare", "--cells", "f0.5000_th2.1000_first_order", "--workers", "1",
        "--seeds", str(seed), "--shop-world", str(world), "--v39-price", LAMBDA]
    if selection == "N3":
        args += ["--select-n3"]
    if retention == "D":
        args += ["--use-forget", "0.4"]
    if level is not None:
        assert level in ("skeleton", "current", "plus4", "plus8")
        args += ["--shop-deco", level]
    return args


def descendants_rss(pid):
    # 他の仕事の引数は読み出さない。共有受付の子孫だけのRSSを合計する。
    lines = subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,rss="], text=True).splitlines()
    rows = {int(p): (int(parent), int(rss) * 1024) for p, parent, rss in (s.split() for s in lines)}
    chosen = {pid}
    while True:
        extra = {p for p, (parent, _) in rows.items() if parent in chosen}
        if extra <= chosen:
            return sum(rows[p][1] for p in chosen if p in rows)
        chosen |= extra


def registered(args, out, tag, mem=0.5, result_file=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "resources.json").exists():
        previous = json.loads((out / "resources.json").read_text())
        assert json.loads((out / "command.json").read_text())["command"] == args
        assert previous["exit_code"] == 0
        if result_file is None:
            assert len(previous["manifest"]) == 1 and not previous["manifest"][0].get("error")
        else:
            assert (out / result_file).is_file()
        return previous
    queue_cmd = ["/usr/bin/python3", JOBS, "run", "--wait", "--owner", tag,
                 "--mem", str(mem), "--disk-path", str(out), "--", *args]
    (out / "command.json").write_text(json.dumps({"command": args, "registered_command": queue_cmd,
        "environment": {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}}, ensure_ascii=False, indent=2) + "\n")
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    started = time.monotonic()
    peak = 0
    with (out / "run.log").open("w") as log:
        process = subprocess.Popen(queue_cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            peak = max(peak, descendants_rss(process.pid))
            time.sleep(0.5)
    logical_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    allocated_bytes = int(subprocess.check_output(["/usr/bin/du", "-sk", str(out)], text=True).split()[0]) * 1024
    manifest = [json.loads(s) for s in (out / "manifest.jsonl").read_text().splitlines()] if (out / "manifest.jsonl").exists() else []
    record = {"tag": tag, "exit_code": process.returncode, "queue_and_run_sec": time.monotonic() - started,
        "peak_descendants_rss_bytes": peak, "logical_output_bytes": logical_bytes,
        "allocated_output_bytes": allocated_bytes, "manifest": manifest}
    (out / "resources.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    complete = (len(manifest) == 1 and not manifest[0].get("error")) if result_file is None else (out / result_file).is_file()
    if process.returncode or not complete:
        raise RuntimeError(f"走行が完了しない: {tag}; resources.jsonとrun.logを参照")
    return record


def without_measured_sec(data):
    """承認されたcfvalueのsec_trial値だけを除く。ほかの文字・順・空白は保つ。"""
    pattern = rb'("sec_trial"\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?=\s*[,}])'
    out = []
    for line in data.splitlines(keepends=True):
        record = json.loads(line)
        assert isinstance(record["sec_trial"], (int, float))
        stripped, n = re.subn(pattern, rb'\1<measured_time>', line)
        assert n == 1
        out.append(stripped)
    return b"".join(out)


def compare_pair(off, current):
    ledger_off = Path(off) / "ledgers" / "cells" / CELL / "seed001.jsonl.gz"
    ledger_current = Path(current) / "ledgers" / "cells" / CELL / "seed001.jsonl.gz"
    # 台帳本体は圧縮を解いた全バイト（ヘッダを含む）。行や欄を除外しない。
    a, b = gzip.decompress(ledger_off.read_bytes()), gzip.decompress(ledger_current.read_bytes())
    result = {"ledger_body_equal": a == b, "ledger_body_sha256_off": hashlib.sha256(a).hexdigest(),
              "ledger_body_sha256_current": hashlib.sha256(b).hexdigest(), "side": {}}
    def side_files(root):
        return {str(p.relative_to(Path(root) / "side")): p for p in (Path(root) / "side").rglob("*") if p.is_file()}
    old, new = side_files(off), side_files(current)
    result["side_file_sets_equal"] = set(old) == set(new)
    for name in sorted(set(old) | set(new)):
        x = old[name].read_bytes() if name in old else None
        y = new[name].read_bytes() if name in new else None
        xc, yc = x, y
        exception = None
        if name.endswith(".cfvalue.jsonl") and x is not None and y is not None:
            xc, yc = without_measured_sec(x), without_measured_sec(y)
            exception = "sec_trial value only; original files unchanged"
        result["side"][name] = {"equal": xc == yc, "raw_equal": x == y, "exception": exception,
            "off_sha256": hashlib.sha256(x).hexdigest() if x is not None else None,
            "current_sha256": hashlib.sha256(y).hexdigest() if y is not None else None,
            "comparison_off_sha256": hashlib.sha256(xc).hexdigest() if xc is not None else None,
            "comparison_current_sha256": hashlib.sha256(yc).hexdigest() if yc is not None else None}
    result["passed"] = result["ledger_body_equal"] and result["side_file_sets_equal"] and all(
        r["equal"] for r in result["side"].values())
    return result
