"""証拠の届け先の記録（2026-09-30 夕方、委任書「外挿の印」の 1 の案 (1)、アストラさんの決定）：旗 --dump-routing。
★ 記録だけ。模型は変えない（台帳・side は旗の有無で一字一句同じ。書くのは別のファイル side/<セル>/seed<種>.routing.jsonl だけ）。
--v39 --v310-be --hist-role と一緒に使う。ほかの差し替えのすべてのあとに入れる（一番外で包む）。

書くもの（一行一件、JSON）
1 kind＝"m1"：m1（誕生・同化）で、登録した定義の席の履歴に足した観察。B（変換の段）の前の値。
  ・trial・R・was_extension（同化なら真）・base_written_at。
  ・席ごと：slot・高階か・登録の前の席の状態（F／H／U／新しい席）・前の履歴・後の履歴・足した名と回数（後 − 前）。
  ・出どころ（記録用に、m1 の中と同じ照合をもう一度計算したもの）。
    - 席の関係の写し先（場面の関係の ID）。
    - 親ごとに：親の行・親の写し先（場面の関係の ID）・同じ位置の子（場面の関係の ID と述語、見えていれば）。
    - 高階の席の、写した引数の位置に一致する場面の関係（今の決まりで高階の席の観察に使うもの）。
  ・「足した名」が出どころの名に含まれるか（recompute_consistent）。含まれなければ、その席を数える。
2 kind＝"score"：B の採点（開示を受けた試行、使った定義の席）。
  ・trial・R・開示された関係（ID・述語・引数）。
  ・席ごと：slot・状態・世代・三答え・写した位置・対応先（--score-role の role_target）とその理由・採点したか・しなかった理由・書換ビット。
    しなかった理由：答えの控えなし（写しが決まらない／U の席）・席の世代や状態が変わった・対応先なし（理由つき）・対応先が開示と違う。
記録はこの台本の外（研究者の側）のもの。エージェントの状態・判断には何も返さない。
"""
from __future__ import annotations

import json

STATS: dict = {}
_FO: list = []


def _counts(h):
    import v39
    return dict(v39.hist_counts(h))


def _write(rec):
    if _FO:
        _FO[0].write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def _sources(d, pre_hist, target):
    """m1 の中の照合（abm/abstraction.py の definition_alignment：定義のグラフ（v3.9 の表し方、登録の前の履歴）→ 場面）をもう一度計算する。"""
    import abm.sme as sme
    import v39
    from abm.filling import _is_higher, _mapped_arguments
    g = v39.v39_graph(d, pre_hist)
    try:
        al = sme.map_graphs(g, target).alignment
    finally:
        v39.unregister(g)
    t_by_id = {r.relation_id: r for r in target.relations}
    rel_ids = {row.relation.relation_id for row in d.constituents}
    out = {}
    for row in d.constituents:
        sid = row.relation.relation_id
        parents = []
        for p in d.constituents:
            for k, a in enumerate(p.relation.arguments):
                if a == sid:
                    Q = t_by_id.get(al.relation_mapping.get(p.relation.relation_id))
                    child = None
                    if Q is not None and k < len(Q.arguments):
                        c = t_by_id.get(Q.arguments[k])
                        child = [Q.arguments[k], c.predicate if c is not None else None]
                    parents.append({"parent_slot": p.slot_index, "pos": k,
                                    "parent_mapped_to": Q.relation_id if Q is not None else None,
                                    "parent_mapped_pred": Q.predicate if Q is not None else None, "child": child})
        pos = _mapped_arguments(row.relation, al.entity_mapping, al.relation_mapping)
        pos_rel = [[r.relation_id, r.predicate] for r in target.relations if pos is not None and r.arguments == pos]
        m = al.relation_mapping.get(sid)
        out[row.slot_index] = {"higher": _is_higher(row.relation, rel_ids), "mapped_to": m,
                               "mapped_visible": m in t_by_id, "parents": parents,
                               "position": list(pos) if pos is not None else None, "position_relations": pos_rel}
    return out


