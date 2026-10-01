"""答えた席の対応先を、作り直した状態から計算し直す（2026-09-30 夜の返事「1・2 は (a) で一度試す」）。★ 記録を読むだけ。模型は変えない。走らせない。
計算の道（予測のときと同じ、tools/v39.py:542-563・:629 と tools/v310be.py:78-112）：
  予測の直前の状態（台帳から作り直し、sha256 を確かめたもの）から、台帳の R_used の定義を組み立て、
  v39.map_v39(定義, slot_history, 提示の場面) で照合し（本番と同じ差し替え：fixorder2・fix2・v39 の候補・ustruct の照合）、
  定義の全席について v310be.role_target(定義, 行, 照合, 場面) と、写した位置（abm.filling._mapped_arguments）を求める。
状態の控えの戻し方：台帳の状態の控えは組（tuple）を整列して書く（abm/loop.py:662-663）。そのため
  ・定義の行は slot_index の順に並べる。
  ・関係の引数の並びは、世界（作り直した全試行の完全な場面）の同じ関係 ID の引数から戻す（引数の集まりが同じことを確かめる。見つからなければ「戻せない」として数える）。
  ・slot_history の値は、控えが dict なら回数の表、list なら集合に戻す。
確かめ①：開示のある試行の routing の kind＝"score" の全席（cid・cid_why・pos）と一致すること。
確かめ②：同じ試行を二回計算して一致すること。計算の前後で、予測の直前の状態の sha256 が変わらず、台帳の一つ前の行の指紋と同じこと。
使い方  python3.12 tools/roletarget_recompute.py <腕の走行根> <出力の場所> [種 …]（既定 1〜20）"""
from __future__ import annotations

import ast
import csv
import glob
import hashlib
import json
import os
import sys
from multiprocessing import Pool

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def _install():
    """tools/v3_run.py worker と同じ順で、照合にかかわる差し替えだけを入れる（書き出しはしない）。"""
    import io
    import fixorder2
    import fix2
    import v39
    import v310be
    import ustruct
    fixorder2.install()                    # tools/v3_run.py:386
    fix2.install(full=True)                # :392
    v39._install_candidates()              # v39.install の中（:431）
    ustruct.install_matching()             # ustruct.install（:443）の照合の部分
    return v39, v310be


def _restore_def(dd, argmap):
    from abm.definition import Constituent, FrozenPrice, NamedDefinition
    from abm.domains import Relation
    rows = []
    bad = []
    for c in sorted(dd["constituents"], key=lambda c: c["slot_index"]):
        r = c["relation"]
        args = argmap.get(r["relation_id"])
        if args is None or sorted(args) != sorted(r["arguments"]):
            bad.append(r["relation_id"])
            args = tuple(r["arguments"])
        rel = Relation(relation_id=r["relation_id"], predicate=r["predicate"], arguments=tuple(args),
                       attributes=r.get("attributes") or {})
        fp = c.get("frozen_price")
        fp = FrozenPrice(**fp) if isinstance(fp, dict) else None
        rows.append(Constituent(slot_index=c["slot_index"], registered_at=c["registered_at"], relation=rel,
                                frozen_price=fp, alive=bool(c["alive"])))
    d = NamedDefinition(name=dd["name"], constituents=tuple(rows), m_alloc=dd["m_alloc"], registered_at=dd["registered_at"],
                        assimilation_count=dd.get("assimilation_count", 1))
    return d, bad


def _restore_hist(sh, R):
    out = {}
    for k, v in sh.items():
        key = ast.literal_eval(k)
        if key[0] != R:
            continue
        out[key] = dict(v) if isinstance(v, dict) else frozenset(v)
    return out


def compute(v39, v310be, pre, R, scene, argmap):
    from abm.filling import _mapped_arguments
    d, bad = _restore_def(pre["definitions"][R], argmap)
    sh = _restore_hist(pre["slot_history"], R)
    _g, al = v39.map_v39(d, sh, scene)
    seats = {}
    for row in d.constituents:
        cid, why = v310be.role_target(d, row, al, scene)
        pos = _mapped_arguments(row.relation, al.entity_mapping, al.relation_mapping)
        seats[row.slot_index] = {"cid": cid, "cid_why": why, "pos": list(pos) if pos is not None else None,
                                 "st": v39.seat_state(d, row, sh)}
    return seats, bad


