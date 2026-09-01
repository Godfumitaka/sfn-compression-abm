"""SPEC B1 §C.4〜C.6 の採点と会計。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from math import exp, log2
from typing import Iterable

from abm.definition import (
    EmbedState,
    ExceptionAccumulator,
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


@dataclass(frozen=True, slots=True)
class ValueTerms:
    """U-09n の V を三項に分けて持つ。D23 が削除イベントに残せと言う成分。"""

    participation_term: float   # P_q·a_q
    beta_term: float            # β·((1−p_R)/p_R)·P_ext,q·a_q
    embed_term: float           # w·(embed_q/ℓ_q)
    total: float                # V_q


# initial_merit の D-cold 種 φ^base_age + 1.0 の上限（base_age = 0 のとき 2.0）。
# ★ p_R の分母はこの上限で事前分を置く。理由は total_opportunity の docstring。
D_COLD_MAX_PRIOR = 2.0


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
    pending_increment: float = 0.0,
) -> MeritAccumulator:
    """照合と採点済み充填の二チャネルを一試行一回だけ加算する。"""

    increment = (1.0 if matched else alpha if filled_scored else 0.0) if applied else 0.0
    factors = tuple(float(value) for value in decay)
    if len(factors) != len(accumulator.basis):
        raise ValueError("減衰係数と基底の本数が異なる")
    # 仕様 (E)：未決の主張が確認されたぶんは ★ 分子（basis）だけに乗せる（判断2・2026-09-02）。
    #   採択の有無を問わない経路なので opportunity_basis と use_count には加えない。P>1 は意図どおり。
    #   ★ 新しい減衰基底は作らず、既存の basis と同じ梯子・同じ順序（減衰してから加算）で貯める。
    basis = tuple(
        old * factor + increment + pending_increment
        for old, factor in zip(accumulator.basis, factors)
    )
    opportunity_basis = tuple(
        old * factor + float(applied)
        for old, factor in zip(accumulator.opportunity_basis, factors)
    )
    # M-018 の R 外使用。★ P・p_R と同じ梯子で、同じ順序（減衰してから加算）で貯める。
    # ★ 一度も立たないうちは () のままにする。零の減衰は零なので値は変わらない。
    ext_basis = accumulator.ext_basis
    if external_use or ext_basis:
        if not ext_basis:
            ext_basis = (0.0,) * len(factors)
        ext_basis = tuple(
            old * factor + float(external_use) for old, factor in zip(ext_basis, factors)
        )
    return replace(
        accumulator,
        basis=basis,
        opportunity_basis=opportunity_basis,
        use_count=accumulator.use_count + increment,
        ext_use_count=accumulator.ext_use_count + int(external_use),
        ext_basis=ext_basis,
    )


def participation(accumulator: MeritAccumulator) -> float:
    denominator = sum(accumulator.opportunity_basis)
    if denominator <= 0.0:
        return 0.0
    return sum(accumulator.basis) / denominator


@lru_cache(maxsize=8192)
def total_opportunity(decay: tuple[float, ...], elapsed: int) -> tuple[float, ...]:
    """全試行の σ加重和を基底ごとに閉形式で置く（新しい状態は持たない）。

    opportunity_basis は基底 φ ごとに seed·φ^t + Σ_{k<t} applied_k·φ^k で進む。
    全試行は applied を常に 1 とした同じ漸化式なので Σ_{k<t} φ^k = (1−φ^t)/(1−φ)。
    ★ 事前分は D-cold の種 seed = φ^base_age + 1.0 と同じ位置に置く。base_age は
      状態に持たないため上限の 2.0 を使う。seed ≤ 2.0 なので基底ごとに
      opportunity_basis ≤ total_opportunity が全ての t で成り立ち、
      ★ p_R が 1 を超えず、P_ext の分母（全試行 − R 適用）が負にならない。
    """

    if elapsed < 0:
        raise ValueError("経過試行数は 0 以上である必要がある")
    values = []
    for factor in decay:
        if not 0.0 <= factor < 1.0:
            raise ValueError(f"減衰係数は [0,1) である必要がある: {factor}")
        power = factor ** elapsed
        values.append(D_COLD_MAX_PRIOR * power + (1.0 - power) / (1.0 - factor))
    return tuple(values)


def adoption_rate(
    accumulator: MeritAccumulator, decay: tuple[float, ...], elapsed: int
) -> float:
    """p_R。★ その def 一本が R_used だった σ加重和 ÷ 全試行の σ加重和（M-069）。"""

    numerator = sum(accumulator.opportunity_basis)
    if not numerator > 0.0:
        # ★ 無言の epsilon は置かない（委任書 §2-4）。D-cold の種が消えていれば止める。
        raise ValueError(
            "生存 def の機会基底が正でない: "
            f"slot_index={accumulator.slot_index}, "
            f"registered_at={accumulator.registered_at}, elapsed={elapsed}"
        )
    return numerator / sum(total_opportunity(decay, elapsed))


def external_participation(
    accumulator: MeritAccumulator, decay: tuple[float, ...], elapsed: int
) -> float:
    """P_ext。分母は M-020 の「全試行 − R 適用」。分子は R 外使用の σ加重和。"""

    denominator = sum(total_opportunity(decay, elapsed)) - sum(accumulator.opportunity_basis)
    if denominator <= 0.0:
        # R 適用が全試行を埋めた場合。R 外の試行が無いので分子も必ず 0 である。
        return 0.0
    return sum(accumulator.ext_basis) / denominator


def embed_value(embed: EmbedState, kappa: float) -> float:
    fan_in = 0.0 if embed.fan_in_raw <= 0 else kappa * embed.fan_in_raw / (kappa + embed.fan_in_raw)
    return embed.fan_out + fan_in


def constituent_value_terms(
    price: FrozenPrice,
    accumulator: MeritAccumulator,
    exceptions: ExceptionAccumulator,
    embed: EmbedState,
    *,
    w: float,
    kappa: float,
    beta: float = 0.0,
    decay: tuple[float, ...] | None = None,
    elapsed: int | None = None,
) -> ValueTerms:
    """U-09n: V ＝ P·a ＋ β·((1−p_R)/p_R)·P_ext·a ＋ w·(embed/ℓ)。

    ★ 保持値は「R 適用あたり」の尺度なので、第一項に p_R は掛けない。
    ★ β=0 のときは β の項を一切足さない。旧式と浮動小数点まで同一に保つため。
    """

    denominator = sum(accumulator.basis)
    charged = sum(exceptions.basis)
    delta_l = price.saving - (charged / denominator if denominator > 0.0 else 0.0)
    a = delta_l / price.ell_frozen
    participation_term = participation(accumulator) * a
    embed_term = w * embed_value(embed, kappa) / price.ell_frozen
    total = participation_term + embed_term
    beta_term = 0.0
    if beta:
        if decay is None or elapsed is None:
            raise ValueError("β≠0 の保持値には減衰梯子と経過試行数が要る")
        p_r = adoption_rate(accumulator, decay, elapsed)
        beta_term = beta * ((1.0 - p_r) / p_r) * external_participation(
            accumulator, decay, elapsed
        ) * a
        total += beta_term
    return ValueTerms(participation_term, beta_term, embed_term, total)


def constituent_value(
    price: FrozenPrice,
    accumulator: MeritAccumulator,
    exceptions: ExceptionAccumulator,
    embed: EmbedState,
    *,
    w: float,
    kappa: float,
    beta: float = 0.0,
    decay: tuple[float, ...] | None = None,
    elapsed: int | None = None,
) -> float:
    return constituent_value_terms(
        price, accumulator, exceptions, embed,
        w=w, kappa=kappa, beta=beta, decay=decay, elapsed=elapsed,
    ).total


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
