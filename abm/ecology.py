"""BUILD ORDER 第10段の提示計画ユーティリティ。"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from math import floor
from types import MappingProxyType
from typing import Mapping, Literal

ScalarMetadata = str | int | float | bool
StratifyBy = Literal["operator_name", "seed_name", "profile_name", "stratum"]

DEFAULT_OPERATOR_NAMES: tuple[str, ...] = (
    "isomorphic",
    "anti_analogy",
    "role_reversal",
    "role_divergence",
    "surplus",
    "opaque",
)


@dataclass(frozen=True, slots=True)
class EcologyArm:
    """提示腕についての説明用メタデータ。"""

    operator_name: str
    weight: float
    group: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.operator_name:
            raise ValueError("operator_name must be nonempty")
        if self.weight < 0:
            raise ValueError("weight must be nonnegative")


@dataclass(frozen=True, slots=True)
class EcologyProfile:
    """alpha/beta/gamma などの提示構成プロファイル。"""

    name: str
    weights: Mapping[str, float]
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("profile name must be nonempty")
        ordered_weights = {key: float(self.weights[key]) for key in sorted(self.weights)}
        if any(weight < 0 for weight in ordered_weights.values()):
            raise ValueError("profile weights must be nonnegative")
        if sum(ordered_weights.values()) <= 0:
            raise ValueError("profile total weight must be positive")
        object.__setattr__(self, "weights", MappingProxyType(ordered_weights))

    def normalized_weights(self) -> Mapping[str, float]:
        return normalize_profile(self)


@dataclass(frozen=True, slots=True)
class InstancePlan:
    """後続の実行ログと結合するための提示予定メタデータ。"""

    instance_id: str
    seed_name: str
    operator_name: str
    order_index: int
    profile_name: str | None = None
    stratum: str | None = None
    metadata: Mapping[str, ScalarMetadata] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instance_id:
            raise ValueError("instance_id must be nonempty")
        if not self.seed_name:
            raise ValueError("seed_name must be nonempty")
        if not self.operator_name:
            raise ValueError("operator_name must be nonempty")
        if self.order_index < 0:
            raise ValueError("order_index must be nonnegative")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EcologyPlan:
    """具体化や評価を行わない提示予定の列。"""

    profile: EcologyProfile
    instances: tuple[InstancePlan, ...]
    expected_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "instances", tuple(self.instances))
        object.__setattr__(self, "expected_counts", MappingProxyType(dict(self.expected_counts)))

    def count_by_operator(self) -> Mapping[str, int]:
        return MappingProxyType(dict(Counter(item.operator_name for item in self.instances)))

    def count_by_seed(self) -> Mapping[str, int]:
        return MappingProxyType(dict(Counter(item.seed_name for item in self.instances)))

    def count_by_stratum(self) -> Mapping[str, int]:
        return MappingProxyType(dict(Counter(item.stratum or "" for item in self.instances)))


ALPHA_PROFILE = EcologyProfile(
    "alpha",
    {"isomorphic": 50, "anti_analogy": 10, "role_divergence": 10, "opaque": 10, "role_reversal": 15, "surplus": 5},
    label="ability_anchor_majority",
)
BETA_PROFILE = EcologyProfile(
    "beta",
    {"isomorphic": 20, "anti_analogy": 25, "role_divergence": 25, "opaque": 20, "role_reversal": 5, "surplus": 5},
    label="error_site_majority",
)
GAMMA_PROFILE = EcologyProfile(
    "gamma",
    {"isomorphic": 30, "anti_analogy": 18, "role_divergence": 17, "opaque": 17, "role_reversal": 13, "surplus": 5},
    label="balanced_middle",
)
DEFAULT_ECOLOGY_PROFILES: Mapping[str, EcologyProfile] = MappingProxyType(
    {profile.name: profile for profile in (ALPHA_PROFILE, BETA_PROFILE, GAMMA_PROFILE)}
)


def normalize_profile(profile: EcologyProfile) -> Mapping[str, float]:
    total = sum(profile.weights.values())
    if any(weight < 0 for weight in profile.weights.values()):
        raise ValueError("profile weights must be nonnegative")
    if total <= 0:
        raise ValueError("profile total weight must be positive")
    return MappingProxyType({key: profile.weights[key] / total for key in sorted(profile.weights)})


def allocate_counts(profile: EcologyProfile, n_instances: int) -> Mapping[str, int]:
    if n_instances < 0:
        raise ValueError("n_instances must be nonnegative")
    normalized = normalize_profile(profile)
    raw = {key: normalized[key] * n_instances for key in sorted(normalized)}
    counts = {key: floor(value) for key, value in raw.items()}
    remainder = n_instances - sum(counts.values())
    ranked = sorted(raw, key=lambda key: (-(raw[key] - counts[key]), key))
    for key in ranked[:remainder]:
        counts[key] += 1
    return MappingProxyType({key: counts[key] for key in sorted(counts)})


def build_ecology_plan(
    profile: EcologyProfile,
    n_instances: int,
    seed_names: tuple[str, ...] | list[str],
    operator_order: tuple[str, ...] = DEFAULT_OPERATOR_NAMES,
    apply_order_policy: bool = True,
) -> EcologyPlan:
    if n_instances < 0:
        raise ValueError("n_instances must be nonnegative")
    seeds = tuple(sorted(str(seed) for seed in seed_names if str(seed)))
    if n_instances and not seeds:
        raise ValueError("seed_names must contain at least one nonempty value")
    known = tuple(operator_order)
    unknown = set(profile.weights) - set(known)
    if unknown:
        raise ValueError(f"unknown operator names: {tuple(sorted(unknown))}")
    counts = allocate_counts(profile, n_instances)
    instances: list[InstancePlan] = []
    seed_cursor = 0
    ordinal_by_operator: dict[str, int] = defaultdict(int)
    for operator_name in known:
        for _ in range(counts.get(operator_name, 0)):
            seed_name = seeds[seed_cursor % len(seeds)] if seeds else ""
            seed_cursor += 1
            ordinal_by_operator[operator_name] += 1
            ordinal = ordinal_by_operator[operator_name]
            instance_id = f"{profile.name}__{operator_name}__{seed_name}__{ordinal:04d}"
            instances.append(
                InstancePlan(
                    instance_id=instance_id,
                    seed_name=seed_name,
                    operator_name=operator_name,
                    order_index=len(instances),
                    profile_name=profile.name,
                    stratum=operator_name,
                )
            )
    ordered = enforce_presentation_order(instances) if apply_order_policy else _reindex(instances)
    expected_counts = {key: value for key, value in counts.items() if value}
    plan = EcologyPlan(profile=profile, instances=ordered, expected_counts=expected_counts)
    validate_ecology_plan(plan, operator_names=known)
    return plan


def enforce_presentation_order(instances: tuple[InstancePlan, ...] | list[InstancePlan]) -> tuple[InstancePlan, ...]:
    indexed = tuple(instances)
    iso = [item for item in indexed if item.operator_name == "isomorphic"]
    middle = [item for item in indexed if item.operator_name not in {"isomorphic", "role_divergence"}]
    divergence = [item for item in indexed if item.operator_name == "role_divergence"]
    return _reindex((*iso, *middle, *divergence))


def stratify_plan(plan: EcologyPlan, by: StratifyBy = "operator_name") -> Mapping[str, tuple[InstancePlan, ...]]:
    groups: dict[str, list[InstancePlan]] = defaultdict(list)
    for item in plan.instances:
        value = getattr(item, by)
        groups[str(value or "")].append(item)
    return MappingProxyType({key: tuple(groups[key]) for key in sorted(groups)})


def validate_ecology_plan(
    plan: EcologyPlan,
    operator_names: tuple[str, ...] = DEFAULT_OPERATOR_NAMES,
) -> None:
    ids = [item.instance_id for item in plan.instances]
    if len(ids) != len(set(ids)):
        raise ValueError("instance_id values must be unique")
    for expected, item in enumerate(plan.instances):
        if item.order_index != expected:
            raise ValueError("order_index must match tuple order and be contiguous")
        if item.operator_name not in operator_names:
            raise ValueError(f"unknown operator name: {item.operator_name}")
        if not item.seed_name:
            raise ValueError("seed_name must be nonempty")
    iso_indexes = [item.order_index for item in plan.instances if item.operator_name == "isomorphic"]
    div_indexes = [item.order_index for item in plan.instances if item.operator_name == "role_divergence"]
    if iso_indexes and div_indexes and max(iso_indexes) >= min(div_indexes):
        raise ValueError("isomorphic presentations must precede role_divergence presentations")
    if plan.expected_counts:
        observed = Counter(item.operator_name for item in plan.instances)
        if dict(observed) != dict(plan.expected_counts):
            raise ValueError("plan counts do not match expected_counts")


def _reindex(instances: tuple[InstancePlan, ...] | list[InstancePlan]) -> tuple[InstancePlan, ...]:
    return tuple(replace(item, order_index=index) for index, item in enumerate(instances))
