"""--answer-gap の確かめ（委任書「欠けた位置にだけ答える」の 2-2・2-3）。★ 記録を読むだけ。
  旗ありの一本と旗なしの一本（同じ腕・同じ種）を読み、次を数える。
  ・話した答えの席の対応先（作り直した状態から計算し直す。tools/roletarget_recompute.py の compute）が、その試行の欠けた位置の集合 D に入るか。
  ・D が伏せた関係の ID 一つだけの試行の割合（研究者の側）。違う試行の例。
  ・最初に答え（台帳の predicted_edge と棄権の理由）が変わる試行 t0。t0 より前の台帳の行が一字一句同じか。
  ・t0 の旗ありの答えが、旗なしの走行の後づけの計算（roletarget の CSV）の「対応先が (i) の最初の候補」と同じか。
  ・t0 以降で、状態の指紋（agent_state_snapshot_hash）が最初に分かれる試行。
使い方  python3.12 tools/answergap_verify.py <旗ありの走行根> <旗なしの走行根> <旗なしの roletarget CSV> <種> <出力の .json>"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import sys
from collections import Counter

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def rows_of(root, seed):
    p = glob.glob(os.path.join(root, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz"))[0]
    with gzip.open(p, "rt", encoding="utf-8") as f:
        next(f)
        return [line for line in f]


def main():
    on_root, off_root, off_rt, seed, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    import roletarget_recompute as rr
    from answergap import gap_ids
    from extrap_reader import iter_run
    v39, v310be = rr._install()
    cell = os.path.basename(os.path.dirname(glob.glob(os.path.join(on_root, "ledgers/cells/*/seed*.done"))[0]))
    res = Counter()
    ex = {"D が伏せた関係一つでない": [], "話した答えの対応先が D に無い": []}
    argmap = {}
    reasons = Counter()
    for tr in iter_run(on_root, cell, seed):
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
        t = tr["t"]
        scene = wt.target_graph_partial
        D = gap_ids(scene)
        res["試行"] += 1
        if D == frozenset({wt.held_out_edge.relation_id}):
            res["D＝伏せた関係の ID 一つ"] += 1
        else:
            res["D がそれ以外"] += 1
            key = "空" if not D else ("伏せた関係を含む・ほかもある" if wt.held_out_edge.relation_id in D else "伏せた関係を含まない")
            res[f"D がそれ以外：{key}"] += 1
            if len(ex["D が伏せた関係一つでない"]) < 5:
                ex["D が伏せた関係一つでない"].append({"trial": t, "D": sorted(D), "held": wt.held_out_edge.relation_id, "区分": key})
        row = tr["row"]
        pe = row.get("predicted_edge")
        if row.get("abstain_reason"):
            reasons[row["abstain_reason"]] += 1
        ans = tr["answer"]
        if ans is None:
            continue
        res["答えた"] += 1
        seats, _bad = rr.compute(v39, v310be, tr["pre"], ans["R"], scene, argmap)
        cid = seats.get(int(ans["slot"]), {}).get("cid")
        if cid in D:
            res["話した答えの対応先が D に入る"] += 1
        else:
            res["話した答えの対応先が D に無い"] += 1
            if len(ex["話した答えの対応先が D に無い"]) < 5:
                ex["話した答えの対応先が D に無い"].append({"trial": t, "R": ans["R"], "slot": ans["slot"], "cid": cid, "D": sorted(D),
                                                     "edge": pe})
    # 旗なしとの比べ
    on_rows, off_rows = rows_of(on_root, seed), rows_of(off_root, seed)
    t0 = None
    for i, (a, b) in enumerate(zip(on_rows, off_rows)):
        ra, rb = json.loads(a), json.loads(b)
        if (ra.get("predicted_edge"), ra.get("abstain_reason")) != (rb.get("predicted_edge"), rb.get("abstain_reason")):
            t0 = i
            break
    same_before = all(on_rows[i] == off_rows[i] for i in range(t0 if t0 is not None else len(on_rows)))
    cmp = {"最初に答えが変わる試行": t0, "それより前の台帳の行が一字一句同じ": same_before}
    if t0 is not None:
        ra, rb = json.loads(on_rows[t0]), json.loads(off_rows[t0])
        cmp["t0 の旗あり"] = {"predicted_edge": ra.get("predicted_edge"), "abstain_reason": ra.get("abstain_reason"), "R_used": ra.get("R_used")}
        cmp["t0 の旗なし"] = {"predicted_edge": rb.get("predicted_edge"), "abstain_reason": rb.get("abstain_reason"), "R_used": rb.get("R_used")}
        rt = next((r for r in csv.DictReader(open(off_rt, encoding="utf-8")) if int(r["trial"]) == t0), None)
        first_i = None
        if rt is not None:
            first_i = next((c for c in json.loads(rt["cands"]) if c["cls"] == "(i) 伏せた関係"), None)
        cmp["旗なしの後づけの計算の (i) の最初の候補"] = first_i
        pe = ra.get("predicted_edge") or {}
        cmp["t0 の旗ありの答えが (i) の最初の候補と同じ"] = (first_i is not None and pe.get("relation_id", "").startswith("filling__")
                                                  and int(pe["relation_id"].rsplit("__", 2)[1]) == first_i["slot"]
                                                  and pe.get("predicate") == first_i["pred"])
        cmp["t0 の台帳の行で違う欄"] = sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))
        ha = [json.loads(x)["agent_state_snapshot_hash"] for x in on_rows]
        hb = [json.loads(x)["agent_state_snapshot_hash"] for x in off_rows]
        t1 = next((i for i in range(len(ha)) if ha[i] != hb[i]), None)
        cmp["状態の指紋が最初に分かれる試行"] = t1
        cmp["答えが違う試行の数"] = sum(1 for a, b in zip(on_rows, off_rows)
                                if (json.loads(a).get("predicted_edge"), json.loads(a).get("abstain_reason"))
                                != (json.loads(b).get("predicted_edge"), json.loads(b).get("abstain_reason")))
        cmp["状態の指紋が違う試行の数"] = sum(1 for a, b in zip(ha, hb) if a != b)
    outd = {"数": dict(res), "例": ex, "旗なしとの比べ": cmp, "棄権の理由（旗あり）": dict(reasons)}
    json.dump(outd, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(outd, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
