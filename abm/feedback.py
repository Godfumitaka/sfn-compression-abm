"""SPEC B0+B2 §B.8 の f(agent, t) と共通乱数判定。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


DEFAULT_F_SETTING = 0.1
FeedbackFrequency = Callable[[str, int], float]


@dataclass(frozen=True, slots=True)
class FeedbackCoinResult:
    agent_id: str
    t: int
    coin_t: float
    f_realized: float
    f_fired: bool

    @property
    def u_t(self) -> float:
        """層Aの旧名を読み取りのみ互換として残す。"""

        return self.coin_t

    @property
    def f_setting(self) -> float:
        return self.f_realized


def f(agent_id: str, t: int) -> float:
    """初期実装の一様な f。後の時空間非一様化に備え署名を保つ。"""

    _ = (agent_id, t)
    return DEFAULT_F_SETTING


def evaluate_feedback_coin(
    agent_id: str,
    t: int,
    coin_t: float,
    frequency: FeedbackFrequency = f,
) -> FeedbackCoinResult:
    """世界列の共通乱数と実際の f を記録し、発火を判定する。"""

    if not 0.0 <= coin_t < 1.0:
        raise ValueError("coin_t は 0 <= coin_t < 1 である必要がある")
    setting = float(frequency(agent_id, t))
    if not 0.0 <= setting <= 1.0:
        raise ValueError("f(agent_id, t) は 0 <= f <= 1 である必要がある")
    return FeedbackCoinResult(agent_id, t, coin_t, setting, coin_t < setting)
