"""U の照合（旗 --u-struct）と、覚え直しの初期の評価（旗 --relearn-init）。2026-09-30 の委任書「U の照合の直し・覚え直しの初期の評価・支持の三分類」の 1・2。
★ abm/ は変えない。旗を切れば何もしない（v3.10hsa-main と一字一句同じ）。

1 --u-struct（--v39 と --hist-role と一緒に使う）
  今：U の席は照合のグラフに置かない。U の子を持つ親の引数は、見えている関係・物には当てはまらず、見えていない ID にだけ当てはまる（tools/v39.py _install_candidates）。
  直し：U の席を、名前の条件を持たない関係の位置として、構造の照合に参加させる。
    U の席そのものは照合の候補にならない（グラフに置かないのは今のまま。支持の分子にも分母にも入らない）。
    U の子を持つ親の候補を作るとき、U の子の引数は次のとおり当てはめる。
      見えている物：当てはまらない（関係と物の区別）。
      見えている関係 C：U の席の行と C の引数の数が同じなら当てはまる。このとき U の席の行の引数も C の引数と対にする
        （行の引数が定義の関係なら関係と、物なら見えている物と。種類が違えば当てはまらない）。
        対は親の候補に入るので、既存の物・関係の対応と食い違えば、その親の候補は採られない（map_graphs の _candidate_fits）。
      見えていない ID：今のまま当てはまる。
    一つの候補の中で、同じ左が二つの右に、又は二つの左が同じ右に当たるなら、その候補は作らない（同じ席を複数の位置へ当てはめない）。
    親自身の名前の条件は今のまま（F は名前の一致、H は履歴の名）。忘れた名前（U の席の名）は照合に使わない（U の席の行の述語は見ない）。
  U の席の観察（m1 の席の履歴）：親が照合で写れば、その親の同じ引数の位置の子を U の席の対応先にし、子が見えていればその述語を観察として足す
    （tools/histrole.py の親の子の規則を、U の席については階を問わず使う。親が無い・写らない・子が見えないときは足さない）。
2 --relearn-init（--u-struct と --v310-be と一緒に使う）
  U の席が観察を受けて覚え直す（U→H、tools/v39.py reconcile）とき、その観察一回だけの新しい H（名前 1 回）の記録の初期値に、
  同じ観察を H で答えた場合（h_answer）と U で答えた場合（u_answer）の書換ビット（一致なら 0、違えば観察した名の ℓ）を入れる（誕生の初期の成績と同じ形）。
  ℓ・H・U の答えは、同じ時点の p̂ と同じ場面で出す。古い履歴や点数は復活させない（世代は reconcile のとおり新しい）。
  未来の予測の成功とは数えない：B の採点の累計（R_B）には足さず、side の kind＝"relearn_init" に別に書く。
  観察が一つでない（鍵の回数の和が 1 でない）覚え直しには初期値を入れず、数だけ記録する。
"""
from __future__ import annotations

import json

CFG: dict = {}
STATS: dict = {}
UREG: dict = {}      # id(g) → {U の席の関係 ID: Relation}
CTX: dict = {}


def u_candidates(prev):
    def _alignment_candidates(base_graph, partial_graph):
        import abm.sme as sme
        import v39
        from abm.sme import AlignmentCandidate
        entry = v39.REG.get(id(base_graph))
        if entry is None or entry[0] is not base_graph:
            return prev(base_graph, partial_graph)
        _, hallow, ushield = entry
        urows = UREG.get(id(base_graph), {})
        base_relation_ids = sme._relation_ids(base_graph)
        def_rel_ids = base_relation_ids | ushield
        partial_by_id = {r.relation_id: r for r in partial_graph.relations}
        partial_relation_ids = frozenset(partial_by_id)
        partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
        candidates = []
        for left in sorted(base_graph.relations, key=sme._relation_key):
            allowed = hallow.get(left.relation_id)
            for right in sorted(partial_graph.relations, key=sme._relation_key):
                if len(left.arguments) != len(right.arguments):
                    continue
                if right.predicate != left.predicate and (allowed is None or right.predicate not in allowed):
                    continue
                entity_pairs = []
                relation_pairs = []
                compatible = True
                upair = False
                for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                    if left_arg in ushield:
                        if right_arg in partial_entity_ids:
                            compatible = False
                            break
                        if right_arg in partial_relation_ids:
                            # ★ --u-struct：U の子が見えている関係に当てはまる（引数の数・種類・物の対応を守る）
                            u = urows.get(left_arg)
                            C = partial_by_id[right_arg]
                            if u is None or len(u.arguments) != len(C.arguments):
                                compatible = False
                                break
                            upair = True
                            relation_pairs.append((left_arg, right_arg))
                            for ua, ca in zip(u.arguments, C.arguments):
                                if ua in def_rel_ids:
                                    if ca in partial_entity_ids:
                                        compatible = False
                                        break
                                    relation_pairs.append((ua, ca))
                                elif ca in partial_entity_ids:
                                    entity_pairs.append((ua, ca))
                                else:
                                    compatible = False
                                    break
                            if not compatible:
                                break
                            continue
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    left_is_relation = left_arg in base_relation_ids
                    right_is_relation = right_arg in partial_relation_ids
                    right_is_unobserved = (not right_is_relation) and (right_arg not in partial_entity_ids)
                    if left_is_relation and right_is_unobserved:
                        relation_pairs.append((left_arg, right_arg))
                        continue
                    if left_is_relation != right_is_relation:
                        compatible = False
                        break
                    if left_is_relation:
                        relation_pairs.append((left_arg, right_arg))
                    else:
                        entity_pairs.append((left_arg, right_arg))
                if compatible and upair:
                    # ★ U の子を見えている関係に当てはめた候補だけ：候補の中の食い違いを確かめ、重複を除く（ほかの候補は今と同じ形）
                    if not _consistent(entity_pairs, relation_pairs, left.relation_id, right.relation_id):
                        STATS["cand_inconsistent"] = STATS.get("cand_inconsistent", 0) + 1
                        compatible = False
                    else:
                        entity_pairs, relation_pairs = sorted(set(entity_pairs)), sorted(set(relation_pairs))
                        STATS["cand_u_visible"] = STATS.get("cand_u_visible", 0) + 1
                if compatible:
                    candidates.append(AlignmentCandidate(
                        base_relation_id=left.relation_id, partial_relation_id=right.relation_id,
                        predicate=left.predicate, arity=len(left.arguments),
                        entity_pairs=tuple(sorted(entity_pairs)), relation_pairs=tuple(sorted(relation_pairs))))
        return tuple(sorted(candidates, key=sme._candidate_order_key))
    return _alignment_candidates


