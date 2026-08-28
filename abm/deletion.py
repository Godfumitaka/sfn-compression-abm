"""SPEC B1 §C.6.3 の theta-prime による唯一の削除経路。"""

from __future__ import annotations

from dataclasses import replace

from abm.accounting import constituent_value, survives
from abm.definition import ExceptionAccumulator, NamedDefinition
from abm.domains import AgentConfig, AgentState, Prototype


def apply_theta(state: AgentState, config: AgentConfig, trial: int) -> tuple[AgentState, tuple[dict[str, object], ...]]:
    definitions = dict(state.definitions)
    events: list[dict[str, object]] = []
    for name, definition in sorted(state.definitions.items()):
        rows = []
        for constituent in definition.constituents:
            if not constituent.alive:
                rows.append(constituent)
                continue
            key = (name, constituent.slot_index, constituent.registered_at)
            exception_key = (name, constituent.slot_index)
            accumulator = state.merit.get(key)
            embed = state.embed.get(key)
            if accumulator is None or embed is None:
                rows.append(constituent)
                continue
            value = constituent_value(
                constituent.frozen_price,
                accumulator,
                state.exceptions.get(exception_key, ExceptionAccumulator((0.0,) * 16, 0.0, 0)),
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
            definition.assimilation_count,
        )
    prototype = state.prototype
    if prototype.traces:
        surviving = prototype.alive(trial, config.theta_prime)
        expired = tuple(trace for trace in prototype.traces if trace not in surviving)
        for trace in expired:
            events.append({
                "kind": "verbatim_deletion",
                "graph_id": trace.scene.graph_id,
                "written_at": trace.written_at,
                "trial": trial,
                "sigma": trace.sigma(trial),
            })
        prototype = Prototype(surviving)
    return replace(
        state,
        definitions=definitions,
        prototype=prototype,
    ), tuple(events)
