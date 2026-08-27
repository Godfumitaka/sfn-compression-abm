"""SPEC B1 §C.4〜C.6 の採点と会計。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, log2
from typing import Iterable

from abm.definition import (
    EmbedState,
    FrequencyTable,
    FrozenPrice,
    MeritAccumulator,
)
from abm.domains import Abstain, AgentOutput, EdgePrediction, Relation


@dataclass(frozen=True, slots=True)
class OracleScore:
    outcome_category: str
    hit: bool
    cost_bits: float


def freeze_price(
    p_hat: FrequencyTable,
    relation: Relation,
    new_slot_count: int,
    m_alloc: int,
) -> FrozenPrice:
    ell = p_hat.code_length(relation.predicate)
    arity = len(relation.arguments)
    c = 1 + 3 * arity - 3 * new_slot_count
    return FrozenPrice(ell, c, ell + 1 + 3 * arity, m_alloc)


def exception_cost(m_live: int, ell_r: float) -> float:
    if m_live <= 0:
        raise ValueError("m_live は正である必要がある")
    return 2.0 + log2(m_live) + ell_r


def update_frequency(table: FrequencyTable, relations: Iterable[Relation]) -> FrequencyTable:
    """場面または開示辺に書かれた述語だけを加算する。"""

    counts = dict(table.counts)
    added = 0
    for relation in relations:
        counts[relation.predicate] = counts.get(relation.predicate, 0) + 1
        added += 1
    return FrequencyTable(counts, table.total + added, table.lambda_mix, frozenset(counts))


def decay_ladder(horizon: int) -> tuple[float, ...]:
    """U-001: tau in geomspace(0.3, T*3, 16)。走行長に合わせて 16 本の時定数を返す。"""

    return tuple(
        exp(-1.0 / (0.3 * ((max(horizon * 3, 0.3) / 0.3) ** (index / 15))))
        for index in range(16)
    )


def initial_merit(
    slot_index: int,
    registered_at: int,
    base_age: int,
    horizon: int,
) -> MeritAccumulator:
    ladder = decay_ladder(horizon)
    seed = tuple(factor ** max(base_age, 0) + 1.0 for factor in ladder)
    return MeritAccumulator(slot_index, registered_at, seed, seed, 2.0, 0)


def update_merit(
    accumulator: MeritAccumulator,
    decay: Iterable[float],
    *,
    matched: bool,
    filled_scored: bool,
    alpha: float,
    applied: bool,
    external_use: bool = False,
) -> MeritAccumulator:
    """照合と採点済み充填の二チャネルを一試行一回だけ加算する。"""

    increment = (1.0 if matched else alpha if filled_scored else 0.0) if applied else 0.0
    factors = tuple(float(value) for value in decay)
    if len(factors) != len(accumulator.basis):
        raise ValueError("減衰係数と基底の本数が異なる")
    basis = tuple(old * factor + increment for old, factor in zip(accumulator.basis, factors))
    opportunity_basis = tuple(
        old * factor + float(applied)
        for old, factor in zip(accumulator.opportunity_basis, factors)
    )
    return replace(
        accumulator,
        basis=basis,
        opportunity_basis=opportunity_basis,
        use_count=accumulator.use_count + increment,
        ext_use_count=accumulator.ext_use_count + int(external_use),
    )


def participation(accumulator: MeritAccumulator) -> float:
    denominator = sum(accumulator.opportunity_basis)
    if denominator <= 0.0:
        return 0.0
    return sum(accumulator.basis) / denominator


def embed_value(embed: EmbedState, kappa: float) -> float:
    fan_in = 0.0 if embed.fan_in_raw <= 0 else kappa * embed.fan_in_raw / (kappa + embed.fan_in_raw)
    return embed.fan_out + fan_in


def constituent_value(
    price: FrozenPrice,
    accumulator: MeritAccumulator,
    embed: EmbedState,
    *,
    w: float,
    kappa: float,
) -> float:
    return participation(accumulator) * price.a0 + w * embed_value(embed, kappa) / price.ell_frozen


def survives(value: float, theta_prime: float) -> bool:
    """削除の唯一の判定を表裏のない関数として保つ。"""

    return value >= theta_prime


def score_prediction(output: AgentOutput, held_out: Relation, vocabulary_size: int) -> OracleScore:
    """O1: 伏せ辺一本だけを研究者側で採点する。"""

    cost = log2(max(vocabulary_size, 1))
    prediction = output.prediction
    if isinstance(prediction, Abstain):
        return OracleScore("保留", False, cost)
    if isinstance(prediction, EdgePrediction):
        hit = (
            prediction.edge.predicate == held_out.predicate
            and prediction.edge.arguments == held_out.arguments
        )
        return OracleScore("的中" if hit else "失敗", hit, cost)
    return OracleScore("未解決", False, cost)