def _consistent(entity_pairs, relation_pairs, left_id, right_id) -> bool:
    """一つの候補の中で、同じ左が二つの右に、又は二つの左が同じ右に当たらないか（親自身の対も含める）。"""
    for pairs in (entity_pairs, list(relation_pairs) + [(left_id, right_id)]):
        fw, bw = {}, {}
        for a, b in pairs:
            if fw.setdefault(a, b) != b or bw.setdefault(b, a) != a:
                return False
    return True


def install(fo, *, relearn_init: bool = False) -> None:
    """tools/v3_run.py の worker で、v39・v310be のあとに入れる。"""
    import abm.loop as loop
    import abm.sme as sme
    import histrole
    import v39
    CFG.clear()
    STATS.clear()
    UREG.clear()
    CTX.clear()
    CFG.update(relearn_init=bool(relearn_init))
    STATS.update(relearn_init=0, relearn_init_multi_obs=0, relearn_init_rU_gt_rH=0)
    real_graph = v39.v39_graph

    def v39_graph(d, slot_history):
        g = real_graph(d, slot_history)
        _, _hallow, ushield = v39.REG[id(g)]
        UREG[id(g)] = {row.relation.relation_id: row.relation for row in d.constituents if row.relation.relation_id in ushield}
        return g

    v39.v39_graph = v39_graph
    real_unreg = v39.unregister

    def unregister(g):
        UREG.pop(id(g), None)
        real_unreg(g)

    v39.unregister = unregister
    sme._alignment_candidates = u_candidates(sme._alignment_candidates)
    histrole.CFG["u_all_orders"] = True
    if not relearn_init:
        return

    # 2 覚え直しの初期の評価：場面を控え、reconcile の覚え直しに初期値を入れる
    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        CTX["scene"] = target
        return real_m1(state, base, target, alignment, trial, **kw)

    loop.m1 = m1
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        CTX["scene"] = scene
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting
    real_rec = v39.reconcile

    def reconcile(state, trial, why):
        n0 = len(v39.CTX.get("relearn") or [])
        out = real_rec(state, trial, why)
        new = (v39.CTX.get("relearn") or [])[n0:]
        if new:
            out = _apply_init(out, trial, why, new, fo)
        return out

    v39.reconcile = reconcile


def _apply_init(state, t, why, events, fo):
    from dataclasses import replace
    import v39
    import v310be
    config = v39.CTX["config"]
    L = v39.code_lengths(state.p_hat)
    seats = dict(state.v39_seats)
    scene = CTX.get("scene")
    for ev in events:
        d = state.definitions[ev["R"]]
        row = next(r for r in d.constituents if r.slot_index == ev["slot"])
        h = {k: v for k, v in v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).items() if v > 0}
        rec = {"kind": "relearn_init", "trial": t, "R": d.name, "slot": row.slot_index, "gen": ev["gen"], "by": why,
               "obs": sorted(h.items())}
        if sum(h.values()) != 1:
            STATS["relearn_init_multi_obs"] += 1
            rec["skipped"] = "観察が一つでない"
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            continue
        o = next(iter(h))
        ha = v39.h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)[0]
        ua = v39.u_answer(d, row, scene, state.p_hat, config.higher_order_predicates)[0] if scene is not None else None
        lo = v310be._ell(o, L)
        rH = 0.0 if ha == o else lo
        rU = 0.0 if ua == o else lo
        col = lambda v: (float(v),) * 16  # noqa: E731
        key = (d.name, row.slot_index)
        seats[key] = replace(seats[key], init=(col(0.0), col(rH), col(rU), col(1.0)))
        STATS["relearn_init"] += 1
        STATS["relearn_init_rU_gt_rH"] += rU > rH
        rec.update(H=ha, U=ua, r_H=rH, r_U=rU)
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return replace(state, v39_seats=seats)
