"""SPEC §8 の収束スタイル指標ユーティリティ。

Stage 9 は、SPEC §7.3 と同じ出力カテゴリ一致形式を再利用する薄い集計層だけを
提供する。カテゴリは正準化済みの予測 relation content または Abstain であり、正誤
二値には潰さない。

層Aでは社会的収束や神話の安定化を主張しない。このモジュールの値が収束指標として
解釈できるのは、後続層で必要な統制条件が別途満たされた場合、または既に計算済みの
伝達条件差を純粋に比較する場合に限られる。ここでは伝達過程・送信方策・集団動態を
実装しない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from abm.gains import PredictionCategory, coordination_gain


@dataclass(frozen=True, slots=True)
class OutputAgreement:
    """試行整列済み出力カテゴリの observed - chance 一致。"""

    observed_agreement: float
    chance_agreement: float
    agreement_gain: float
    n_items: int


@dataclass(frozen=True, slots=True)
class ErrorAgreement:
    """呼び出し側が事前抽出したカテゴリ上の一致。

    この型は「どれが誤りか」を判定しない。入力カテゴリは、事後分析側が必要な根拠で
    既に抽出した出力カテゴリ列であり、Abstain が含まれる場合も単なるカテゴリとして
    扱う。
    """

    observed_agreement: float
    chance_agreement: float
    error_agreement: float
    n_items: int


@dataclass(frozen=True, slots=True)
class PairPredictability:
    """二者の出力カテゴリ一致から得る pair predictability。"""

    observed_agreement: float
    chance_agreement: float
    pair_predictability: float
    n_items: int


@dataclass(frozen=True, slots=True)
class TransmissionComparison:
    """既に計算済みの off/on 指標値の純粋比較。"""

    off_value: float
    on_value: float
    delta: float


def agreement_from_categories(
    categories_a: Sequence[PredictionCategory],
    categories_b: Sequence[PredictionCategory],
) -> OutputAgreement:
    """Stage 8 の出力カテゴリ一致式を、汎用名で返す薄いラッパー。"""

    result = coordination_gain(categories_a, categories_b)
    return OutputAgreement(
        observed_agreement=result.observed_agreement,
        chance_agreement=result.chance_agreement,
        agreement_gain=result.coordination_gain,
        n_items=result.n_trials,
    )


def pair_predictability(
    categories_a: Sequence[PredictionCategory],
    categories_b: Sequence[PredictionCategory],
) -> PairPredictability:
    """SPEC §8 の pair predictability を §7.3 と同一式で計算する。"""

    agreement = agreement_from_categories(categories_a, categories_b)
    return PairPredictability(
        observed_agreement=agreement.observed_agreement,
        chance_agreement=agreement.chance_agreement,
        pair_predictability=agreement.agreement_gain,
        n_items=agreement.n_items,
    )


def error_agreement(
    error_categories_a: Sequence[PredictionCategory],
    error_categories_b: Sequence[PredictionCategory],
) -> ErrorAgreement:
    """事前抽出済みカテゴリ上の一致を計算する。

    空列は、抽出対象が存在しないことを曖昧にしないため ``ValueError`` とする。
    """

    if len(error_categories_a) == 0 and len(error_categories_b) == 0:
        raise ValueError("error_agreement requires at least one prefiltered category")
    agreement = agreement_from_categories(error_categories_a, error_categories_b)
    return ErrorAgreement(
        observed_agreement=agreement.observed_agreement,
        chance_agreement=agreement.chance_agreement,
        error_agreement=agreement.agreement_gain,
        n_items=agreement.n_items,
    )


def compare_transmission_conditions(off_metric: float, on_metric: float) -> TransmissionComparison:
    """既に算出済みの伝達 off/on 指標値を比較する。"""

    return TransmissionComparison(
        off_value=float(off_metric),
        on_value=float(on_metric),
        delta=float(on_metric) - float(off_metric),
    )
