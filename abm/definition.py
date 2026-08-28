"""SPEC B1 §C.2 のdef(R)と会計用の不変型。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from abm.domains import Relation


@dataclass(frozen=True, slots=True)
class FrozenPrice:
    """登録時に確定し、以後いっさい再計算しない価格。"""

    ell_frozen: float
    c: int
    hold_cost: float
    m_alloc_at_reg: int

    @property
    def saving(self) -> float:
        return self.ell_frozen + self.c

    @property
    def a0(self) -> float:
        return self.saving / self.ell_frozen


@dataclass(frozen=True, slots=True)
class Constituent:
    slot_index: int
    registered_at: int
    relation: Relation
    frozen_price: FrozenPrice
    alive: bool = True


@dataclass(frozen=True, slots=True)
class NamedDefinition:
    name: str
    constituents: tuple[Constituent, ...]
    m_alloc: int
    registered_at: int
    assimilation_count: int = 1

    @property
    def m_live(self) -> int:
        return sum(1 for constituent in self.constituents if constituent.alive)


@dataclass(frozen=True, slots=True)
class MeritAccumulator:
    slot_index: int
    registered_at: int
    basis: tuple[float, ...]
    opportunity_basis: tuple[float, ...]
    use_count: float
    ext_use_count: int

    def __post_init__(self) -> None:
        if len(self.basis) != 16 or len(self.opportunity_basis) != 16:
            raise ValueError("指数基底は分子・分母とも16本である必要がある")


@dataclass(frozen=True, slots=True)
class ExceptionAccumulator:
    basis: tuple[float, ...]
    bits: float
    event_count: int

    def __post_init__(self) -> None:
        if len(self.basis) != 16:
            raise ValueError("例外費用の基底は16本である必要がある")


@dataclass(frozen=True, slots=True)
class EmbedState:
    slot_index: int
    fan_out: float
    fan_in_raw: float


@dataclass(frozen=True, slots=True)
class FrequencyTable:
    """p-hat。書かれた述語のみで更新するエージェント固有表。"""

    counts: Mapping[str, int]
    total: int
    lambda_mix: float
    alive_vocab: frozenset[str]

    @classmethod
    def empty(cls, lambda_mix: float = 0.1) -> "FrequencyTable":
        return cls({}, 0, lambda_mix, frozenset())

    def prob(self, predicate: str) -> float:
        vocabulary_size = max(len(self.alive_vocab), 1)
        if self.total == 0:
            return 1.0 / vocabulary_size
        empirical = self.counts.get(predicate, 0) / self.total
        if empirical == 0.0:
            return self.lambda_mix / vocabulary_size
        return empirical

    def code_length(self, predicate: str) -> float:
        return -math.log2(self.prob(predicate))
