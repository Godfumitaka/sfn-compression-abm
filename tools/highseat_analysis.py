"""高階の席は採点されずに忘れられていたか（2026-10-01 未明の委任書）。★ 台帳・side・記録を読むだけ。模型は変えない。走らせない。
席の階の分類：席の関係の生まれたときの述語で分ける。述語は、定義の行の関係 ID と同じ ID の世界の関係の述語（状態の控えでは、墓石の行の
  述語は「⟨消去⟩」に置き換わるため）。分類は種ファイルの骨組みから：根＝motif_structure の third、T 階＝T1〜T4 の higher、
  部分木階＝A〜H の higher、一階＝A〜H の first_order。世界に ID が無ければ「不明」、骨組みの語でなければ「骨組みの外」。
席の状態：F＝生きている行、H＝墓石で slot_history に欄がある、U＝墓石で欄が無い（tools/v39.py:133-137）。席の同一性は（定義名・定義の登録試行・席番号）。
  1 階 × 状態：試行 100・200・…・1,700 の終わりの状態と走行の終わりの状態の、全定義の席。
     予測で選ばれた定義（台帳の R_used）の席：各時点を中心とする 100 試行（t−50〜t+49。走行の終わりは最後の 100 試行）の予測の直前の状態の和。
  2 採点の回数：--dump-routing の kind＝"score" の席のうち scored＝真のもの。その試行の予測の直前の状態で、同じ名前の定義の登録試行に結びつける。
  3 薄くされるまで：各試行の終わりの状態で、誕生（定義の登録試行）から最初に H になった試行まで、最初の H から最初に U になった試行まで。
  4 答えた課題：選ばれた定義の根の席の、予測の直前の状態 × 話した席の対応先（roletarget の CSV）× 当たり外れ、
     定義が生まれた試行の場面の型と今の場面の型が同じか。
使い方  python3.12 tools/highseat_analysis.py <出力の .json> <腕名>=<腕の走行根>:<roletarget の場所> …"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

CHECK_T = list(range(100, 1701, 100))


def levels(seed_path):
    d = json.load(open(seed_path, encoding="utf-8"))
    lv = {}
    for m in d["motif_structure"].values():
        lv[m["third"]] = "根"
    for name, st in d["subtrees"].items():
        if "subtrees" in st:
            lv[st["higher"]] = "T 階"
        else:
            lv[st["higher"]] = "部分木階"
            for p in st["first_order"]:
                lv[p] = "一階"
    return lv


def one(args):
    root, cell, seed, rtdir = args
    W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path[:0] = [os.path.join(W, "tools"), W]
    from extrap_reader import iter_run
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(W, fl["config"]), encoding="utf-8"))
    LV = levels(os.path.join(W, cfg["seed_file"]))
    rt = {}
    for p in glob.glob(os.path.join(rtdir, f"{cell}_seed{seed:03d}.roletarget.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["answered"] == "1":
                rt[int(r["trial"])] = r
    pred = {}
    motif = {}
    lvl = lambda rid: (LV.get(pred[rid], "骨組みの外") if rid in pred else "不明")  # noqa: E731

    def seat_states(state):
        hk = set(state["slot_history"])
        for d in state["definitions"].values():
            for c in d["constituents"]:
                st = "F" if c["alive"] else ("H" if str((d["name"], c["slot_index"])) in hk else "U")
                yield d, c, st

    snap = defaultdict(Counter)       # 時点 → (階, 状態) → 数
    used = defaultdict(Counter)       # 時点 → (階, 状態) → 数（R_used の窓）
    seat_lv = {}                      # 席 → 階
    first_st, t_H, t_U, last_seen, last_st = {}, {}, {}, {}, {}
    fu_direct = set()
    scored = Counter()
    q4 = Counter()
    windows = [(str(t), t - 50, t + 49) for t in CHECK_T]
    last_t = None
    for tr in iter_run(root, cell, seed):
        t = tr["t"]
        wt = tr["world"]
        motif[t] = wt.motif
        for r in wt.G_star.relations:
            pred.setdefault(r.relation_id, r.predicate)
        pre, post = tr["pre"], tr["post"]
        # 1 R_used の窓・4 答えた課題・2 採点（予測の直前の状態）
        R = tr["row"].get("R_used")
        if pre is not None and R and R in pre["definitions"]:
            d = pre["definitions"][R]
            hk = set(pre["slot_history"])
            sts = {c["slot_index"]: ("F" if c["alive"] else ("H" if str((R, c["slot_index"])) in hk else "U")) for c in d["constituents"]}
            for name, a, b in windows:
                if a <= t <= b:
                    for c in d["constituents"]:
                        used[name][(lvl(c["relation"]["relation_id"]), sts[c["slot_index"]])] += 1
            used["_all"][("計", "予測")] += 1
            ans = tr["answer"]
            if ans is not None:
                roots = [sts[c["slot_index"]] for c in d["constituents"] if lvl(c["relation"]["relation_id"]) == "根"]
                rs = "根の席なし" if not roots else ("+".join(sorted(roots)))
                r = rt.get(t)
                cls = r["cls"].split("：")[0] if r else "対応先の行なし"
                same = "同じ型" if motif.get(d["registered_at"]) == wt.motif else "違う型"
                q4[(rs, cls, "当たり" if ans["hit"] == "1" else "外れ", same)] += 1
        for sc in tr["routing"].get("score", []):
            if pre is None or sc["R"] not in pre["definitions"]:
                continue
            reg = pre["definitions"][sc["R"]]["registered_at"]
            for it in sc["items"]:
                if it.get("scored"):
                    scored[(sc["R"], reg, it["slot"])] += 1
        # 状態の移り（試行の終わりの状態）
        for d, c, st in seat_states(post):
            key = (d["name"], d["registered_at"], c["slot_index"])
            if key not in seat_lv:
                seat_lv[key] = lvl(c["relation"]["relation_id"])
                first_st[key] = (st, t)
            if st == "H" and key not in t_H:
                t_H[key] = t
            if st == "U" and key in t_H and key not in t_U:
                t_U[key] = t
            if st == "U" and key not in t_H and last_st.get(key) == "F":
                fu_direct.add(key)
            last_seen[key] = t
            last_st[key] = st
        if t in CHECK_T:
            for d, c, st in seat_states(post):
                snap[str(t)][(lvl(c["relation"]["relation_id"]), st)] += 1
        last_t = t
        last_post = post
    for d, c, st in seat_states(last_post):
        snap["終わり"][(lvl(c["relation"]["relation_id"]), st)] += 1
    # 走行の終わりの窓（最後の 100 試行）の R_used の席は one_end で数える（走行の長さが分かってから）
    alive_end = {(d["name"], d["registered_at"], c["slot_index"]) for d, c, _ in seat_states(last_post)}
    seats = {}
    for key, lv in seat_lv.items():
        reg = key[1]
        fs, ft = first_st[key]
        h = t_H.get(key)
        u = t_U.get(key)
        seats["|".join(map(str, key))] = {
            "lv": lv, "reg": reg, "first": fs, "first_t": ft, "tH": h, "tU": u, "fu_direct": key in fu_direct,
            "alive_end": key in alive_end, "last_seen": last_seen[key], "last_st": last_st[key], "scored": scored.get(key, 0)}
    return {"seed": seed, "cell": cell, "last_t": last_t,
            "snap": {k: {"|".join(kk): v for kk, v in c.items()} for k, c in snap.items()},
            "used": {k: {"|".join(kk): v for kk, v in c.items()} for k, c in used.items()},
            "seats": seats, "q4": {"|".join(k): v for k, v in q4.items()},
            "scored_unmatched": sum(v for k, v in scored.items() if k not in seat_lv)}


def one_end(args):
    """走行の終わりの窓（最後の 100 試行）の R_used の席。"""
    root, cell, seed, rtdir, last_t = args
    W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path[:0] = [os.path.join(W, "tools"), W]
    from extrap_reader import iter_run
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(W, fl["config"]), encoding="utf-8"))
    LV = levels(os.path.join(W, cfg["seed_file"]))
    pred = {}
    c = Counter()
    for tr in iter_run(root, cell, seed, check_hash=False):
        for r in tr["world"].G_star.relations:
            pred.setdefault(r.relation_id, r.predicate)
        t = tr["t"]
        if t < last_t - 99:
            continue
        R = tr["row"].get("R_used")
        pre = tr["pre"]
        if pre is not None and R and R in pre["definitions"]:
            d = pre["definitions"][R]
            hk = set(pre["slot_history"])
            for x in d["constituents"]:
                st = "F" if x["alive"] else ("H" if str((R, x["slot_index"])) in hk else "U")
                rid = x["relation"]["relation_id"]
                c[(LV.get(pred[rid], "骨組みの外") if rid in pred else "不明", st)] += 1
    return {"seed": seed, "end_used": {"|".join(k): v for k, v in c.items()}}


def main():
    out = sys.argv[1]
    res = {}
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        root, rtdir = rest.split(":", 1)
        jobs = []
        for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
            s = int(os.path.basename(p)[4:7])
            if 1 <= s <= 20:
                jobs.append((root, os.path.basename(os.path.dirname(p)), s, rtdir))
        with Pool(4) as pool:
            runs = pool.map(one, jobs)
            ends = pool.map(one_end, [(j[0], j[1], j[2], j[3], r["last_t"]) for j, r in zip(jobs, runs)])
        for r, e in zip(runs, ends):
            r["used"]["終わり"] = e["end_used"]
        res[name] = runs
        print(name, len(runs), sum(len(r["seats"]) for r in runs), "席", flush=True)
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("ok", out)


if __name__ == "__main__":
    main()