def install(path: str) -> None:
    import abm.loop as loop
    import v39
    STATS.clear()
    STATS.update(m1_records=0, seats=0, seats_added=0, recompute_inconsistent=0, score_records=0, score_items=0)
    _FO.clear()
    _FO.append(open(path, "w", encoding="utf-8"))

    # 1 m1：一番外で包む（v310be の E・v39・--hist-role の包み・tools/v3_run.py の包みを含めた実際の鎖の前後）
    inner_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        pre_defs = dict(state.definitions)
        pre_hist = state.slot_history
        out, reg = inner_m1(state, base, target, alignment, trial, **kw)
        if reg is None:
            return out, reg
        R = reg["R"]
        d = out.definitions.get(R)
        if d is None:
            return out, reg
        src = _sources(d, pre_hist, target)
        d0 = pre_defs.get(R)
        rows0 = {r.slot_index: r for r in d0.constituents} if d0 is not None else {}
        seats = []
        for row in sorted(d.constituents, key=lambda r: r.slot_index):
            key = (R, row.slot_index)
            before = _counts(pre_hist.get(key))
            after = _counts(out.slot_history.get(key))
            added = {p: after.get(p, 0) - before.get(p, 0) for p in after if after.get(p, 0) != before.get(p, 0)}
            st0 = (v39.seat_state(d0, rows0[row.slot_index], pre_hist) if row.slot_index in rows0 else "新")
            s = src[row.slot_index]
            names = {pp["child"][1] for pp in s["parents"] if pp["child"] and pp["child"][1]} | {x[1] for x in s["position_relations"]}
            cons = all(p in names for p in added)
            STATS["seats"] += 1
            STATS["seats_added"] += bool(added)
            STATS["recompute_inconsistent"] += not cons
            seats.append({"slot": row.slot_index, "state_before": st0, "hist_before": before, "hist_after": after,
                          "added": added, "recompute_consistent": cons, **s})
        STATS["m1_records"] += 1
        _write({"kind": "m1", "trial": trial, "R": R, "was_extension": bool(reg.get("was_extension")),
                "base_written_at": kw.get("base_written_at"), "seats": seats})
        return out, reg

    loop.m1 = m1

    # 2 採点：v39 の update_accounting が呼ぶ score_answers を包む（呼ぶ側はモジュールの名前で引く）
    real_score = v39.score_answers

    def score_answers(seats_in, ans, received, t):
        out, scored = real_score(seats_in, ans, received, t)
        done = {x[0]: x for x in scored}
        items = []
        for it in ans["items"]:
            key = (ans["R"], it["slot"])
            rec = seats_in.get(key)
            e = {"slot": it["slot"], "st": it["st"], "gen": it.get("gen"), "pos": it.get("pos"), "ans": it.get("ans"),
                 "cid": it.get("cid"), "cid_why": it.get("cid_why"), "higher": it.get("higher")}
            if it["slot"] in done:
                x = done[it["slot"]]
                e.update(scored=True, rF=x[2], rH=x[3], rU=x[4])
            else:
                if "ans" not in it:
                    why = "答えの控えなし"
                elif rec is None or rec.gen != it["gen"] or rec.state != it["st"]:
                    why = "席の世代・状態が変わった"
                elif "cid" in it and it.get("cid") is None:
                    why = f"対応先なし：{it.get('cid_why')}"
                elif "cid" in it and it.get("cid") != received.relation_id:
                    why = "対応先が開示と違う"
                elif "cid" not in it and tuple(it.get("pos") or ()) != tuple(received.arguments):
                    why = "写した位置が開示と違う"
                else:
                    why = "その他"
                e.update(scored=False, why=why)
            items.append(e)
        STATS["score_records"] += 1
        STATS["score_items"] += len(items)
        _write({"kind": "score", "trial": t, "R": ans["R"],
                "received": [received.relation_id, received.predicate, list(received.arguments)], "items": items})
        return out, scored

    v39.score_answers = score_answers


def close() -> None:
    if _FO:
        _FO[0].close()
        _FO.clear()
