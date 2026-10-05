"""誤りの印と記憶の量（委任書「誤りの印の確かめと、シールを守ると記憶が少なくなる理由」2026-10-02 朝）。★ 記録を読むだけ。模型は変えない。走らせない。
一本の走行を一度読み、二つの表を書く。
(1) <出力>/<腕>/seed<種>.answers.csv：答えた試行ごとに、本人に見える量（予測の時点）。
  - 支持の割合：答えの記録（answers.csv）の support_ratio。
  - U の席の割合：答えの記録の def_U ÷ (def_F＋def_H＋def_U)。
  - 選ばれた定義（R_used）のシールの席（関係 ID が tools/shopworld.py の IDS で "sig" の行）の状態。二つの決め方（仮の決定）：
    ・照合で決める：予測の直前の状態から本番と同じ照合（tools/roletarget_recompute.py compute と同じ計算）で、F の席は照合の直接の対応、
      H の席は対応先 cid（role_target）を求め、今の場面のシールの関係（INFO の sig_id）に写ったら「F で合った／H で合った」、
      写らなければ「F・H で合わなかった」（None なら対応先なし、別の関係なら「別の関係に写った」）。
    ・名前で決める：F は行の述語が、H は履歴の名（回数 1 以上）に、今の場面のシールの述語があれば「合った」、無ければ「名前が違って合わなかった」。
    ・どちらも U は「U」、シールの席が無ければ「シールの席なし」。シールの席が二つ以上なら、合った F → 合った H → 合わなかった F・H → U の順で
      一つを代表にし、席の数を残す（仮の決定）。
  - 確かめ：答えた席の対応先（cid）を、前の照合の再計算（~/v310cprod/roletarget/<腕>/…roletarget.csv）と比べる（引数 rt_root があるとき）。
(2) <出力>/<腕>/seed<種>.mem.csv：試行ごとの、試行の終わりの状態の記憶の内訳（tools/v39.py total_bits の項に分ける）。
  - G：全体の表（global_table_bits）、Idef：定義の数の符号 I(定義の数)、S：定義の骨組み（structure_bits の和）、
    seat2：席ごとの 2 ビット（2 × 席の数）、Hc：H の席の中身（hcost）、Fc：F の席の中身（hcost＋fixed_spec_bits）。
  - 合計が side の C_end と一致することを確かめる（一致しない試行の数を残す）。
  - 定義をシールの席の状態（F・H・U の最もよいもの、シールの席が無ければ「無し」）で分けた数（試行の終わり）、
    同化された定義のシールの席の状態（予測の直前の状態。その試行に生まれた定義なら「新」）、誕生した定義のシールの席の状態（試行の終わり）。
  - 定義の数、席の状態ごとの数（F・H・U）、その試行の誕生（side の birth）・同化（side の assim）・手放し（前の試行の終わりにあって、
    この試行の終わりに無い（定義名・登録試行）の数）、E の判断（side の v310be：x が no_m1 なら無し、chosen が無ければ「新しく作る」、
    あれば「既存にまとめる」）、R_B・R_E（side の v310be）。
使い方  python3.12 tools/sealmem.py <出力の場所> <腕の走行根> [--rt <roletarget の根>] [--no-seal]   （並列は環境変数 SM_WORKERS、既定 4）"""
from __future__ import annotations

import ast
import csv
import glob
import json
import os
import sys
from multiprocessing import Pool
from types import SimpleNamespace as NS

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]

RANK = {"F で合った": 0, "H で合った": 1, "F で合わなかった（対応先なし）": 2, "H で合わなかった（対応先なし）": 2,
        "F で別の関係に写った": 2, "H で別の関係に写った": 2, "F で名前が違って合わなかった": 2, "H で名前が違って合わなかった": 2, "U": 3}


def _hist(sh):
    out = {}
    for k, v in sh.items():
        key = ast.literal_eval(k)
        out[key] = dict(v) if isinstance(v, dict) else frozenset(v)
    return out


def mem_parts(v39, state):
    """試行の終わりの状態（dict）の記憶のビットの内訳。"""
    ph = NS(counts=state["p_hat"]["counts"], total=state["p_hat"]["total"])
    L = v39.code_lengths(ph)
    sh = _hist(state["slot_history"])
    G = v39.global_table_bits(ph)
    defs = state["definitions"]
    Idef = v39.I(len(defs))
    S = seat2 = Hc = Fc = 0
    n = {"F": 0, "H": 0, "U": 0}
    for dd in defs.values():
        rows = [NS(slot_index=c["slot_index"], registered_at=c["registered_at"], alive=bool(c["alive"]),
                   relation=NS(relation_id=c["relation"]["relation_id"], predicate=c["relation"]["predicate"],
                               arguments=tuple(c["relation"]["arguments"])))
                for c in sorted(dd["constituents"], key=lambda c: c["slot_index"])]
        d = NS(name=dd["name"], registered_at=dd["registered_at"], constituents=tuple(rows))
        S += v39.structure_bits(d)
        for row in rows:
            st = v39.seat_state(d, row, sh)
            n[st] += 1
            seat2 += 2
            c = v39.seat_content_bits(d, row, st, sh, L)
            if st == "H":
                Hc += c
            elif st == "F":
                Fc += c
    return {"G": G, "Idef": Idef, "S": S, "seat2": seat2, "Hc": Hc, "Fc": Fc, "total": G + Idef + S + seat2 + Hc + Fc,
            "defs": len(defs), "nF": n["F"], "nH": n["H"], "nU": n["U"]}


