"""SPEC B1 §C.6.3 の theta-prime による唯一の削除経路。"""

from __future__ import annotations

from dataclasses import replace

from abm.accounting import constituent_value, survives
from abm.definition import NamedDefinition
from abm.domains import AgentConfig, AgentState, RelationGraph, VerbatimClock


def apply_theta(state: AgentState, config: AgentConfig, trial: int) -> tuple[AgentState, tuple[dict[str, object], ...]]:
    definitions = dict(state.definitions)
    events: list[dict[str, object]] = []
    for name, definition in sorted(state.definitions.items()):
        rows = []
        for constituent in definition.constituents:
            if not constituent.alive:
                rows.append(constituent)
                continue
            key = (name, constituent.slot_index)
            accumulator = state.merit.get(key)
            embed = state.embed.get(key)
            if accumulator is None or embed is None:
                rows.append(constituent)
                continue
            value = constituent_value(
                constituent.frozen_price,
                accumulator,
                embed,
                w=config.w,
                kappa=config.kappa,
            )
            if survives(value, config.theta_prime):
                rows.append(constituent)
                continue
            rows.append(replace(constituent, alive=False))
            events.append({
                "kind": "deletion",
                "R": name,
                "slot_index": constituent.slot_index,
                "registered_at": constituent.registered_at,
                "trial": trial,
                "V": value,
            })
        definitions[name] = NamedDefinition(
            definition.name,
            tuple(rows),
            definition.m_alloc,
            definition.registered_at,
        )
    prototype = state.prototype
    clock = state.verbatim_clock
    if prototype is not None:
        surviving = clock.surviving(trial, config.theta_prime)
        expired = set(clock.written_at) - surviving
        for relation_id in sorted(expired):
            events.append({
                "kind": "verbatim_deletion",
                "relation_id": relation_id,
                "trial": trial,
                "sigma": clock.sigma(relation_id, trial),
            })
        prototype = RelationGraph(
            prototype.graph_id,
            prototype.entities,
            tuple(relation for relation in prototype.relations if relation.relation_id in surviving),
        )
        clock = VerbatimClock({key: value for key, value in clock.written_at.items() if key in surviving})
    return replace(
        state,
        definitions=definitions,
        prototype=prototype,
        verbatim_clock=clock,
    ), tuple(events)