def one(args):
    root, cell, seed, out_dir = args
    from abm.loop import _json_bytes
    from extrap_reader import iter_run
    v39, v310be = _install()
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    if fl.get("strict_pc"):
        # ★ --strict-pc の走行は、同じ照合の直し（tools/strictpc.py）を入れて計算し直す
        import strictpc
        strictpc.install()
    strict = bool(fl.get("strict_pc"))
    rows = []
    st = dict(trials=0, R_used=0, check1_seats=0, check1_mismatch=0, check2_mismatch=0, hash_mismatch=0, args_unrestored=0,
              score_R_differs=0, answer_R_differs=0, spoken_first_differs=0)
    examples = []
    argmap = {}
    prev_hash = None
    for tr in iter_run(root, cell, seed):
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
        row = tr["row"]
        t = tr["t"]
        st["trials"] += 1
        R = row.get("R_used")
        pre = tr["pre"]
        if R and pre is not None:
            st["R_used"] += 1
            h0 = hashlib.sha256(_json_bytes(pre)).hexdigest()
            scene = wt.target_graph_partial
            s1, bad = compute(v39, v310be, pre, R, scene, argmap)
            s2, _ = compute(v39, v310be, pre, R, scene, argmap)
            h1 = hashlib.sha256(_json_bytes(pre)).hexdigest()
            if s1 != s2:
                st["check2_mismatch"] += 1
                examples.append({"種類": "二回の計算が違う", "trial": t, "R": R})
            if h0 != h1 or h0 != prev_hash:
                st["hash_mismatch"] += 1
                examples.append({"種類": "状態の指紋", "trial": t, "前": h0, "後": h1, "台帳の一つ前": prev_hash})
            st["args_unrestored"] += len(bad)
            for sc in tr["routing"].get("score", []):
                if sc["R"] != R:
                    st["score_R_differs"] += 1
                    continue
                for it in sc["items"]:
                    st["check1_seats"] += 1
                    mine = s1.get(it["slot"], {})
                    if (mine.get("cid"), mine.get("cid_why"), mine.get("pos")) != (it.get("cid"), it.get("cid_why"), it.get("pos")):
                        st["check1_mismatch"] += 1
                        if len(examples) < 50:
                            examples.append({"種類": "記録と違う", "trial": t, "R": R, "slot": it["slot"],
                                             "記録": [it.get("cid"), it.get("cid_why"), it.get("pos")],
                                             "計算": [mine.get("cid"), mine.get("cid_why"), mine.get("pos")]})
            held = wt.held_out_edge
            vis = {r.relation_id for r in scene.relations}
            cls = lambda cid, why: ("(i) 伏せた関係" if cid == held.relation_id else "(ii) 見えている関係" if cid in vis  # noqa: E731
                                    else f"(iii) 対応先なし：{why}" if cid is None else "その他の ID")
            ans = tr["answer"]
            cands = row.get("predictions_all_slots") or []
            cinfo = []
            for k, c in enumerate(cands):
                rid = c["relation_id"]
                slot = int(rid.rsplit("__", 2)[1]) if rid.startswith("filling__") else None
                m = s1.get(slot, {})
                cinfo.append({"k": k, "slot": slot, "pred": c["predicate"], "cid": m.get("cid"), "cls": cls(m.get("cid"), m.get("cid_why")),
                              "correct": int(c["predicate"] == held.predicate and list(c["arguments"]) == list(held.arguments))})
            rec = {"seed": seed, "trial": t, "R_used": R, "answered": int(ans is not None), "disclosed": int(tr["disclosed"])}
            if ans is not None:
                if ans["R"] != R:
                    st["answer_R_differs"] += 1
                slot = int(ans["slot"]) if ans["slot"] not in ("", None) else None
                m = s1.get(slot, {})
                rec.update(source=ans["source"], slot=slot, seat_state=ans["seat_state"], hit=int(ans["hit"]),
                           cid=m.get("cid"), cid_why=m.get("cid_why"), cls=cls(m.get("cid"), m.get("cid_why")))
                if ans["source"].endswith("_fill") and cands and cinfo[0]["slot"] != slot:
                    st["spoken_first_differs"] += 1
            hid = [c for c in cinfo if c["cls"] == "(i) 伏せた関係"]
            rec.update(n_cands=len(cands), hid_cand=int(bool(hid)), hid_first_k=(hid[0]["k"] if hid else ""),
                       hid_correct=(hid[0]["correct"] if hid else ""), cands=json.dumps(cinfo, ensure_ascii=False))
            rows.append(rec)
        prev_hash = row["agent_state_snapshot_hash"]
        if strict:
            # ★ --strict-pc の定義の行の引数の種類の控え：走行と同じく、この試行の計算のあとで、この試行の提示（と開示）を控えに足す
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
    out = os.path.join(out_dir, f"{cell}_seed{seed:03d}.roletarget.csv")
    keys = ["seed", "trial", "R_used", "answered", "disclosed", "source", "slot", "seat_state", "hit", "cid", "cid_why", "cls",
            "n_cands", "hid_cand", "hid_first_k", "hid_correct", "cands"]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    return {"seed": seed, "cell": cell, **st, "examples": examples}


def main():
    root, out_dir = sys.argv[1], sys.argv[2]
    seeds = [int(x) for x in sys.argv[3:]] or list(range(1, 21))
    os.makedirs(out_dir, exist_ok=True)
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        s = int(os.path.basename(p)[4:7])
        if s in seeds:
            jobs.append((root, os.path.basename(os.path.dirname(p)), s, out_dir))
    with Pool(min(8, len(jobs))) as pool:
        res = pool.map(one, jobs)
    json.dump(res, open(os.path.join(out_dir, "checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = {k: sum(r[k] for r in res) for k in res[0] if k not in ("seed", "cell", "examples")}
    print(json.dumps(tot, ensure_ascii=False))


if __name__ == "__main__":
    main()
