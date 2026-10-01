"""E の判断と、候補の定義のシールの席（委任書 2026-10-02 朝の問い 2 の 4、候補①の材料）。★ 記録を読むだけ。
side の v310be の記録の cands（[R or None（新しく作る）, …, K]。K の小さい順に並ぶ。先頭が選ばれたもの）から、
  ・E が「新しく作る」（chosen が None）を選んだ試行：既存の定義の候補のうち K が最も小さいもの（いちばん近かった既存）
  ・E が「既存にまとめる」を選んだ試行：選ばれた定義
の、予測の直前の状態でのシールの席の状態（F・H・U の最もよいもの。シールの席が無ければ「無し」。既存の候補が無ければ「候補なし」）を数える。
あわせて、新しく作った試行での「いちばん近かった既存の K − 新しく作る K」の分布を、その既存のシールの席の状態ごとに出す。
使い方  python3.12 tools/birthcand.py <出力の .json> <腕の根> …   （並列は環境変数 BC_WORKERS、既定 4）"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from statistics import median

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def one(args):
    root, cell, seed = args
    import shopworld as sw
    from extrap_reader import iter_run
    from sealmem import _hist, def_seal
    c = Counter()
    gaps = defaultdict(list)
    for tr in iter_run(root, cell, seed, check_hash=False):
        be = (tr["side"].get("v310be") or [{}])[0]
        if "chosen" not in be or be.get("x") == "no_m1":
            continue
        pre = tr["pre"] or {"definitions": {}, "slot_history": {}}
        hk = set(_hist(pre["slot_history"]))
        cands = be.get("cands") or []
        if be["chosen"] is None:
            ex = [x for x in cands if x[0] is not None]
            new = [x for x in cands if x[0] is None]
            if not ex:
                c[("新しく作る", "候補なし")] += 1
                continue
            R = ex[0][0]
            dd = pre["definitions"].get(R)
            s = def_seal(dd, hk, sw.IDS) if dd is not None else "状態に無い"
            c[("新しく作る", s)] += 1
            if new:
                gaps[s].append(ex[0][-2] - new[0][-2])
        else:
            dd = pre["definitions"].get(be["chosen"])
            s = def_seal(dd, hk, sw.IDS) if dd is not None else "状態に無い"
            c[("既存にまとめる", s)] += 1
    return {"c": {"|".join(k): v for k, v in c.items()}, "gaps": dict(gaps)}


def main():
    out = sys.argv[1]
    res = {}
    for root in sys.argv[2:]:
        jobs = [(root, os.path.basename(os.path.dirname(p)), int(os.path.basename(p)[4:7]))
                for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))) if 1 <= int(os.path.basename(p)[4:7]) <= 20]
        with Pool(int(os.environ.get("BC_WORKERS", "4"))) as pool:
            runs = pool.map(one, jobs)
        c = Counter()
        g = defaultdict(list)
        for r in runs:
            for k, v in r["c"].items():
                c[k] += v
            for k, v in r["gaps"].items():
                g[k] += v
        res[os.path.basename(root)] = {"数（20 走行の和）": dict(sorted(c.items())),
                                       "新しく作った試行の K の差（いちばん近かった既存 − 新しく作る）中央値・数": {k: [round(median(v), 3), len(v)] for k, v in g.items()}}
        print(os.path.basename(root), dict(c), flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
