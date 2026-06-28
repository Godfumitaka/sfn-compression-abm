import importlib
import inspect
import subprocess
import sys

import pytest

from abm.ecology import (
    ALPHA_PROFILE,
    BETA_PROFILE,
    DEFAULT_ECOLOGY_PROFILES,
    EcologyPlan,
    EcologyProfile,
    InstancePlan,
    allocate_counts,
    build_ecology_plan,
    enforce_presentation_order,
    stratify_plan,
    validate_ecology_plan,
)


def test_profile_rejects_negative_weights():
    with pytest.raises(ValueError):
        EcologyProfile("bad", {"isomorphic": -1})


def test_profile_rejects_zero_total():
    with pytest.raises(ValueError):
        EcologyProfile("bad", {"isomorphic": 0, "surplus": 0})


def test_default_profiles_are_named_presentation_profiles_only():
    assert set(DEFAULT_ECOLOGY_PROFILES) == {"alpha", "beta", "gamma"}
    assert ALPHA_PROFILE.weights["isomorphic"] > BETA_PROFILE.weights["isomorphic"]
    forbidden_result_words = {"useful_abstraction", "mythology", "isolated_insight", "success_rate"}
    for profile in DEFAULT_ECOLOGY_PROFILES.values():
        assert forbidden_result_words.isdisjoint(profile.weights)


def test_allocate_counts_sum_exactly_and_tie_breaks_by_name():
    profile = EcologyProfile("tie", {"b": 1, "a": 1, "c": 1})
    assert allocate_counts(profile, 2) == {"a": 1, "b": 1, "c": 0}
    assert sum(allocate_counts(ALPHA_PROFILE, 37).values()) == 37


def test_allocate_counts_is_hash_seed_independent(tmp_path):
    code = "from abm.ecology import ALPHA_PROFILE, allocate_counts; print(dict(allocate_counts(ALPHA_PROFILE, 17)))"
    outputs = set()
    for seed in ("1", "777"):
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            text=True,
            capture_output=True,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": "."},
        )
        outputs.add(result.stdout.strip())
    assert len(outputs) == 1


def test_build_plan_ids_and_order_are_deterministic():
    first = build_ecology_plan(ALPHA_PROFILE, 12, ["seed_b", "seed_a"])
    second = build_ecology_plan(ALPHA_PROFILE, 12, ["seed_b", "seed_a"])
    assert first.instances == second.instances
    assert len({item.instance_id for item in first.instances}) == len(first.instances)
    assert [item.order_index for item in first.instances] == list(range(12))


def test_isomorphic_precedes_role_divergence_and_other_order_is_stable():
    items = (
        InstancePlan("x1", "s", "anti_analogy", 0),
        InstancePlan("x2", "s", "role_divergence", 1),
        InstancePlan("x3", "s", "opaque", 2),
        InstancePlan("x4", "s", "isomorphic", 3),
        InstancePlan("x5", "s", "surplus", 4),
    )
    ordered = enforce_presentation_order(items)
    assert [item.instance_id for item in ordered] == ["x4", "x1", "x3", "x5", "x2"]
    validate_ecology_plan(EcologyPlan(ALPHA_PROFILE, ordered))


def test_plan_construction_is_metadata_only_without_forbidden_dependencies(monkeypatch):
    import abm.ecology as ecology

    def blocked_import(name, *args, **kwargs):
        if name in {"abm.perturbations", "abm.agent_runtime"}:
            raise AssertionError(f"unexpected import: {name}")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", blocked_import)
    importlib.reload(ecology)
    plan = ecology.build_ecology_plan(ecology.ALPHA_PROFILE, 6, ["seed"])
    assert all(set(item.metadata) == set() for item in plan.instances)


def test_module_source_has_no_forbidden_boundary_dependencies():
    import abm.ecology as ecology

    source = inspect.getsource(ecology)
    for token in ("OracleView", "ScoringKey", "OracleEvaluator", "G_star", "held_out_edge", "AgentInput"):
        assert token not in source


def test_stratification_is_pure_metadata_grouping():
    plan = build_ecology_plan(ALPHA_PROFILE, 10, ["seed_b", "seed_a"])
    by_operator = stratify_plan(plan)
    assert set(by_operator) <= set(ALPHA_PROFILE.weights)
    assert sum(len(items) for items in by_operator.values()) == len(plan.instances)


def test_no_stage_11_entrypoints_are_introduced():
    import abm.ecology as ecology

    names = set(dir(ecology))
    assert {"run", "execute", "sweep", "simulate"}.isdisjoint(names)
