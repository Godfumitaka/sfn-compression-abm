"""2026-09-30 Codex 委任書の専用走行。台帳を残し、種1〜20だけを使う。"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

L90 = "0.09900039055209096"
CFG = "config/sweep_b2_hide_s1_2026-09-22.json"
CELL = "f0.5000_th2.1000_first_order"
FLAGS = ["--nohash", "--vt", "0.3842", "--extend-rule", "none", "--charge1", "d32", "--fast",
         "--no-public-history", "--dump-slot-history", "--fix2-full", "--fix-order2", "--proj-first",
         "--fill-norestate", "--no-charge2", "--own-evidence", "--v39", "--v39-decay", "actr",
         "--v39-budget", "inf", "--v310-be", "--hist-role", "--score-role", "--nsim", "0.7",
         "--ident-rho", "0.5", "--ident-argmax", "--ident-commons", "--cells", CELL, "--no-compare"]
ARMS = [("v310BEhsc_L90", "source-be", L90, 20, False),
        ("v310BEhsc_lam015", "source-be", "0.15", 20, False),
        ("v310BEhsc_lam020", "source-be", "0.2", 20, False),
        ("v310BEhsc_lam030", "source-be", "0.3", 20, False),
        ("v310BEhsc_lam050", "source-be", "0.5", 20, False),
        ("v4vc_L0", "source-v4", "0", 10, True),
        ("v4vc_L90", "source-v4", L90, 10, True)]


def now():
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST")


def body_sha(path):
    """prod_post_one.body_sha と同じ、見出しを除いたUTF-8本体。"""
    h, n = hashlib.sha256(), 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        header = json.loads(next(f))
        for line in f:
            h.update(line.encode("utf-8"))
            n += 1
    return h.hexdigest(), n, header


def progress(base, message):
    path = base / "results/control/2026-09-30_Codex_進み具合.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {now()} {message}\n")
    print(now(), message, flush=True)


def run(base, name, source, price, count, world, dump, workers):
    root = base / "outputs" / name
    if root.exists():
        raise RuntimeError(f"既存の出力を上書きしない：{root}")
    if shutil.disk_usage(base).free < 15_000_000_000:
        raise RuntimeError("空きが15GB未満。腕を始めず停止")
    cmd = [sys.executable, "tools/v3_run.py", CFG, str(root), *FLAGS, "--v39-price", price,
           "--seeds", ",".join(map(str, range(1, count + 1))), "--workers", str(workers)]
    if world:
        cmd += ["--world-cue", "--world-cue-p", "0.8"]
    if dump:
        cmd += ["--dump-answers"]
    logdir = base / "outputs/logs"
    logdir.mkdir(exist_ok=True)
    print(now(), "開始", name, flush=True)
    with (logdir / f"{name}.log").open("x", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=base / source, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, "PYTHONHASHSEED": "0", "PROD_KEEP_SEEDS": "all"})
        last = datetime.now().timestamp()
        while True:
            try:
                rc = proc.wait(timeout=30)
                break
            except subprocess.TimeoutExpired:
                if datetime.now().timestamp() - last >= 1800:
                    done = len(list(root.glob("ledgers/cells/*/seed*.done")))
                    progress(base, f"{name} {done}/{count} 本完了。空き {shutil.disk_usage(base).free / 1e9:.2f} GB。")
                    last = datetime.now().timestamp()
    if rc:
        raise RuntimeError(f"{name} の走行が失敗 rc={rc}。{logdir / (name + '.log')}")
    done = sorted(root.glob("ledgers/cells/*/seed*.done"))
    seeds = [int(p.stem.removeprefix("seed")) for p in done]
    if seeds != list(range(1, count + 1)):
        raise RuntimeError(f"完走した種が不一致：{seeds}")
    records = [json.loads(s) for s in (root / "manifest.jsonl").read_text().splitlines()]
    if len(records) != count or any(r.get("error") or r.get("v39_unfit") for r in records):
        raise RuntimeError(f"manifestの件数またはエラー：{name}")
    if any(r.get("trial_count", 1740) != 1740 for r in records):
        raise RuntimeError("1,740試行と不一致")
    print(now(), "完走", name, len(done), flush=True)
    return root


def validate(base):
    out = []
    for label, source, price, world in [("BE_L90", "source-be", L90, False), ("v4_L0", "source-v4", "0", True)]:
        off = run(base, f"verify_{label}_off", source, price, 1, world, False, 1)
        on = run(base, f"verify_{label}_on", source, price, 1, world, True, 1)
        a, b = next(off.glob("ledgers/cells/*/seed001.jsonl.gz")), next(on.glob("ledgers/cells/*/seed001.jsonl.gz"))
        ha, na, _ = body_sha(a)
        hb, nb, _ = body_sha(b)
        record = {"condition": label, "seed": 1, "trials": 1740, "off": str(a), "on": str(b),
                  "off_body_sha256": ha, "on_body_sha256": hb, "off_records": na, "on_records": nb,
                  "equal": ha == hb and na == nb}
        out.append(record)
        (base / "outputs/validation.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
        if not record["equal"]:
            progress(base, f"★★ {label} seed001 台帳本体不一致。停止。")
            raise RuntimeError("台帳本体不一致")
        progress(base, f"{label} seed001 全1,740試行で記録の有無の台帳本体一致。sha256={ha}、本体 {na} 行。")


def gather(base, root, arm, count):
    dest = base / "results/mac" / arm
    if dest.exists():
        raise RuntimeError(f"既存の結果を上書きしない：{dest}")
    dest.mkdir(parents=True)
    files = sorted(root.glob("side/*/seed*.answers.csv"))
    if len(files) != count:
        raise RuntimeError(f"答えの記録の本数が不一致：{arm}")
    n, header = 0, None
    with gzip.open(dest / f"answers_{arm}.csv.gz", "wt", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        for path in files:
            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                h = next(reader)
                if header is None:
                    header = h
                    writer.writerow(h)
                if h != header:
                    raise RuntimeError("答えの列が不一致")
                for row in reader:
                    writer.writerow(row)
                    n += 1
    shutil.copy2(root / "flag.json", dest / "flag.json")
    hashes = []
    for path in sorted(root.glob("ledgers/cells/*/seed*.jsonl.gz")):
        digest, lines, head = body_sha(path)
        hashes.append({"arm": arm, "seed": int(path.name.split('.')[0].removeprefix("seed")), "cell": path.parent.name,
                       "body_sha256": digest, "records": lines, "ledger": str(path), "bytes": path.stat().st_size,
                       "code_commit": head.get("code_commit"), "deleted": False})
    (dest / "sha256.jsonl").write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in hashes))
    (dest / "README.md").write_text(f"# {arm}：候補の答えを含む記録（Codex）\n\n"
        f"- 走行 {count} 本、各1,740試行、種1〜{count}、答えた試行 {n:,} 行。\n"
        f"- 記録：answers_{arm}.csv.gz。列の意味はコードの tools/answerlog.py。候補の答えは門の下も含め開示前に計算。\n"
        f"- 旗とコードの版：flag.json。本体のsha256（見出しを除いた内容の指紋）：sha256.jsonl。\n"
        f"- 台帳と個別記録はすべて {root} に残した。削除はしていない。\n", encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("validate", "run"))
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if sys.version_info[:3] != (3, 12, 13):
        raise RuntimeError("Python 3.12.13以外では走らせない")
    base = args.workspace.resolve()
    try:
        if args.mode == "validate":
            validate(base)
        else:
            validations = json.loads((base / "outputs/validation.json").read_text())
            if len(validations) != 2 or not all(v["equal"] for v in validations):
                raise RuntimeError("台帳本体の一致を確認する前には本番を始めない")
            for arm, source, price, count, world in ARMS:
                free = shutil.disk_usage(base).free
                # 直前の腕の実測量を使い、次の腕で15GBを割りそうなら区切りで停止。
                previous = [p for p in (base / "outputs").iterdir() if p.name.startswith(("v310BEhsc_", "v4vc_"))]
                projected = max((sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) for p in previous), default=0)
                if free - projected < 15_000_000_000:
                    raise RuntimeError(f"次の腕で15GBを割る見込み。空き{free / 1e9:.2f}GB、直前までの最大腕{projected / 1e9:.2f}GB")
                progress(base, f"{arm} を開始。種1〜{count}、各1,740試行。空き{free / 1e9:.2f}GB。")
                root = run(base, arm, source, price, count, world, True, args.workers)
                rows = gather(base, root, arm, count)
                progress(base, f"{arm} {count}/{count} 本完了。答えの記録{rows:,}行をmac/{arm}/に作成。台帳を全部保持。空き{shutil.disk_usage(base).free / 1e9:.2f}GB。")
    except Exception as e:
        progress(base, f"★★ 停止：{e}")
        raise


if __name__ == "__main__":
    main()
