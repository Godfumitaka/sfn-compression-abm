"""SPEC B1 §C.8 の predict -> oracle -> update 縦断ループ。"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from hashlib import sha256
import json
from random import Random
from typing import Any, Callable, Mapping, Protocol

from abm.abstraction import _identify_definition, m1
from abm.accounting import decay_ladder, exception_cost, score_prediction, update_merit
from abm.definition import ExceptionAccumulator
from abm.agent_runtime import _definition_graph, predict, update
from abm.deletion import apply_theta
from abm.domains import (
    Abstain,
    AgentConfig,
    AgentState,
    EdgePrediction,
    RepairScope,
    RevealedEdge,
)
from abm.feedback import FeedbackFrequency, evaluate_feedback_coin, f
from abm.ledger import LEDGER_FIELDS, Ledger, empty_record
from abm.world import WorldSequence
from abm.sme import map_graphs, project
from abm.filling import _mapped_arguments, fill_missing_slots


_CANONICAL_CACHE: dict[int, Any] = {}
_CANONICAL_KEEP: list[Any] = []
_REPR_CACHE: dict[int, str] = {}
_DELETED = "__deleted__"


@dataclass(frozen=True, slots=True)
class LoopResult:
    states: Mapping[str, AgentState]
    world_hash: str
    trial_count: int


def run_longitudinal(
    world: WorldSequence,
    states: Mapping[str, AgentState],
    configs: Mapping[str, AgentConfig],
    ledger: Ledger,
    *,
    frequency: FeedbackFrequency = f,
    snapshot_mode: str = "delta",
    snapshot_every: int = 1,
    calculate_counterfactuals: bool = True,
) -> LoopResult:
    """共通世界列を順方向に一度だけ走査する。"""

    _CANONICAL_CACHE.clear()
    _CANONICAL_KEEP.clear()
    _REPR_CACHE.clear()
    if snapshot_mode not in {"delta", "full", "hash_only"}:
        raise ValueError(f"未知の snapshot_mode: {snapshot_mode}")
    if snapshot_every < 1:
        raise ValueError("snapshot_every は 1 以上でなければなりません")
    if snapshot_mode != "delta" and snapshot_every != 1:
        raise ValueError("snapshot_every は snapshot_mode='delta' でのみ指定できます")
    current = dict(states)
    previous_snapshots: dict[str, Any] = {}
    previous_hashes: dict[str, str] = {}
    self_score_caches: dict[str, dict[str, float]] = {
        agent_id: {} for agent_id in current
    }
    for trial in world.trials:
        for agent_id in sorted(current):
            config = configs[agent_id]
            before = current[agent_id]
            agent_input = _agent_input(trial, before)
            output, pending = predict(agent_input, before, config, Random(_rng_seed(agent_id, trial.trial)))
            counterfactuals = (_counterfactual_predictions(before, agent_input.target_graph_partial, output, trial.held_out_edge)
                               if calculate_counterfactuals else [])
            verbatim_baseline = _verbatim_baseline(output, agent_input.target_graph_partial)
            score = score_prediction(output, trial.held_out_edge, len(before.p_hat.alive_vocab))
            coin = evaluate_feedback_coin(agent_id, trial.trial, trial.u_coins[agent_id], frequency)
            feedback = RevealedEdge(trial.held_out_edge) if coin.f_fired else None
            after = update(pending, feedback)
            after, accounting = _update_accounting(
                after, output, agent_input.target_graph_partial, config,
                len(world.trials), score, coin, trial.held_out_edge,
            )

            registration = None
            if output.trace.get("selected_scene") is not None:
                identified = _identify_definition(
                    after,
                    agent_input.target_graph_partial,
                    config.nsim_threshold,
                    self_score_caches[agent_id],
                )
                after, registration = m1(
                    after,
                    output.trace["selected_scene"],
                    agent_input.target_graph_partial,
                    output.trace["alignment"],
                    trial.trial,
                    name=identified,
                    base_written_at=output.trace["selected_scene_written_at"],
                    horizon=len(world.trials),
                )
            after, deletion_events = apply_theta(after, config, trial.trial)
            current[agent_id] = after
            capture_snapshot = (
                snapshot_mode == "delta"
                and (
                    agent_id not in previous_snapshots
                    or trial.trial % snapshot_every == 0
                    or trial.trial == len(world.trials) - 1
                )
            )
            record, snapshot, snapshot_hash = _ledger_record(
                agent_id,
                trial,
                config,
                output,
                score,
                coin,
                after,
                registration,
                deletion_events,
                world.world_hash,
                verbatim_baseline,
                accounting,
                snapshot_mode, previous_snapshots.get(agent_id), previous_hashes.get(agent_id),
                capture_snapshot, counterfactuals,
            )
            ledger.append(record)
            if capture_snapshot:
                previous_snapshots[agent_id] = snapshot
                previous_hashes[agent_id] = snapshot_hash
    return LoopResult(dict(sorted(current.items())), world.world_hash, len(world.trials))


def classify_row(row: Any, scene: Any, entity_mapping: Mapping[str, str], relation_mapping: Mapping[str, str]) -> str:
    """rev6 §C.5.2b の四値分類を一箇所で行う。"""

    position = _mapped_arguments(row.relation, entity_mapping, relation_mapping)
    if position is None:
        return "判定不能"
    visible_content = {(relation.predicate, relation.arguments) for relation in scene.relations}
    if (row.relation.predicate, position) in visible_content:
        return "充足"
    if position in {relation.arguments for relation in scene.relations}:
        return "②"
    return "③"


def _update_accounting(
    state: AgentState,
    output: Any,
    scene: Any,
    config: AgentConfig,
    horizon: int,
    score: Any,
    coin: Any,
    revealed_edge: Any,
) -> tuple[AgentState, dict[str, Any]]:
    """功績と例外費用を同じ減衰梯子で一試行ぶん更新する。"""

    merit = dict(state.merit)
    exceptions = dict(state.exceptions)
    filled = {relation.predicate for relation in output.trace.get("filled_slots", ())}
    decay = decay_ladder(horizon)
    used_name = output.trace.get("R_used")
    alignment = output.trace.get("definition_alignment")
    reasons: dict[str, dict[int, str]] = {}
    sources: dict[str, list[Any]] = {"①": [], "②": [], "衝突": []}
    charged_total = 0.0

    # R が適用されない行も、蓄積した例外費用の減衰だけは進む。
    for key, accumulator in exceptions.items():
        exceptions[key] = replace(
            accumulator,
            basis=tuple(old * factor for old, factor in zip(accumulator.basis, decay)),
        )

    for name, definition in state.definitions.items():
        for row in definition.constituents:
            if not row.alive:
                continue
            key = (name, row.slot_index, row.registered_at)
            accumulator = merit.get(key)
            if accumulator is None:
                continue
            applied = used_name == name
            reason = None
            if applied and alignment is not None:
                reason = classify_row(row, scene, alignment.entity_mapping, alignment.relation_mapping)
                reasons.setdefault(name, {})[row.slot_index] = reason
            merit[key] = update_merit(
                accumulator,
                decay,
                matched=reason == "充足",
                filled_scored=row.relation.predicate in filled,
                alpha=config.alpha,
                applied=applied,
            )
            if reason == "②":
                position = _mapped_arguments(row.relation, alignment.entity_mapping, alignment.relation_mapping)
                candidates = [relation for relation in scene.relations if relation.arguments == position]
                lengths = [state.p_hat.code_length(relation.predicate) for relation in candidates]
                ell_r = sum(lengths) / len(lengths)
                cost = exception_cost(definition.m_live, ell_r)
                exception_key = (name, row.slot_index)
                exceptions[exception_key] = _charge(exceptions[exception_key], cost)
                charged_total += cost
                sources["②"].append((name, row.slot_index))
                if len(candidates) >= 2:
                    sources["衝突"].append({
                        "R": name, "slot_index": row.slot_index,
                        "候補": [relation.predicate for relation in candidates], "符号長": lengths,
                        "最短": min(lengths), "平均": ell_r, "合計": sum(lengths),
                    })

    # ①は非棄権の誤答が開示された試行だけに立つ。
    if used_name is not None and alignment is not None and not isinstance(output.prediction, Abstain) and not score.hit and coin.f_fired:
        definition = state.definitions[used_name]
        base_ids = {
            row.relation.relation_id for row in definition.constituents
            if row.alive and row.relation.relation_id in alignment.relation_mapping
        }
        charged_ids = _repair_targets(definition, base_ids, config.repair_scope)
        cost = exception_cost(definition.m_live, state.p_hat.code_length(revealed_edge.predicate))
        for row in definition.constituents:
            if row.alive and row.relation.relation_id in charged_ids:
                exception_key = (used_name, row.slot_index)
                exceptions[exception_key] = _charge(exceptions[exception_key], cost)
                charged_total += cost
                sources["①"].append(exception_key)

    next_state = replace(state, merit=merit, exceptions=exceptions)
    return next_state, {
        "constituent_reason_123": reasons,
        "charge_source": sources if sources["①"] or sources["②"] else None,
        "type2_fired": bool(sources["②"]),
        "exception_bits_charged": charged_total,
    }


def _charge(accumulator: ExceptionAccumulator, cost: float) -> ExceptionAccumulator:
    return replace(
        accumulator,
        basis=tuple(value + cost for value in accumulator.basis),
        bits=accumulator.bits + cost,
        event_count=accumulator.event_count + 1,
    )


def _repair_targets(definition: Any, base_ids: set[str], scope: RepairScope) -> set[str]:
    alive = [row for row in definition.constituents if row.alive]
    reached = set(base_ids)
    frontier = set(base_ids)
    depth = 1 if scope is RepairScope.FIRST_ORDER else 2 if scope is RepairScope.SECOND_ORDER else None
    steps = 0
    while frontier and (depth is None or steps < depth):
        parents = {
            row.relation.relation_id for row in alive
            if any(argument in frontier for argument in row.relation.arguments)
        } - reached
        reached.update(parents)
        frontier = parents
        steps += 1
    return reached


def _agent_input(trial: Any, state: AgentState):
    from abm.domains import AgentInput

    return AgentInput(trial.target_graph_partial, trial.target_graph_partial, tuple(r.relation_id for r in trial.target_graph_partial.relations))


def _verbatim_baseline(output: Any, target: Any) -> EdgePrediction | None:
    """採用した逐語枚の反実仮想予測を研究者側で再構成する。"""

    base = output.trace.get("selected_scene")
    alignment = output.trace.get("alignment")
    if base is None or alignment is None:
        return None
    prediction = project(alignment, base, target, prototype_prior_weight=0.0)
    return prediction if isinstance(prediction, EdgePrediction) else None


def _counterfactual_predictions(state: AgentState, target: Any, output: Any, held_out: Any) -> list[dict[str, Any]]:
    results = []
    for item in output.trace.get("tau_passed_defs", []):
        if item["selected"]:
            continue
        definition = state.definitions[item["R"]]
        graph = _definition_graph(definition)
        alignment = map_graphs(graph, target).alignment
        prediction = project(alignment, graph, target, prototype_prior_weight=0.0)
        filling = fill_missing_slots(definition, target, alignment.entity_mapping, alignment.relation_mapping,
                                     state.slot_history, state.p_hat)
        if filling.ambiguous:
            prediction = Abstain(reason="ambiguous_projection")
        elif isinstance(prediction, Abstain) and filling.relations:
            prediction = EdgePrediction(filling.relations[0])
        elif isinstance(prediction, Abstain):
            prediction = Abstain(reason="no_projectable_relation")
        edge = prediction.edge if isinstance(prediction, EdgePrediction) else None
        results.append({"R": definition.name, "predicted_edge": edge.to_dict() if edge else None,
                        "hit": int(edge is not None and edge.predicate == held_out.predicate and edge.arguments == held_out.arguments),
                        "abstain_reason": prediction.reason if isinstance(prediction, Abstain) else None})
    return results


def _ledger_record(
    agent_id: str,
    trial: Any,
    config: AgentConfig,
    output: Any,
    score: Any,
    coin: Any,
    state: AgentState,
    registration: Any,
    deletions: tuple[dict[str, object], ...],
    world_hash: str,
    verbatim_baseline: EdgePrediction | None,
    accounting: Mapping[str, Any],
    snapshot_mode: str, previous_snapshot: Any, previous_hash: str | None,
    capture_snapshot: bool,
    counterfactuals: list[dict[str, Any]],
) -> tuple[dict[str, Any], Any, str]:
    prediction = output.prediction
    abstain_reason = prediction.reason if isinstance(prediction, Abstain) else None
    predicted = prediction.edge.to_dict() if isinstance(prediction, EdgePrediction) else None
    definitions = tuple(state.definitions.values())
    m_alloc = sum(definition.m_alloc for definition in definitions)
    m_live = sum(definition.m_live for definition in definitions)
    support = int(output.trace.get("support_at_adoption", 0))
    snapshot = _canonical(state)
    snapshot_hash = sha256(_json_bytes(snapshot)).hexdigest()
    if snapshot_mode == "hash_only":
        stored_snapshot = None
    elif snapshot_mode == "full" or previous_snapshot is None:
        stored_snapshot = {"kind": "full", "value": snapshot}
    elif not capture_snapshot:
        stored_snapshot = {"kind": "skipped", "base_hash": previous_hash}
    else:
        stored_snapshot = {"kind": "delta", "base_hash": previous_hash,
                           "changes": _diff(previous_snapshot, snapshot) or {}}
    required = {
        "run_id": world_hash,
        "agent_id": agent_id,
        "prediction_order": trial.trial,
        "instance_id": trial.G_star.graph_id,
        "observable_mask_edges": [r.relation_id for r in trial.target_graph_partial.relations],
        "prediction_kind": type(prediction).__name__,
        "predicted_edge": predicted,
        "abstain_reason": abstain_reason,
        "hit": int(score.hit),
        "coverage": int(not isinstance(prediction, Abstain)),
        "accuracy": float(score.hit),
        "verbatim_baseline_prediction": (
            verbatim_baseline.edge.to_dict() if verbatim_baseline is not None else None
        ),
        "verbatim_baseline_hit": int(
            verbatim_baseline is not None
            and verbatim_baseline.edge.predicate == trial.held_out_edge.predicate
            and verbatim_baseline.edge.arguments == trial.held_out_edge.arguments
        ),
        "counterfactual_predictions": counterfactuals,
        "coin_t": coin.coin_t,
        "f_realized": coin.f_realized,
        "f_fired": coin.f_fired,
        "feedback_content": trial.held_out_edge.to_dict() if coin.f_fired else None,
        "held_out_content": trial.held_out_edge.to_dict(),
        "oracle_verdict": score.outcome_category,
        "registration_event": registration,
        "deletion_event": list(deletions),
        "tie_event": bool(output.trace.get("tie_event", False)),
        "R_used": output.trace.get("R_used"),
        "def_R_diff": registration,
        "agent_state_snapshot_hash": snapshot_hash,
        "state_snapshot": stored_snapshot,
        "scene_G_star_ref": trial.G_star.graph_id,
        "m_alloc": m_alloc,
        "m_live": m_live,
        "theta_prime": config.theta_prime,
        "tau": config.tau_acc,
        "constituent_states": _constituent_states(state),
        "entity_map_covered": bool(output.trace.get("entity_map_covered", False)),
        "slot_history_size": sum(len(values) for values in state.slot_history.values()),
        "filled_predicate": [r.predicate for r in output.trace.get("filled_slots", ())],
        "slot_signature": [list(r.arguments) for r in output.trace.get("filled_slots", ())],
        "support_at_adoption": support,
        "verbatim_written": True,
        "reg_del_events": [event for event in (registration, *deletions) if event is not None],
        "exception_bits_charged": accounting["exception_bits_charged"],
        "M051_balance": sum(value.bits for value in state.exceptions.values()),
        "matcher": "sme",
        "n_tie_candidates": 0,
        "candidate_distribution": [],
        "enumeration_version": "B1-v0",
        "V_vocab": len(state.p_hat.alive_vocab),
        "merit_event_times": [],
        "outcome_category": score.outcome_category,
        "tau_passed_defs": output.trace.get("tau_passed_defs", []),
        "constituent_reason_123": accounting["constituent_reason_123"],
        "charge_source": accounting["charge_source"],
        "type2_fired": accounting["type2_fired"],
        "arm_repair_scope": config.repair_scope.value,
        "world_hash": world_hash,
    }
    return empty_record(**{key: value for key, value in required.items() if key in LEDGER_FIELDS}), snapshot, snapshot_hash


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _diff(old: object, new: object) -> object | None:
    if isinstance(old, dict) and isinstance(new, dict):
        out = {}
        for key in new:
            if key not in old:
                out[key] = {"set": new[key]}
            else:
                difference = _diff(old[key], new[key])
                if difference is not None:
                    out[key] = difference
        for key in old:
            if key not in new:
                out[key] = _DELETED
        return out or None
    if isinstance(old, list) and isinstance(new, list):
        from collections import Counter
        old_keys, new_keys = [_key(x) for x in old], [_key(x) for x in new]
        if old_keys == new_keys:
            return None
        old_counts, new_counts = Counter(old_keys), Counter(new_keys)
        needed = new_counts - old_counts
        insertions = []
        for index, key in enumerate(new_keys):
            if needed[key] > 0:
                insertions.append([index, new[index]]); needed[key] -= 1
        needed = old_counts - new_counts
        deletions = []
        for index, key in enumerate(old_keys):
            if needed[key] > 0:
                deletions.append(index); needed[key] -= 1
        current = list(old)
        for index in sorted(deletions, reverse=True): current.pop(index)
        for index, value in insertions: current.insert(index, value)
        if [_key(x) for x in current] != new_keys:
            return {"set": new}
        return {"ld": {"d": deletions, "i": insertions}}
    if old == new:
        return None
    return {"set": new}


def _apply(old: object, delta: object) -> object:
    if delta is None: return old
    if isinstance(delta, dict) and set(delta) == {"set"}: return delta["set"]
    if isinstance(delta, dict) and set(delta) == {"ld"}:
        current = list(old)
        for index in sorted(delta["ld"]["d"], reverse=True): current.pop(index)
        for index, value in delta["ld"]["i"]: current.insert(index, value)
        return current
    out = dict(old) if isinstance(old, dict) else {}
    for key, value in delta.items():
        if value == _DELETED: out.pop(key, None)
        else: out[key] = _apply(out.get(key), value)
    return out


def _constituent_states(state: AgentState) -> list[dict[str, Any]]:
    result = []
    for name, definition in sorted(state.definitions.items()):
        for row in definition.constituents:
            key = (name, row.slot_index, row.registered_at)
            merit = state.merit.get(key)
            embed = state.embed.get(key)
            result.append({
                "R": name,
                "slot_index": row.slot_index,
                "registered_at": row.registered_at,
                "alive": row.alive,
                "S_q": merit.use_count if merit else 0.0,
                "ext_use_count": merit.ext_use_count if merit else 0,
                "embed": _canonical(embed),
            })
    return result


def _canonical(value: Any) -> Any:
    if is_dataclass(value) or isinstance(value, (tuple, frozenset)):
        key = id(value)
        if key in _CANONICAL_CACHE:
            return _CANONICAL_CACHE[key]
        result = _canonical_build(value)
        _CANONICAL_CACHE[key] = result
        _CANONICAL_KEEP.append(value)
        return result
    return _canonical_build(value)


def _canonical_build(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list, frozenset, set)):
        return [_canonical(item) for item in sorted(value, key=_canonical_sort_key) if item is not None]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _canonical_sort_key(value: Any) -> str:
    """不変要素の repr を再利用し、既存の整列順を保つ。"""

    if is_dataclass(value) or isinstance(value, (tuple, frozenset)):
        key = id(value)
        cached = _REPR_CACHE.get(key)
        if cached is not None:
            return cached
        rendered = repr(value)
        _REPR_CACHE[key] = rendered
        return rendered
    return repr(value)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _rng_seed(agent_id: str, trial: int) -> int:
    return int.from_bytes(sha256(f"{agent_id}\x1f{trial}\x1fagent".encode()).digest(), "big")
