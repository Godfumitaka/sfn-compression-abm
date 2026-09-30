"""委任書「答えた席と伏せた位置の関係、定義の厚さ、未経験の課題の時期（2026-09-30 夜）」の 3・4・5。★ 数えるだけ。判断しない。
  3 ぶら下がった参照：伏せた関係の ID が、提示の関係（本人の見た場面。開示は含めない）のどれかの引数に入っているか。
  4 定義の厚さ：予測で選ばれた定義（台帳の R_used）の、予測の直前の F・H・U の席の数。
    100 試行ごと（試行番号 prediction_order が 100・200・…・1,700 の試行の終わりの状態）と走行の終わり（最後の試行の終わり）の、全定義の F・H・U の席の数と定義の本数。
    席の状態：生きている行＝F、墓石で履歴の欄がある＝H、墓石で履歴の欄が無い＝U（tools/v39.py seat_state と同じ）。
  5 細かい状況で「確かめる機会がまだなかった」課題（tools/extrap_marks.py の印）の、試行・型・伏せた位置の階（伏せた関係の引数が物だけなら 1、関係を含めば 1＋子の最大の階）。
使い方  python3.12 tools/answerseat_analysis.py <出力の .json> <腕名>=<腕の走行根> …"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from multiprocessing import Pool

CHECK_T = list(range(100, 1701, 100))


def seat_counts(defn, hist_keys):
    F = H = U = 0
    for r in defn["constituents"]:
        if r.get("alive"):
            F += 1
        elif str((defn["name"], r["slot_index"])) in hist_keys:
            H += 1
        else:
            U += 1
    return F, H, U


def one(args):
    root, cell, seed = args
    sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
    from extrap_reader import iter_run
    out = {"seed": seed, "dangling": {"あり": 0, "なし": 0}, "dangling_none_trials": [], "sel": [], "snap": {}, "world_hash": None}
    last = None
    for tr in iter_run(root, cell, seed):
        t = tr["t"]
        wt = tr["world"]
        out["world_hash"] = tr["header"]["world_hash"]
        hid = wt.held_out_edge.relation_id
        vis = wt.target_graph_partial.relations
        if any(hid in r.arguments for r in vis):
            out["dangling"]["あり"] += 1
        else:
            out["dangling"]["なし"] += 1
            out["dangling_none_trials"].append(t)
        R = tr["row"].get("R_used")
        pre = tr["pre"]
        if R and pre and R in pre["definitions"]:
            out["sel"].append(seat_counts(pre["definitions"][R], set(pre["slot_history"])))
        post = tr["post"]
        if t in CHECK_T:
            keys = set(post["slot_history"])
            out["snap"][str(t)] = [seat_counts(d, keys) for d in post["definitions"].values()]
        last = (t, post)
    t, post = last
    keys = set(post["slot_history"])
    out["snap"]["終わり"] = [seat_counts(d, keys) for d in post["definitions"].values()]
    out["last_t"] = t
    return out


def dist(xs):
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]  # noqa: E731
    return {"n": len(xs), "最小": xs[0], "第1四分位": q(0.25), "中央値": q(0.5), "第3四分位": q(0.75), "最大": xs[-1]}


def level_of(rel, rels_by_id):
    kids = [a for a in rel.arguments if a in rels_by_id]
    return 1 if not kids else 1 + max(level_of(rels_by_id[k], rels_by_id) for k in kids)


def main():
    out_json = sys.argv[1]
    res = {}
    for spec in sys.argv[2:]:
        name, root = spec.split("=", 1)
        jobs = []
        for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
            jobs.append((root, os.path.basename(os.path.dirname(p)), int(os.path.basename(p)[4:7])))
        with Pool(8) as pool:
            runs = pool.map(one, jobs)
        arm = {"走行": len(runs), "ぶら下がった参照": {"あり": sum(r["dangling"]["あり"] for r in runs), "なし": sum(r["dangling"]["なし"] for r in runs)},
               "ぶら下がった参照_走行ごと": {r["seed"]: r["dangling"] for r in runs},
               "ぶら下がり無しの試行": {r["seed"]: r["dangling_none_trials"] for r in runs},
               "world_hash": {r["seed"]: r["world_hash"] for r in runs}}
        sel = [x for r in runs for x in r["sel"]]
        arm["選ばれた定義の席"] = {"予測の数": len(sel), "F": dist([x[0] for x in sel]), "H": dist([x[1] for x in sel]),
                            "U": dist([x[2] for x in sel]), "席の計": dist([sum(x) for x in sel])}
        snaps = {}
        for k in [str(t) for t in CHECK_T] + ["終わり"]:
            allc = [c for r in runs for c in r["snap"].get(k, [])]
            snaps[k] = {"定義の本数（走行の和）": len(allc), "定義の本数（走行ごと）": dist([len(r["snap"].get(k, [])) for r in runs]),
                        "F": dist([c[0] for c in allc]), "H": dist([c[1] for c in allc]), "U": dist([c[2] for c in allc])}
        arm["全定義の席"] = snaps
        # 5：印の行から
        rows = []
        for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.extrap.csv"))):
            rows += [r for r in csv.DictReader(open(p, encoding="utf-8")) if r["細_印"] == "確かめる機会がまだなかった"]
        arm["未経験_細かい"] = [{"seed": int(r["seed"]), "trial": int(r["trial"])} for r in rows]
        res[name] = arm
        print(name, arm["ぶら下がった参照"], len(rows))
    # 5 の型と階（世界を作り直す。どの腕も同じ世界：world_hash で確かめる）
    sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    from abm.seed import load_seed
    from abm.world import generate_world
    first = next(iter(res.values()))
    root0 = sys.argv[2].split("=", 1)[1]
    fl = json.load(open(os.path.join(root0, "flag.json")))
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = json.load(open(os.path.join(repo, fl["config"])))
    seedobj = load_seed(os.path.join(repo, cfg["seed_file"]))
    worlds = {}
    for name, arm in res.items():
        det = []
        for x in arm["未経験_細かい"]:
            s = x["seed"]
            if s not in worlds:
                import gzip
                p = glob.glob(os.path.join(root0, f"ledgers/cells/*/seed{s:03d}.jsonl.gz"))[0]
                with gzip.open(p, "rt") as f:
                    h = json.loads(next(f))
                worlds[s] = generate_world(h["run_seed"], h["trial_count"], ["agent"], seed=seedobj,
                                           holdout_include_second_order=bool(h.get("arm_holdout_second_order") or False))
            wt = worlds[s].trials[x["trial"]]
            rb = {r.relation_id: r for r in wt.G_star.relations}
            det.append({**x, "型": wt.motif, "伏せた位置の階": level_of(wt.held_out_edge, rb), "伏せた述語": wt.held_out_edge.predicate})
        arm["未経験_細かい"] = det
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out_json)


if __name__ == "__main__":
    main()
