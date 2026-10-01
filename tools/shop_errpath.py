"""お店の世界：誤答の経路の仮の分類（予約の委任書「手がかりの世界」の 6-5、研究者の側）。★ 読むだけ。分類の決め方は仮の決定。
対象：ドアの課題（伏せた関係がドア）で、答えて外れた試行。
「その状況（店 × シール）用の区別を持つ定義」＝予測の直前の状態の定義のうち、次の三つを満たすもの（仮の決定）。
  ・シールの席（関係 ID がシール：tools/shopworld.py の IDS）の名（F は固定の名、H は履歴の名（回数 1 以上）、U は無し）に、今のシールの述語（sig_n／sig_e）がある。
  ・ドアの席（関係 ID がどこかの試行のドア）の名に、その状況の正しいドアの述語（世界の表）がある。
  ・定義が生まれた試行の場面の店（研究者の側の型）が、今の店と同じ。
分類：(a) その状況用の区別を持つ定義が、走行の始めから今まで一度もできていない
      (b) 前はあったが、今の予測の直前の状態には無い（同化か忘却で失われた後）
      (c) 今あるのに、別の定義を選んだ（台帳の R_used が区別を持つ定義でない）
      (d) 今あって、それを選んだのに外れた（参考）
使い方  python3.12 tools/shop_errpath.py <出力の .json> <腕の根> …"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def names(d, c, hist):
    if c["alive"]:
        return {c["relation"]["predicate"]}
    h = hist.get(str((d["name"], c["slot_index"])))
    if h is None:
        return set()
    if isinstance(h, dict):
        return {p for p, n in h.items() if n >= 1}
    return set(h)


def one(args):
    root, cell, seed = args
    from extrap_reader import iter_run
    import shopworld as sw
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    world = int(fl["shop_world"])
    motif, door_ids, ever = {}, set(), set()
    c = Counter()
    ex = []
    for tr in iter_run(root, cell, seed, check_hash=False):
        t = tr["t"]
        wt = tr["world"]
        info = sw.INFO[wt.G_star.graph_id]
        motif[t] = info["shop_type"]
        door_ids.add(info["door_id"])
        pre = tr["pre"]
        if pre is None:
            continue
        hist = pre["slot_history"]
        have = {}
        for sit in [(ty, cu) for ty in ("甲", "乙") for cu in ("n", "e")]:
            want_sig = sw.SIG_E if sit[1] == "e" else sw.SIG_N
            want_door = sw.door_pred(world, sit[0], sit[1])
            ok = set()
            for d in pre["definitions"].values():
                if motif.get(d["registered_at"]) != sit[0]:
                    continue
                sig_ok = any(sw.IDS.get(x["relation"]["relation_id"]) == "sig" and want_sig in names(d, x, hist) for x in d["constituents"])
                door_ok = any(x["relation"]["relation_id"] in door_ids and want_door in names(d, x, hist) for x in d["constituents"])
                if sig_ok and door_ok:
                    ok.add(d["name"])
            have[sit] = ok
            if ok:
                ever.add(sit)
        row = tr["row"]
        if not info["held_out_is_door"] or row.get("predicted_edge") is None or row.get("hit"):
            continue
        sit = (info["shop_type"], info["shop_cue"])
        R = row.get("R_used")
        if have[sit]:
            k = "(d) 今あって、それを選んだのに外れた" if R in have[sit] else "(c) 今あるのに、別の定義を選んだ"
        elif sit in ever:
            k = "(b) 前はあったが、今は無い"
        else:
            k = "(a) 一度もできていない"
        c[(f"{sit[0]}・{sit[1]}", k)] += 1
        if len(ex) < 3:
            ex.append({"seed": seed, "trial": t, "状況": f"{sit[0]}・{sit[1]}", "分類": k, "R_used": R, "区別を持つ定義": sorted(have[sit])})
    return {"seed": seed, "c": {"|".join(k): v for k, v in c.items()}, "ex": ex}


def main():
    out = sys.argv[1]
    res = {}
    for root in sys.argv[2:]:
        jobs = [(root, os.path.basename(os.path.dirname(p)), int(os.path.basename(p)[4:7]))
                for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))) if 1 <= int(os.path.basename(p)[4:7]) <= 20]
        with Pool(int(os.environ.get("EP_WORKERS", "8"))) as pool:
            runs = pool.map(one, jobs)
        c = Counter()
        for r in runs:
            for k, v in r["c"].items():
                c[k] += v
        res[os.path.basename(root)] = {"数": dict(sorted(c.items())), "例": [e for r in runs for e in r["ex"]][:10]}
        print(os.path.basename(root), dict(c), flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
