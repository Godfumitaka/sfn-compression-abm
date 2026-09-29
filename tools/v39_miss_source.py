"""v3.9 の誤答の出どころ（2026-09-29 朝の追記 2）。★ 判断しない。模型は動かさない。台帳と side を読むだけ。
出どころ（実際の発話＝台帳の coverage＝1。誤答＝そのうち hit≠1。tools/v39_summary.py と同じ数え方）：
  F の投影     prediction_path＝projection（v3.9 の投影は F の行だけ。tools/v39.py:545-547、v3.9-main 94e2de6。以下の行番号も同じ版）
  F／H／U の穴埋め  prediction_path＝filling_live・filling_tombstone。話した関係は穴埋めの最初の関係（tools/v39.py:610）で、
               その席の状態は side の kind＝"v39" の fill の最初の組（関係の ID と F/H/U。tools/v39.py:1086）。関係の ID が
               台帳の predicted_edge の relation_id と合うことを確かめ、合わなければ「分からない」に入れる。
生まれた型以外：話した定義の生まれた型（merged/defs_spoke8org_<腕>.csv の born_motif。tools/def_origin.py）と、その試行の型（世界の motif）が違う。
  見つけ方は tools/v39_summary.py と同じ（名前・生まれた試行・消えた試行で同一性を選ぶ）。
使い方  python3.12 tools/v39_miss_source.py <出力の .json> <腕の走行根> [<腕の走行根> …]"""
import collections
import csv
import glob
import gzip
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
from v39_summary import motifs  # noqa: E402

SRC = ("F の投影", "F の穴埋め", "H の穴埋め", "U の穴埋め", "分からない")


def one(args):
    p, side, inc, seedf = args
    fill = {}
    for line in open(side, encoding="utf-8"):
        d = json.loads(line)
        if d.get("kind") == "v39":
            fill[d["trial"]] = d.get("fill") or []
    C = collections.Counter()
    with gzip.open(p, "rt", encoding="utf-8") as f:
        h = json.loads(next(f))
        MOT = motifs(h, seedf)
        for line in f:
            r = json.loads(line)
            if r.get("record_type", "trial") != "trial" or r.get("coverage") != 1:
                continue
            t = r["prediction_order"]
            path = r.get("prediction_path")
            if path == "projection":
                src = "F の投影"
            elif path in ("filling_live", "filling_tombstone"):
                fl = fill.get(t) or []
                pe = r.get("predicted_edge") or {}
                src = f"{fl[0][1]} の穴埋め" if fl and fl[0][0] == pe.get("relation_id") and fl[0][1] in "FHU" else "分からない"
            else:
                src = "分からない"
            miss = r.get("hit") != 1
            C[("発話", src)] += 1
            C[("誤答", src)] += miss
            bm = None
            for born, died, motif in inc.get(r.get("R_used"), ()):
                if born < t and (died is None or t <= died):
                    bm = motif
                    break
            where = "型が分からない" if bm is None else ("生まれた型以外" if bm != MOT[t] else "生まれた型")
            C[(f"発話_{where}", src)] += 1
            C[(f"誤答_{where}", src)] += miss
    return p, C


def arm_counts(root):
    root = Path(root)
    arm = root.name
    fl = json.load(open(root / "flag.json", encoding="utf-8"))
    cfg = json.load(open(REPO / fl["config"], encoding="utf-8"))
    seedf = str(REPO / cfg.get("seed_file", "seeds/U-011_seed_v3a2.json"))
    inc = collections.defaultdict(lambda: collections.defaultdict(list))
    csvp = root / "merged" / f"defs_spoke8org_{arm}.csv"
    for row in csv.DictReader(open(csvp, encoding="utf-8")):
        cell, seed, K = row["defid"].split("/")
        R, born = K.rsplit("@", 1)
        died = row.get("died")
        inc[(cell, seed)][R].append((int(born), int(died) if died not in (None, "") else None, row.get("born_motif") or None))
    jobs = []
    for p in sorted(glob.glob(str(root / "ledgers/cells/*/seed*.jsonl.gz"))):
        cell = os.path.basename(os.path.dirname(p))
        sd = os.path.basename(p)[:7]
        if not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
            continue
        jobs.append((p, str(root / "side" / cell / f"{sd}.jsonl"), dict(inc[(cell, sd)]), seedf))
    with Pool(4) as pool:
        res = pool.map(one, jobs)
    tot = collections.Counter()
    for _, c in res:
        tot.update(c)
    return {"腕": arm, "走行": len(res), "予算": fl.get("v39_budget"), "U": fl.get("v39_u"),
            "数": {f"{k[0]}|{k[1]}": v for k, v in sorted(tot.items())}}


if __name__ == "__main__":
    out = sys.argv[1]
    json.dump([arm_counts(r) for r in sys.argv[2:]], open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out)
