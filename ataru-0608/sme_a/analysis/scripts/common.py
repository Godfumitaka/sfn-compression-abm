"""(a) 版の本番の解析で共通に使う場所と読み方。読むだけ。本番の出力・作業場所には書かない。"""
import glob
import gzip
import hashlib
import json
import os
from pathlib import Path

HOME = Path.home()
A_ROOT = HOME / "smeprod_a" / "sme"            # (a) 版の本番（読むだけ）
OLD_ROOT = HOME / "smeprod" / "sme"            # 古い本番（台帳だけ残っている。読むだけ）
OLD_SHA = HOME / "v33prod/results/ataru-0608/sme_6e93e0b"   # 古い本番の一本ごとの sha256（読むだけ）
PLAN_EVICT = HOME / "smeprod_a/plan/sme.commands.evict.json"
PLAN_ORIG = HOME / "smeprod_a/plan/sme.commands.json"
REPLAY_SRC = HOME / "sfn/audit/_read/smeevict"   # 再生に使う作業場所（10cd8bd、読むだけ）
REPLAY_COMMIT = "10cd8bdd46416aff55d0015e9072fc2186deed83"
WORK = HOME / "sme_analysis"
OUT = WORK / "out"
REPLAY_DIR = WORK / "replay"     # 一本ごとの再生の結果（候補の記録・確かめ・時間）
MEM_DIR = WORK / "memcmp"        # 一本ごとの記憶の比べの結果
TMP = WORK / "tmp"
ARMS = ["w2_A_L50", "w1_A_L50", "w2_A_zero", "w1_A_zero", "w2_D_tau04", "w1_D_tau04", "w2_C_L50", "w1_C_L50"]
SEEDS = range(1, 21)   # 種 21〜40 は読まない
CELL = "f0.5000_th2.1000_vt0.3842_first_order"


def run_dir(arm, seed):
    return A_ROOT / arm / f"seed{seed:03d}"


def is_complete(arm, seed):
    """完了の印（ledgers/cells/*/seedNNN.done）がある本だけを完了とする。"""
    d = run_dir(arm, seed)
    return bool(glob.glob(str(d / "ledgers/cells/*" / f"seed{seed:03d}.done")))


def complete_runs():
    for arm in ARMS:
        for seed in SEEDS:
            if is_complete(arm, seed):
                yield arm, seed


def run_commit(arm, seed):
    return json.loads((run_dir(arm, seed) / "flag.json").read_text())["commit"]


def ledger_path(root_dir, seed):
    p = glob.glob(str(Path(root_dir) / "ledgers/cells/*" / f"seed{seed:03d}.jsonl.gz"))
    assert len(p) == 1, (root_dir, p)
    return Path(p[0])


def side_dir(root_dir):
    p = glob.glob(str(Path(root_dir) / "side/*/"))
    assert len(p) == 1, (root_dir, p)
    return Path(p[0])


def ledger_rows(path):
    """台帳の行を順に返す（見出しの行も含む）。"""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_csv(path, rows, fields):
    import csv
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, path)


def jdump(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def diff_paths(a, b, prefix=""):
    """二つの JSON の値の違う場所を「欄.欄.[]」の形で返す（Codex の (1) の書き方に合わせた）。"""
    if type(a) is not type(b):
        return [prefix or "(全体)"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            p = f"{prefix}.{k}" if prefix else str(k)
            if k not in a or k not in b:
                out.append(p)
            elif a[k] != b[k]:
                out.extend(diff_paths(a[k], b[k], p))
        return out
    if isinstance(a, list):
        p = f"{prefix}.[]" if prefix else "[]"
        if len(a) != len(b):
            return [p + "(長さ)"]
        out = []
        for x, y in zip(a, b):
            if x != y:
                out.extend(diff_paths(x, y, p))
        return sorted(set(out))
    return [prefix or "(全体)"] if a != b else []