def def_seal(dd, hkeys, ids):
    """定義のシールの席の状態（F・H・U の最もよいもの。シールの席が無ければ「無し」）。"""
    sts = []
    for c in dd["constituents"]:
        if ids.get(c["relation"]["relation_id"]) == "sig":
            sts.append("F" if c["alive"] else "H" if (dd["name"], c["slot_index"]) in hkeys else "U")
    return min(sts, key="FHU".index) if sts else "無し"


def compute2(v39, v310be, pre, R, scene, argmap):
    """tools/roletarget_recompute.py compute と同じ計算に、照合の直接の対応（行の関係 ID → 場面の関係 ID）を足したもの。"""
    from abm.filling import _mapped_arguments
    import roletarget_recompute as rr
    d, bad = rr._restore_def(pre["definitions"][R], argmap)
    sh = rr._restore_hist(pre["slot_history"], R)
    _g, al = v39.map_v39(d, sh, scene)
    seats, direct = {}, {}
    for row in d.constituents:
        cid, why = v310be.role_target(d, row, al, scene)
        pos = _mapped_arguments(row.relation, al.entity_mapping, al.relation_mapping)
        seats[row.slot_index] = {"cid": cid, "cid_why": why, "pos": list(pos) if pos is not None else None, "st": v39.seat_state(d, row, sh)}
        direct[row.slot_index] = al.relation_mapping.get(row.relation.relation_id)
    return seats, bad, direct


def seal_class(dd, seats, hist, sig_id, sig_pred, ids, direct):
    """選ばれた定義のシールの席の分類（照合で・名前で）。返り値：(照合, 名前, シールの席の数)。
    照合で（2026-10-02 朝の直し）：F の席（生きている行）は照合の直接の対応（relation_mapping）で、H の席は対応先 cid（role_target。
    親の行の対応先の同じ位置の子）で、今の場面のシールの関係に写ったかを見る。生きている行は照合で直接写り、role_target は親（link）が
    対応しないと None になるため。"""
    by_map, by_name = [], []
    for c in dd["constituents"]:
        if ids.get(c["relation"]["relation_id"]) != "sig":
            continue
        s = seats.get(c["slot_index"], {})
        st = s.get("st")
        if st == "U":
            by_map.append("U")
            by_name.append("U")
            continue
        cid = direct.get(c["slot_index"]) if st == "F" else s.get("cid")
        by_map.append(f"{st} で合った" if cid == sig_id else f"{st} で合わなかった（対応先なし）" if cid is None else f"{st} で別の関係に写った")
        if st == "F":
            ok = c["relation"]["predicate"] == sig_pred
        else:
            h = hist.get(str((dd["name"], c["slot_index"])))
            names = {p for p, k in h.items() if k >= 1} if isinstance(h, dict) else set(h or ())
            ok = sig_pred in names
        by_name.append(f"{st} で合った" if ok else f"{st} で名前が違って合わなかった")
    if not by_map:
        return "シールの席なし", "シールの席なし", 0
    return min(by_map, key=RANK.get), min(by_name, key=RANK.get), len(by_map)


