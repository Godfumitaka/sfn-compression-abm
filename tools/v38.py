"""v3.8（2026-09-28 夕、委任書「v3.8（本人が受け取った証拠だけで学ぶ会計）」）：旗 --own-evidence。
仕様：control/sfn_claude_handoff_2026-09-28.md の付録（D-08〜D-11）と、委任書 1 の追加 1〜4。★ abm/ は変えない。旗を切れば何もしない（v3.7 と一字一句同じ）。
主条件だけに限る（α＝0・pending_claims オフ・charge1＝d32・--no-charge2。ほかの設定では止める）。

D-08 開示で確かめられた関係を、行の確認実績へ一回入れる。
  ・本人が実際に受け取った開示（coin.f_fired のときの伏せ辺）だけを使う。研究者用の伏せ辺（_update_accounting の revealed_edge）は、開示が無ければ読まない（T02）。
  ・tools/v31.py の d32 は、外れ＋開示の試行で内の会計を f_fired＝False で呼ぶ（①を二重にしないため）。受け取った開示は、この包みが一番外で本当の coin から
    取り出して内へ渡すので、その内部の制御で消えない。
  ・行の関係を、選ばれた写しで具体化（loop._mapped_arguments）し、「見えている関係 ＋ 受け取った開示」と、述語と引数の組が完全に一致すれば確認（「充足」）。
  ・直接の予測元（sme_projection__<行の関係 ID>）は、実際に出した予測が受け取った開示と完全に一致すれば確認（写しで位置が決まらない高階の行でも、予測の引数で照らす。T12）。
D-09 確かめられないこと（未確認）は、加点も減点もしない。確認率の分母を「評価した回数」にする。
  ・MeritAccumulator に評価の基底（eval_basis）を足した型（MeritAccumulatorV38）を、旗のときだけ使う。
    basis＝確認の基底、eval_basis＝評価の基底（確認＋反証）、opportunity_basis＝使った回数の基底（今の意味のまま。p_R・P_ext もこれを読む）。
  ・参加率 participation ＝ Σbasis ÷ Σeval_basis（eval_basis が無い行は今までどおり opportunity_basis）。減衰は三つとも同じ梯子・同じ順（減衰してから加算）。
  ・生まれたときの実績（比べた二つの場面の 2 回分、initial_merit の seed）は変えない：eval_basis は、その行を初めて更新するときに opportunity_basis の値から始める
    （生まれてから最初の更新までは、この二つは同じ seed）。
D-10 穴埋めの予測が当たり（score.hit）、開示を受け取ったら、予測元の席（filling__<R>__<席>__<登録>）の履歴へ、その述語の観察を一回足す
  （abm/filling.py の observe_slot をそのまま使う。生きている行でも墓石でも。述語名だけで他の席へ足さない）。
  ・通常の席の観察（m1）は、この試行の開示前の場面を使うので、開示された関係そのものは観察しない。同じ試行・同じ席・同じ関係の二重は、ここで一回に限る。
  ・席の履歴は、直し②（fix2）を通して照合・同化・支持比にも効く（委任書の追加 3。正当な波及として扱う）。更新の前後を side に書く。
D-11 使った定義（R_used と写しがある定義。話したか黙ったかを問わない）の生存行で、開示を受け取り、写しで位置が決まり（_mapped_arguments が None でない）、
  「見えている関係 ＋ 受け取った開示」の中にその関係が無ければ「反証」：評価回数 +1・確認回数 +0。追加の罰（②）は付けない。
  ・開示が無ければ、見えない関係はすべて未確認（委任書の追加 1：本人は「一つの場面で伏せられる関係は一本だけ」を知らない）。位置が決まらない行も未確認。
  ・① の罰は今までどおり（tools/v31.py の d32。外れ＋開示のときだけ）。
記録（side、kind＝"v38"。その試行に何かあったときだけ）：受け取った開示・予測の出どころ・評価した行ごとの元の判定と新しい判定・確認／評価／使用の追加分と前後の参加率・
  席の観察の前後。
使い方：tools/v3_run.py の --own-evidence（--no-charge2 と一緒に）。検査用に V38_FROM＝t（試行 t から v3.8 を効かせ、それより前は v3.7 のまま）。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace

STATS: dict = {}
CTX: dict = {}
_REAL: dict = {}


def _key(rel):
    return (rel.predicate, tuple(rel.arguments))


def install(fo) -> None:
    import abm.accounting as acc_mod
    import abm.loop as loop
    from abm.definition import MeritAccumulator
    from abm.domains import Abstain, EdgePrediction
    from abm.filling import observe_slot

    start = int(os.environ.get("V38_FROM", "0"))
    STATS.clear()
    STATS.update(trials=0, received=0, confirmed_visible=0, confirmed_disclosure=0, confirmed_by_prediction=0,
                 refuted=0, unconfirmed=0, undetermined=0, seat_obs_added=0, seat_obs_skipped=0,
                 lazy_init=0, active_from=start)

    @dataclass(frozen=True, slots=True)
    class MeritAccumulatorV38(MeritAccumulator):
        eval_basis: tuple = ()

    _REAL.setdefault("classify_row", loop.classify_row)
    _REAL.setdefault("update_merit", loop.update_merit)
    _REAL.setdefault("participation", acc_mod.participation)
    real_classify = loop.classify_row          # ★ --no-charge2 の包みの外から包む（② はもう ③ になっている）
    real_update_merit = loop.update_merit
    real_participation = acc_mod.participation
    real_accounting = loop._update_accounting  # ★ v31 の d32 の包みの外から包む（本当の coin を見る）

    def participation(accumulator):
        ev = getattr(accumulator, "eval_basis", ())
        if ev:
            den = sum(ev)
            return sum(accumulator.basis) / den if den > 0.0 else 0.0
        return real_participation(accumulator)

    def classify_row(row, scene, entity_mapping, relation_mapping):
        reason = real_classify(row, scene, entity_mapping, relation_mapping)
        if not CTX.get("active"):
            return reason
        new = reason
        received = CTX.get("received")
        pos = loop._mapped_arguments(row.relation, entity_mapping, relation_mapping)
        if reason == "充足":
            STATS["confirmed_visible"] += 1
        elif received is not None and CTX.get("src_row") == row.relation.relation_id and CTX.get("pred_matches_received"):
            new = "充足"; STATS["confirmed_by_prediction"] += 1
        elif received is not None and pos is not None and (row.relation.predicate, tuple(pos)) == _key(received):
            new = "充足"; STATS["confirmed_disclosure"] += 1
        elif received is not None and pos is not None:
            new = "反証"; STATS["refuted"] += 1
        elif pos is None:
            STATS["undetermined"] += 1
        else:
            STATS["unconfirmed"] += 1
        CTX["last"] = (row.slot_index, row.registered_at, new)
        CTX["rows"].append({"slot": row.slot_index, "reg": row.registered_at, "pred": row.relation.predicate,
                            "pos": list(pos) if pos is not None else None, "元": reason, "新": new})
        return new

    def update_merit(accumulator, decay, **kw):
        if not CTX.get("active"):
            return real_update_merit(accumulator, decay, **kw)
        last = CTX.pop("last", None)
        reason = last[2] if (last is not None and last[0] == accumulator.slot_index and last[1] == accumulator.registered_at) else None
        applied = bool(kw.get("applied"))
        if not applied:
            reason = None
        factors = tuple(float(v) for v in decay)
        ev = getattr(accumulator, "eval_basis", ())
        if not ev:
            ev = accumulator.opportunity_basis; STATS["lazy_init"] += 1
        inc = 1.0 if reason in ("充足", "反証") else 0.0
        new_ev = tuple(old * f + inc for old, f in zip(ev, factors))
        p_before = participation(accumulator)
        out = real_update_merit(accumulator, decay, **kw)
        out = MeritAccumulatorV38(out.slot_index, out.registered_at, out.basis, out.opportunity_basis, out.use_count,
                                  out.ext_use_count, out.ext_basis, new_ev)
        if reason is not None and CTX["rows"]:
            r = CTX["rows"][-1]
            if r["slot"] == accumulator.slot_index and r["reg"] == accumulator.registered_at:
                r.update({"確認+": 1 if reason == "充足" else 0, "評価+": int(inc), "使用+": int(applied),
                          "P前": p_before, "P後": participation(out)})
        return out

    def update_accounting(state, output, scene, config, horizon, score, coin, revealed_edge):
        t = coin.t
        active = t >= start
        if active:
            if config.alpha or config.pending_claims:
                raise ValueError("--own-evidence は α＝0・pending_claims オフの主条件だけ（仕様の対象条件）")
            received = revealed_edge if coin.f_fired else None    # ★ 研究者用の伏せ辺は、開示が無ければ読まない（T02）
            p = output.prediction
            pred = p.edge if isinstance(p, EdgePrediction) else None
            rid = pred.relation_id if pred is not None else ""
            src_row = rid[len("sme_projection__"):] if rid.startswith("sme_projection__") else None
            CTX.clear()
            CTX.update(active=True, received=received, src_row=src_row, rows=[],
                       pred_matches_received=(received is not None and pred is not None and _key(pred) == _key(received)))
            STATS["trials"] += 1; STATS["received"] += received is not None
        try:
            next_state, acc = real_accounting(state, output, scene, config, horizon, score, coin, revealed_edge)
        finally:
            rows = CTX.get("rows", []) if active else []
            CTX.clear()
        if not active:
            return next_state, acc
        seat = None
        p = output.prediction
        if (received is not None and isinstance(p, EdgePrediction) and bool(score.hit) and _key(p.edge) == _key(received)
                and p.edge.relation_id.startswith("filling__")):
            _, R, slot, reg = p.edge.relation_id.split("__")
            slot = int(slot)
            key = (R, slot)
            before = next_state.slot_history.get(key)
            history = observe_slot(next_state.slot_history, R, slot, p.edge.predicate, config.local_lambda)
            after = history.get(key)
            next_state = replace(next_state, slot_history=history)
            STATS["seat_obs_added"] += 1
            alive = None
            d = next_state.definitions.get(R)
            if d is not None:
                c = next((c for c in d.constituents if c.slot_index == slot), None)
                alive = None if c is None else bool(c.alive)
            seat = {"R": R, "slot": slot, "reg": int(reg), "述語": p.edge.predicate, "生きている行": alive,
                    "前": (dict(before) if hasattr(before, "items") else sorted(before or ())),
                    "後": (dict(after) if hasattr(after, "items") else sorted(after or ()))}
        if rows or seat or received is not None:
            src = None
            if isinstance(p, EdgePrediction):
                rid = p.edge.relation_id
                src = "投影" if rid.startswith("sme_projection__") else "穴埋め" if rid.startswith("filling__") else "その他"
            fo.write(json.dumps({"kind": "v38", "trial": t, "R_used": output.trace.get("R_used"), "hit": bool(score.hit),
                                 "受け取った開示": ([received.predicate, list(received.arguments)] if received is not None else None),
                                 "予測": ([p.edge.relation_id, p.edge.predicate, list(p.edge.arguments)] if isinstance(p, EdgePrediction) else None),
                                 "出どころ": src, "行": rows, "席の観察": seat}, ensure_ascii=False) + "\n")
        return next_state, acc

    loop.classify_row = classify_row
    loop.update_merit = update_merit
    acc_mod.participation = participation
    loop._update_accounting = update_accounting
