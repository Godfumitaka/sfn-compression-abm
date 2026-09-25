"""v3.1（2026-09-25 決裁 アストラさん）の変更。★ abm/ は変えない。ドライバの作業プロセスの中で差し替える。既定は今の動き。

D-31 取り込み（--extend-rule）
  profit（v3.1a）：同化で足すかを「足すと儲けの合計 Σ(V−θ′) が増えるか」で一本ずつ決め、増えなくなったら止める。
    判定の V
      今ある生きている行：使われて決まる部分（参加率・罰の蓄え・embed）はそのまま、構造の部分（新規スロット数 → c）だけを、
        「生きている行＋足す行」の組の中で計算し直す（値段の凍結は変えない。判定のためだけの計算）。
      足す行：生まれた直後の値 1＋c/ℓ（c は同じ組の中で、ℓ はその試行の p̂）。
    候補：今と同じく、土台と今の場面の構造の対で、述語が一致し、生きている行の述語に無いもの（abstraction.py:202-203）。
      ★ 死んだ述語（墓石の述語）も候補になる（価値の審査だけで許す）。戻った回数を記録する。
    同点：同点の候補をまとめて足して増えるならまとめて、増えないなら組の中の行と引数の共有が多い方。それでも決まらなければ止めて記録。
    席：足す行の今の場面での引数の組（順番も同じ）と、墓石の行を今の場面に写した引数の組が同じで、
        生きている行のいない墓石の席があればそこへ。無ければ新しい席（m_alloc を一つ増やす）。行数の上限なし。
        ★ 墓石の行の引数は、その行が生まれた場面の ID なので、定義（墓石込み）を今の場面に写して比べる（abstraction.py:125-129 と同じ写し方）。
    値段：塔の参照価格の log₂ m_alloc（FrozenPrice.m_alloc_at_reg）には、足した後の m_alloc を入れる。
      ★ m_alloc_at_reg は今のコードでは記録されるだけで、V の計算には使われていない（definition.py:20 のほかに出てこない）。
  none（v3.1b）：同化では行を足さない。slot_history の記録・同化の回数など、ほかの同化の処理は今のまま（m1 が行う）。

D-32 ① の罰（--charge1 d32、両方の版）
  投影で外したら：① は予測を出した行（sme_projection__<行の関係 ID>）だけに付ける。前提の行には付けない。
    親への広げ（repair_scope）は今の設定のまま、その行を起点にする（loop.py:367-381 の _repair_targets をそのまま使う）。額は今と同じ（loop.py:299）。
  穴埋め（墓石・生きている行の空いた位置、filling__R__位置__登録試行）で外したら：① は行に付けず、
    その位置の slot_history で、予測した述語の回数を一つ減らす（0 未満にしない）。
    ★ 予測した述語がその位置の履歴に無いとき（署名からの候補で埋めたとき）は、履歴を変えない（記録だけ残す）。
  ★ ① が立つ条件（R_used あり・棄権でない・外れ・開示あり）は今と同じ（loop.py:293）。今の ① は、本物の会計を「開示なし」として呼んで止め、
    その後にここで付ける。② と棄権の課金は本物の会計のまま。
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Mapping

EPS = 1e-9
CFG: dict = {"extend_rule": "v2", "charge1": "v2", "theta": 0.0, "w": 0.0, "kappa": 1.0, "beta": 0.0,
             "target": None, "fo": None}
STATS: dict = {}


def _log(obj):
    fo = CFG.get("fo")
    if fo is not None:
        fo.write(json.dumps(obj, ensure_ascii=False) + "\n")


def install(extend_rule: str, charge1: str, theta: float, w: float, kappa: float, beta: float, fo=None) -> None:
    import abm.abstraction as ab
    import abm.loop as loop
    CFG.update(extend_rule=extend_rule, charge1=charge1, theta=theta, w=w, kappa=kappa, beta=beta, fo=fo)
    STATS.clear(); STATS.update(ext_calls=0, ext_added=0, ext_new_seat=0, ext_reused_seat=0, ext_returned_dead=0,
                                ext_tie_unresolved=0, c1_projection=0, c1_filling=0, c1_other=0)
    if beta:
        raise ValueError("v31 の儲けの判定は β=0 だけに対応（b2 は β=0）")
    if extend_rule == "profit":
        ab._extend_definition = _extend_profit
    elif extend_rule == "none":
        ab._extend_definition = _extend_none
    elif extend_rule != "v2":
        raise ValueError(extend_rule)
    if charge1 == "d32":
        real = loop._update_accounting

        def wrapped(state, output, scene, config, horizon, score, coin, revealed_edge):
            from abm.domains import Abstain
            used = output.trace.get("R_used")
            fire = (used is not None and output.trace.get("definition_alignment") is not None
                    and not isinstance(output.prediction, Abstain) and not score.hit and coin.f_fired)
            if not fire:
                return real(state, output, scene, config, horizon, score, coin, revealed_edge)
            next_state, acc = real(state, output, scene, config, horizon, score, replace(coin, f_fired=False), revealed_edge)
            return _charge1_d32(state, next_state, acc, output, config, revealed_edge)

        loop._update_accounting = wrapped
    elif charge1 != "v2":
        raise ValueError(charge1)


def _charge1_d32(state, next_state, acc, output, config, revealed_edge):
    from abm.accounting import exception_cost
    from abm.definition import ExceptionAccumulator
    import abm.loop as loop
    used = output.trace["R_used"]
    definition = state.definitions[used]
    rid = output.prediction.edge.relation_id
    sources = acc.get("charge_source")
    sources = {k: list(v) for k, v in sources.items()} if sources else {"①": [], "②": [], "衝突": []}
    charged_total = 0.0
    exceptions = dict(next_state.exceptions)
    history = dict(next_state.slot_history)
    if rid.startswith("sme_projection__"):
        STATS["c1_projection"] += 1
        row_id = rid[len("sme_projection__"):]
        targets = loop._repair_targets(definition, {row_id}, config.repair_scope)
        cost = exception_cost(definition.m_live, state.p_hat.code_length(revealed_edge.predicate))
        for row in definition.constituents:
            if row.alive and row.relation.relation_id in targets:
                key = (used, row.slot_index)
                exceptions[key] = loop._charge(exceptions.get(key, ExceptionAccumulator((0.0,) * 16, 0.0, 0)), cost)
                charged_total += cost
                sources["①"].append(key)
    elif rid.startswith("filling__"):
        STATS["c1_filling"] += 1
        _, R, slot, reg = rid.split("__")
        key = (R, int(slot))
        pred = output.prediction.edge.predicate
        cur = history.get(key)
        before = after = None
        if isinstance(cur, Mapping) and pred in cur:
            # ★ その席の履歴にある述語だけを一つ減らす（0 未満にしない）。履歴に無い述語（署名からの候補、filling.py:203-209）は触らない。
            counts = dict(cur); before = counts[pred]; after = max(0, before - 1)
            counts[pred] = after; history[key] = counts
        sources.setdefault("①_穴埋め", []).append({"R": R, "slot_index": int(slot), "registered_at": int(reg),
                                                "述語": pred, "前": before, "後": after})
    else:
        STATS["c1_other"] += 1
        sources.setdefault("①_その他", []).append(rid)
    acc = dict(acc)
    acc["charge_source"] = sources if any(sources.get(k) for k in sources) else None
    acc["exception_bits_charged"] = acc.get("exception_bits_charged", 0.0) + charged_total
    return replace(next_state, exceptions=exceptions, slot_history=history), acc


def _extend_none(old, pairs, state, trial, *, pricing_rule="legacy", base=None, refill_rule="legacy"):
    STATS["ext_calls"] += 1
    return old


def _v_existing(row, name, scope, state, pricing_rule, predicate_of):
    from abm.abstraction import _new_slot_count
    from abm.accounting import embed_value, participation
    from abm.definition import ExceptionAccumulator
    acc = state.merit.get((name, row.slot_index, row.registered_at))
    if acc is None:
        return None
    exc = state.exceptions.get((name, row.slot_index), ExceptionAccumulator((0.0,) * 16, 0.0, 0))
    ns = _new_slot_count(row.relation, tuple(scope), pricing_rule=pricing_rule, predicate_of=predicate_of)
    c = 1 + 3 * len(row.relation.arguments) - 3 * ns
    ell = row.frozen_price.ell_frozen
    denom = sum(acc.basis); charged = sum(exc.basis)
    a = ((ell + c) - (charged / denom if denom > 0.0 else 0.0)) / ell
    v = participation(acc) * a
    if CFG["w"]:
        emb = state.embed.get((name, row.slot_index, row.registered_at))
        if emb is not None:
            v += CFG["w"] * embed_value(emb, CFG["kappa"]) / ell
    return v


def _v_new(rel, scope, p_hat, pricing_rule, predicate_of):
    from abm.abstraction import _new_slot_count
    ns = _new_slot_count(rel, tuple(scope), pricing_rule=pricing_rule, predicate_of=predicate_of)
    c = 1 + 3 * len(rel.arguments) - 3 * ns
    ell = p_hat.code_length(rel.predicate)
    return (ell + c) / ell


def _conn(q, S):
    qa = set(q.arguments)
    return sum(1 for r in S if r.relation_id != q.relation_id and qa & set(r.arguments))


def _extend_profit(old, pairs, state, trial, *, pricing_rule="legacy", base=None, refill_rule="legacy"):
    from abm.abstraction import _definition_graph
    from abm.accounting import freeze_price
    from abm.definition import Constituent, NamedDefinition
    from abm.filling import _mapped_arguments
    from abm.sme import map_graphs
    STATS["ext_calls"] += 1
    theta = CFG["theta"]
    live = [row for row in old.constituents if row.alive]
    live_rel = [row.relation for row in live]
    live_preds = {r.predicate for r in live_rel}
    dead_preds = {row.relation.predicate for row in old.constituents if not row.alive}
    cands = [(l, r) for l, r in pairs if l.predicate not in live_preds]
    predicate_of = {item.relation_id: item.predicate for item in base.relations} if base is not None else None
    info = {"kind": "extend_profit", "trial": trial, "R": old.name, "candidates": len(cands)}
    if not cands:
        _log({**info, "chosen": 0}); return old

    def profit(A):
        scope = live_rel + [a for a, _ in A]
        tot = 0.0
        for row in live:
            v = _v_existing(row, old.name, scope, state, pricing_rule, predicate_of)
            if v is not None:
                tot += v - theta
        for a, _ in A:
            tot += _v_new(a, scope, state.p_hat, pricing_rule, predicate_of) - theta
        return tot

    A: list = []
    G = profit(A)
    info["profit_start"] = G
    ties = 0
    while True:
        rest = [c for c in cands if c not in A]
        if not rest:
            break
        scored = [(profit(A + [c]), c) for c in rest]
        best = max(g for g, _ in scored)
        if not best > G + EPS:
            break
        tied = [c for g, c in scored if abs(g - best) <= EPS]
        if len(tied) == 1:
            A.append(tied[0])
        elif profit(A + tied) > G + EPS:
            A.extend(tied); ties += 1
        else:
            pool = live_rel + [a for a, _ in A]
            m = max(_conn(c[0], pool + [c[0]]) for c in tied)
            strong = [c for c in tied if _conn(c[0], pool + [c[0]]) == m]
            if len(strong) == 1:
                A.append(strong[0]); ties += 1
            else:
                STATS["ext_tie_unresolved"] += 1; info["tie_unresolved"] = True
                break
        G = profit(A)
    info["chosen"] = len(A); info["profit_end"] = G; info["ties"] = ties
    if not A:
        _log(info); return old
    # 席を決める。墓石の行を今の場面に写した引数の組と、足す行の今の場面での引数の組（右側の関係の引数）を比べる。
    target = CFG.get("target")
    occupied = {row.slot_index for row in live}
    free_seats: dict[int, list] = {}
    for row in old.constituents:
        if not row.alive and row.slot_index not in occupied:
            free_seats.setdefault(row.slot_index, []).append(row)
    seat_args: dict[int, set] = {}
    if target is not None and free_seats:
        al = map_graphs(_definition_graph(old, mode="all"), target).alignment
        for s, rows in free_seats.items():
            seat_args[s] = {pos for pos in (_mapped_arguments(r.relation, al.entity_mapping, al.relation_mapping) for r in rows)
                            if pos is not None}
    used_seats: set[int] = set()
    m_alloc = old.m_alloc
    placed = []
    for left, right in A:
        seat = next((s for s in sorted(seat_args) if s not in used_seats and tuple(right.arguments) in seat_args[s]), None)
        if seat is None:
            seat = m_alloc; m_alloc += 1; STATS["ext_new_seat"] += 1
        else:
            used_seats.add(seat); STATS["ext_reused_seat"] += 1
        placed.append((left, seat))
    scope = tuple(a for a, _ in A) + tuple(live_rel)
    rows = list(old.constituents)
    returned = 0
    from abm.abstraction import _new_slot_count
    for left, seat in placed:
        price = freeze_price(state.p_hat, left,
                             _new_slot_count(left, scope, pricing_rule=pricing_rule, predicate_of=predicate_of), m_alloc)
        rows.append(Constituent(seat, trial, left, price))
        returned += left.predicate in dead_preds
    STATS["ext_added"] += len(placed); STATS["ext_returned_dead"] += returned
    info.update(new_seats=sum(1 for _, s in placed if s >= old.m_alloc), reused_seats=sum(1 for _, s in placed if s < old.m_alloc),
                returned_dead=returned, m_alloc_before=old.m_alloc, m_alloc_after=m_alloc,
                preds=[l.predicate for l, _ in placed])
    _log(info)
    return NamedDefinition(old.name, tuple(rows), m_alloc, old.registered_at, old.assimilation_count)