def one(args):
    out_dir, root, cell, seed, rt_root, do_seal = args
    import shopworld as sw
    import v39
    from extrap_reader import iter_run
    import roletarget_recompute as rr
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    world = int(fl["shop_world"])
    if do_seal:
        v39m, v310be = rr._install()
        if fl.get("strict_pc"):
            import strictpc
            strictpc.install()
    # 記憶の内訳に要る CFG（tools/v39.py:986 と同じ値：T＝試行の数、D＝種の辞書の大きさ、dict_index＝辞書の順）
    from abm.seed import load_seed
    cfg = json.load(open(os.path.join(W, fl["config"]), encoding="utf-8"))
    v39.CFG["T"] = int(cfg["trial_count"])
    dictionary = list(load_seed(os.path.join(W, cfg.get("seed_file", "seeds/U-011_seed_v3a2.json"))).data["marginal"].keys())
    v39.CFG["D"] = len(dictionary)
    v39.CFG["dict_index"] = {p: i for i, p in enumerate(dictionary)}
    rtc = {}
    if rt_root:
        p = os.path.join(rt_root, f"{cell}_seed{seed:03d}.roletarget.csv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if r["answered"] == "1":
                    rtc[int(r["trial"])] = r["cid"] or None
    argmap = {}
    ans_rows, mem_rows = [], []
    st = {"trials": 0, "answered": 0, "C_end_mismatch": 0, "rt_checked": 0, "rt_mismatch": 0, "args_unrestored": 0}
    prev = None
    for tr in iter_run(root, cell, seed, check_hash=False):
        t = tr["t"]
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
        st["trials"] += 1
        info = sw.INFO[wt.G_star.graph_id]
        ans = tr["answer"]
        if do_seal and ans is not None:
            st["answered"] += 1
            R = ans["R"]
            pre = tr["pre"]
            seats, bad, direct = compute2(v39m, v310be, pre, R, wt.target_graph_partial, argmap)
            st["args_unrestored"] += len(bad)
            sig_pred = next(r.predicate for r in wt.G_star.relations if r.relation_id == info["sig_id"])
            cm, cn, ns = seal_class(pre["definitions"][R], seats, pre["slot_history"], info["sig_id"], sig_pred, sw.IDS, direct)
            slot = int(ans["slot"]) if ans["slot"] not in ("", None) else None
            cid = seats.get(slot, {}).get("cid")
            if t in rtc:
                st["rt_checked"] += 1
                st["rt_mismatch"] += int(rtc[t] != cid)
            F, H, U = int(ans["def_F"]), int(ans["def_H"]), int(ans["def_U"])
            ans_rows.append({"seed": seed, "trial": t, "door": int(info["held_out_is_door"]), "shop_type": info["shop_type"],
                             "shop_cue": info["shop_cue"], "hit": int(ans["hit"]), "support_ratio": float(ans["support_ratio"]),
                             "def_F": F, "def_H": H, "def_U": U, "u_ratio": U / (F + H + U) if F + H + U else 0.0,
                             "seal_map": cm, "seal_name": cn, "seal_seats": ns, "R": R, "slot": slot, "cid": cid})
        if do_seal and fl.get("strict_pc"):
            # ★ roletarget_recompute と同じく、この試行の計算のあとで、この試行の提示（と開示）を引数の種類の控えに足す
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        post = tr["post"]
        mp = mem_parts(v39, post)
        side = tr["side"]
        be = (side.get("v310be") or [{}])[0]
        if be.get("C_end") is not None and be["C_end"] != mp["total"]:
            st["C_end_mismatch"] += 1
        cur = {(d["name"], d["registered_at"]) for d in post["definitions"].values()}
        # 定義をシールの席の状態で分けた数（試行の終わり）と、同化・誕生した定義のシールの席の状態（同化は予測の直前の状態、誕生は試行の終わり）
        hk_post = set(_hist(post["slot_history"]))
        ds = {"F": 0, "H": 0, "U": 0, "無し": 0}
        for dd in post["definitions"].values():
            ds[def_seal(dd, hk_post, sw.IDS)] += 1
        pre = tr["pre"]
        hk_pre = set(_hist(pre["slot_history"])) if pre is not None else set()
        asg = {"F": 0, "H": 0, "U": 0, "無し": 0, "新": 0}
        for a in side.get("assim", []):
            dd = (pre or {}).get("definitions", {}).get(a["R"])
            asg[def_seal(dd, hk_pre, sw.IDS) if dd is not None else "新"] += 1
        bsg = {"F": 0, "H": 0, "U": 0, "無し": 0, "無い": 0}
        for b in side.get("birth", []):
            dd = post["definitions"].get(b["R"])
            bsg[def_seal(dd, hk_post, sw.IDS) if dd is not None else "無い"] += 1
        E = "無し" if be.get("x") == "no_m1" or "chosen" not in be else ("新しく作る" if be["chosen"] is None else "既存にまとめる")
        mem_rows.append({"seed": seed, "trial": t, **mp, "C_end": be.get("C_end"), "births": len(side.get("birth", [])),
                         "assims": len(side.get("assim", [])), "released": len(prev - cur) if prev is not None else 0,
                         "E": E, "R_B": be.get("R_B", 0.0), "R_E": be.get("R_E", 0.0), "world": world,
                         **{f"defs_seal{k}": v for k, v in ds.items()}, **{f"assim_seal{k}": v for k, v in asg.items()},
                         **{f"birth_seal{k}": v for k, v in bsg.items()}})
        prev = cur
    arm = os.path.basename(root.rstrip("/"))
    os.makedirs(os.path.join(out_dir, arm), exist_ok=True)
    for name, rows in (("answers", ans_rows), ("mem", mem_rows)):
        if not rows:
            continue
        with open(os.path.join(out_dir, arm, f"seed{seed:03d}.{name}.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return {"arm": arm, "seed": seed, **st}


def main():
    out_dir, root = sys.argv[1], sys.argv[2]
    rt_root = sys.argv[sys.argv.index("--rt") + 1] if "--rt" in sys.argv else None
    do_seal = "--no-seal" not in sys.argv
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        s = int(os.path.basename(p)[4:7])
        if 1 <= s <= 20:
            jobs.append((out_dir, root, os.path.basename(os.path.dirname(p)), s, rt_root, do_seal))
    with Pool(min(int(os.environ.get("SM_WORKERS", "4")), len(jobs))) as pool:
        res = pool.map(one, jobs)
    arm = os.path.basename(root.rstrip("/"))
    json.dump(res, open(os.path.join(out_dir, arm, "checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(arm, json.dumps({k: sum(r[k] for r in res) for k in res[0] if k not in ("arm", "seed")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
