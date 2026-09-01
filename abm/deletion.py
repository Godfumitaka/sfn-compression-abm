"""SPEC B1 §C.6.3 の theta-prime による唯一の削除経路。"""

from __future__ import annotations

from dataclasses import replace

from abm.accounting import constituent_value_terms, decay_ladder, survives
from abm.definition import ExceptionAccumulator, NamedDefinition
from abm.domains import AgentConfig, AgentState, Prototype


def apply_theta(
    state: AgentState,
    config: AgentConfig,
    trial: int,
    *,
    horizon: int | None = None,
) -> tuple[AgentState, tuple[dict[str, object], ...]]:
    definitions = dict(state.definitions)
    events: list[dict[str, object]] = []
    # ★ β の項は p_R・P_ext を要求し、両者は功績と同じ減衰梯子を使う（委任書 §4-5）。
    if config.beta and horizon is None:
        raise ValueError("β≠0 の削除判定には走行長（horizon）が要る")
    decay = decay_ladder(horizon) if config.beta else None
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
            terms = constituent_value_terms(
                constituent.frozen_price,
                accumulator,
                state.exceptions.get(exception_key, ExceptionAccumulator((0.0,) * 16, 0.0, 0)),
                embed,
                w=config.w,
                kappa=config.kappa,
                beta=config.beta,
                decay=decay,
                elapsed=trial - constituent.registered_at,
            )
            value = terms.total
            if survives(value, config.theta_prime):
                rows.append(constituent)
                continue
            rows.append(replace(constituent, alive=False))
            event: dict[str, object] = {
                "kind": "deletion",
                "R": name,
                "slot_index": constituent.slot_index,
                "registered_at": constituent.registered_at,
                "trial": trial,
                "V": value,
            }
            if config.beta:
                # D23 の V 成分。★ β の項が四つ目になる（θ′ は台帳の別欄）。
                # ★ β=0 では欄を足さない。既存 4,322 走行と台帳バイト列を一致させるため。
                event["V_participation"] = terms.participation_term
                event["V_beta"] = terms.beta_term
                event["V_embed"] = terms.embed_term
            events.append(event)
        definitions[name] = NamedDefinition(
            definition.name,
            tuple(rows),
            definition.m_alloc,
            definition.registered_at,
            definition.assimilation_count,
        )
    prototype = state.prototype
    if prototype.traces:
        surviving = prototype.alive(trial, config.verbatim_threshold)
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
