"""SPEC B1 §C.8 の predict -> oracle -> update 縦断ループ。"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
from math import exp
import json
from random import Random
from typing import Any, Callable, Mapping, Protocol

from abm.abstraction import m1
from abm.accounting import score_prediction, update_merit
from abm.agent_runtime import predict, update
from abm.deletion import apply_theta
from abm.domains import (
    Abstain,
    AgentConfig,
    AgentState,
    EdgePrediction,
    RevealedEdge,
)
from abm.feedback import FeedbackFrequency, evaluate_feedback_coin, f
from abm.ledger import LEDGER_FIELDS, Ledger, empty_record
from abm.world import WorldSequence


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
) -> LoopResult:
    """共通世界列を順方向に一度だけ走査する。"""

    current = dict(states)
    for trial in world.trials:
        for agent_id in sorted(current):
            config = configs[agent_id]
            before = current[agent_id]
            agent_input = _agent_input(trial, before)
            output, pending = predict(agent_input, before, config, Random(_rng_seed(agent_id, trial.trial)))
            score = score_prediction(output, trial.held_out_edge, len(before.p_hat.alive_vocab))
            coin = evaluate_feedback_coin(agent_id, trial.trial, trial.u_coins[agent_id], frequency)
            feedback = RevealedEdge(trial.held_out_edge) if coin.f_fired else None
            after = update(pending, feedback)
            after = _update_merit(after, output, agent_input.target_graph_partial, config, len(world.trials))

            registration = None
            used_name = output.trace.get("R_identified")
            definition_alignment = output.trace.get("definition_alignment")
            if used_name is not None and definition_alignment is not None:
                definition = after.definitions[str(used_name)]
                after, registration = m1(
                    after,
                    _definition_graph(definition),
                    agent_input.target_graph_partial,
                    definition_alignment,
                    trial.trial,
                    name=str(used_name),
                )
            elif before.prototype is not None:
                after, registration = m1(
                    after,
                    before.prototype,
                    agent_input.target_graph_partial,
                    output.trace["alignment"],
                    trial.trial,
                )
            after, deletion_events = apply_theta(after, config, trial.trial)
            current[agent_id] = after
            ledger.append(_ledger_record(
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
            ))
    return LoopResult(dict(sorted(current.items())), world.world_hash, len(world.trials))


def _update_merit(
    state: AgentState,
    output: Any,
    scene: Any,
    config: AgentConfig,
    horizon: int,
) -> AgentState:
    """U3〜U5: 可視場面での述語充足を全生存行へ一度だけ反映する。"""

    from dataclasses import replace

    merit = dict(state.merit)
    visible_predicates = {relation.predicate for relation in scene.relations}
    filled = {relation.predicate for relation in output.trace.get("filled_slots", ())}
    decay = tuple(
        exp(-1.0 / (0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (index / 15))))
        for index in range(16)
    )
    for name, definition in state.definitions.items():
        for row in definition.constituents:
            if not row.alive:
                continue
            key = (name, row.slot_index)
            accumulator = merit.get(key)
            if accumulator is None:
                continue
            merit[key] = update_merit(
                accumulator,
                decay,
                matched=row.relation.predicate in visible_predicates,
                filled_scored=row.relation.predicate in filled,
                alpha=config.alpha,
            )
    return replace(state, merit=merit)


def _agent_input(trial: Any, state: AgentState):
    from abm.domains import AgentInput, RelationGraph

    base = state.prototype or trial.target_graph_partial
    return AgentInput(base, trial.target_graph_partial, tuple(r.relation_id for r in trial.target_graph_partial.relations))


def _definition_graph(definition: Any):
    from abm.domains import Entity, RelationGraph

    relation_ids = {row.relation.relation_id for row in definition.constituents}
    entity_ids = sorted({
        argument
        for row in definition.constituents
        for argument in row.relation.arguments
        if argument not in relation_ids
    })
    return RelationGraph(
        graph_id=f"definition:{definition.name}",
        entities=tuple(Entity(entity_id) for entity_id in entity_ids),
        relations=tuple(row.relation for row in definition.constituents),
    )


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
) -> dict[str, Any]:
    prediction = output.prediction
    abstain_reason = prediction.reason if isinstance(prediction, Abstain) else None
    predicted = prediction.edge.to_dict() if isinstance(prediction, EdgePrediction) else None
    definitions = tuple(state.definitions.values())
    m_alloc = sum(definition.m_alloc for definition in definitions)
    m_live = sum(definition.m_live for definition in definitions)
    support = int(output.trace.get("support_at_adoption", 0))
    snapshot = _canonical(state)
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
        "coin_t": coin.coin_t,
        "f_realized": coin.f_realized,
        "f_fired": coin.f_fired,
        "feedback_content": trial.held_out_edge.to_dict() if coin.f_fired else None,
        "held_out_content": trial.held_out_edge.to_dict(),
        "oracle_verdict": score.outcome_category,
        "registration_event": registration,
        "deletion_event": list(deletions),
        "R_used": output.trace.get("R_used"),
        "def_R_diff": registration,
        "agent_state_snapshot_hash": sha256(_json_bytes(snapshot)).hexdigest(),
        "state_snapshot": snapshot,
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
        "exception_bits_charged": 0.0,
        "M051_balance": state.exceptions.bits,
        "matcher": "sme",
        "n_tie_candidates": 0,
        "candidate_distribution": [],
        "enumeration_version": "B1-v0",
        "V_vocab": len(state.p_hat.alive_vocab),
        "merit_event_times": [],
        "outcome_category": score.outcome_category,
        "constituent_reason_123": {},
        "world_hash": world_hash,
    }
    return empty_record(**{key: value for key, value in required.items() if key in LEDGER_FIELDS})


def _constituent_states(state: AgentState) -> list[dict[str, Any]]:
    result = []
    for name, definition in sorted(state.definitions.items()):
        for row in definition.constituents:
            merit = state.merit.get((name, row.slot_index))
            embed = state.embed.get((name, row.slot_index))
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
    if is_dataclass(value):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list, frozenset, set)):
        return [_canonical(item) for item in sorted(value, key=repr) if item is not None]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _rng_seed(agent_id: str, trial: int) -> int:
    return int.from_bytes(sha256(f"{agent_id}\x1f{trial}\x1fagent".encode()).digest(), "big")
