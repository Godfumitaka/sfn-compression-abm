"""予測で作った対応を再利用する研究者用の候補記録。模型へは返さない。"""
from __future__ import annotations

from dataclasses import replace
from random import Random
import inspect
import json
import sys

ST = {}


def prediction_key(prediction):
    from abm.domains import EdgePrediction
    return (prediction.edge.to_dict() if isinstance(prediction, EdgePrediction)
            else {"abstain_reason": prediction.reason})


def diagnostic_call():
    return any(f.function in ("variants_correct", "_measure", "_probe")
               and f.frame.f_globals.get("__name__") in ("cflearn", "cfvalue", "probeworld")
               for f in inspect.stack())


def candidate_answer(item, scene, state, config, rng_state):
    """照合を呼ばず、固定した対応から通常の投影・穴埋め・門で答える。"""
    import abm.agent_runtime as ar
    from abm.domains import Abstain, EdgePrediction
    from abm.sme import project
    import v39
    _ratio, support, definition, graph, alignment, n, n3 = item
    passed = support >= ar._need(config.tau_acc, n)
    path = source = slot = None
    if not passed:
        prediction = Abstain(reason="below_tau")
    else:
        fids = {r.relation.relation_id for r in definition.constituents if r.alive}
        alignment = replace(alignment, candidate_projections=tuple(
            x for x in alignment.candidate_projections if x in fids))
        prediction = project(alignment, graph, scene, prototype_prior_weight=0.0)
        rng = Random()
        rng.setstate(rng_state)
        filling = v39.fill_v39(definition, scene, alignment.entity_mapping,
                              alignment.relation_mapping, state.slot_history, state.p_hat,
                              config.fill_selection, rng,
                              higher_order_predicates=config.higher_order_predicates,
                              local_lambda=config.local_lambda)
        prediction, path = v39.fill_decision(prediction, filling, None)
        if isinstance(prediction, EdgePrediction):
            if path == "projection":
                source = "F_proj"
                rid = prediction.edge.relation_id.removeprefix("sme_projection__")
                slot = next((r.slot_index for r in definition.constituents
                             if r.relation.relation_id == rid), None)
            else:
                i = next((i for i, r in enumerate(filling.relations) if r == prediction.edge), None)
                if i is None:
                    raise RuntimeError("候補の穴埋めの答えが通常の候補に無い")
                slot = filling.slot_indices[i]
                row = next(r for r in definition.constituents if r.slot_index == slot)
                source = v39.seat_state(definition, row, state.slot_history) + "_fill"
    edge = prediction.edge.to_dict() if isinstance(prediction, EdgePrediction) else None
    return dict(R=definition.name, born_trial=definition.registered_at,
                result_id=alignment.sme_result_id, S_dx=alignment.total_score, N3=float(n3),
                support=support, denominator=n, gate_passed=passed, prediction=edge,
                abstain_reason=prediction.reason if edge is None else None,
                source=source, slot=slot, prediction_path=path)


def candidates(pool, scene, state, config, rng_state):
    """各候補の前後で診断用の控えを戻す。順・他候補の有無に依存させない。"""
    import probeworld
    import cstar_runtime
    saved = probeworld._snapshot_modules()
    rows = []
    try:
        for item in pool:
            probeworld._restore_modules(saved)
            with cstar_runtime.phase(state, config, scene, cstar_runtime.CFG.get("match_cstar", False)):
                rows.append(candidate_answer(item, scene, state, config, rng_state))
    finally:
        probeworld._restore_modules(saved)
    return rows


def finish_row(row, held, original_hit):
    """正解の参照は予測の後の研究者の記録だけ。この値の読み手は集計だけ。"""
    for c in row["candidates"]:
        p = c["prediction"]
        c["hit"] = (p is not None and p["predicate"] == held.predicate
                    and tuple(p["arguments"]) == tuple(held.arguments))
    row["any_correct"] = any(c["hit"] for c in row["candidates"])
    row["correct_gate_passed"] = any(c["hit"] and c["gate_passed"] for c in row["candidates"])
    row["original_hit"] = bool(original_hit)
    row["classification"] = ("" if original_hit or "abstain_reason" in row["prediction"] else
                             "選び間違い" if row["correct_gate_passed"] else "区別の喪失")
    return row


def install(path, *, check=False):
    import abm.loop as loop
    import smeshared
    import smereplay
    import v39
    ST.clear()
    ST.update(f=smeshared._text_gzip(path), rows=0, pending={}, pool=None, selected=None)
    real_choice, real_select, real_predict = smeshared._definition_choice, v39.select_definition, loop.predict

    def choice(pool, scene):
        if ST.get("capturing"):
            ST["pool"] = tuple(pool)
        return real_choice(pool, scene)

    def select(*a, **kw):
        value = real_select(*a, **kw)
        if ST.get("capturing"):
            ST["selected"] = value
        return value

    smeshared._definition_choice, v39.select_definition = choice, select

    def predict(ai, state, config, rng):
        if diagnostic_call():
            return real_predict(ai, state, config, rng)
        before_rng = rng.getstate()
        ST.update(capturing=True, pool=None, selected=None)
        try:
            output, pending = real_predict(ai, state, config, rng)
        finally:
            ST["capturing"] = False
        after_rng = rng.getstate()
        pool, selected = ST["pool"] or (), ST["selected"]
        rows = candidates(pool, ai.target_graph_partial, state, config, before_rng)
        chosen = selected[2].name if selected is not None else None
        for row in rows:
            row["selected"] = row["R"] == chosen
            if row["selected"]:
                expected = row["prediction"] or {"abstain_reason": row["abstain_reason"]}
                if expected != prediction_key(output.prediction):
                    raise RuntimeError(f"走行中の候補記録：試行{smereplay.ST['trial']}の選ばれた答えが本物と違う")
        if check:
            reverse = candidates(tuple(reversed(pool)), ai.target_graph_partial, state, config, before_rng)
            forward = [{k: v for k, v in r.items() if k != "selected"} for r in rows]
            if forward != list(reversed(reverse)):
                raise RuntimeError("候補の記録が調べる順に依存する")
            if forward != candidates(pool, ai.target_graph_partial, state, config, before_rng):
                raise RuntimeError("候補の記録が二回で一致しない")
        if rng.getstate() != after_rng:
            raise RuntimeError("候補の記録が模型の乱数を変えた")
        trial = smereplay.ST["trial"]
        ST["pending"][trial] = dict(trial=trial, chosen_R=chosen, prediction=prediction_key(output.prediction),
                                   candidates=rows, candidate_policy="actual-prediction-mappings-v1")
        return output, pending

    loop.predict = predict
    real_record = loop._ledger_record

    def record(agent_id, trial, config, output, score, coin, state, *a, **kw):
        row = finish_row(ST["pending"].pop(trial.trial), trial.held_out_edge, score.hit)
        ST["f"].write(json.dumps(row, ensure_ascii=False) + "\n")
        ST["rows"] += 1
        return real_record(agent_id, trial, config, output, score, coin, state, *a, **kw)

    loop._ledger_record = record


def close():
    if ST["pending"]:
        raise RuntimeError("予測後に研究者の記録が閉じていない試行がある")
    ST["f"].close()
    return {"rows": ST["rows"]}
