from __future__ import annotations

import inspect

import pytest

import abm.smoke as smoke
from abm.domains import AgentOutput, OracleView, ScoringKey


def test_minimal_smoke_suite_runs_exact_four_trials_in_fixed_order():
    result = smoke.run_minimal_smoke_suite()

    assert tuple((row.seed_name, row.operator_name) for row in result.results) == (
        ("solar_system_atom", "isomorphic"),
        ("solar_system_atom", "anti_analogy"),
        ("water_heat_flow", "isomorphic"),
        ("water_heat_flow", "anti_analogy"),
    )
    assert tuple(row.trial_id for row in result.results) == (
        "stage_11a::solar_system_atom::isomorphic",
        "stage_11a::solar_system_atom::anti_analogy",
        "stage_11a::water_heat_flow::isomorphic",
        "stage_11a::water_heat_flow::anti_analogy",
    )
    assert result.transfer_metrics.n_trials == 4


def test_run_smoke_trial_rejects_stage_11b_operator():
    with pytest.raises(ValueError, match="unsupported Stage 11a operator"):
        smoke.run_smoke_trial(smoke.SmokeTrialConfig(seed_name="solar_system_atom", operator_name="role_divergence"))


def test_leak_spy_blocks_oracle_objects_from_agent_side_calls(monkeypatch):
    violations: list[str] = []
    forbidden_attrs = {"G_star", "held_out_edge", "target_type", "seed_id", "oracle_view", "scoring_key"}

    def assert_oracle_free(name: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        for value in (*args, *kwargs.values()):
            if isinstance(value, (OracleView, ScoringKey)):
                violations.append(f"{name} received {type(value).__name__}")
            exposed = forbidden_attrs.intersection(dir(value))
            if exposed:
                violations.append(f"{name} received object exposing {sorted(exposed)}")

    original_map = smoke.map_graphs
    original_project = smoke.project
    original_description = smoke.description_length
    original_frequency = smoke.frequency_baseline
    original_flat = smoke.flat_matcher_baseline

    def map_spy(*args, **kwargs):
        assert_oracle_free("map_graphs", args, kwargs)
        return original_map(*args, **kwargs)

    def project_spy(*args, **kwargs):
        assert_oracle_free("project", args, kwargs)
        return original_project(*args, **kwargs)

    def description_spy(*args, **kwargs):
        assert_oracle_free("description_length", args, kwargs)
        return original_description(*args, **kwargs)

    def frequency_spy(*args, **kwargs):
        assert_oracle_free("frequency_baseline", args, kwargs)
        return original_frequency(*args, **kwargs)

    def flat_spy(*args, **kwargs):
        assert_oracle_free("flat_matcher_baseline", args, kwargs)
        return original_flat(*args, **kwargs)

    monkeypatch.setattr(smoke, "map_graphs", map_spy)
    monkeypatch.setattr(smoke, "project", project_spy)
    monkeypatch.setattr(smoke, "description_length", description_spy)
    monkeypatch.setattr(smoke, "frequency_baseline", frequency_spy)
    monkeypatch.setattr(smoke, "flat_matcher_baseline", flat_spy)

    smoke.run_minimal_smoke_suite()

    assert violations == []


def test_hit_evaluation_delegates_to_oracle_evaluator(monkeypatch):
    calls: list[ScoringKey] = []
    original = smoke.OracleEvaluator

    def evaluator(agent_output: AgentOutput, scoring_key: ScoringKey):
        calls.append(scoring_key)
        return original(agent_output, scoring_key)

    monkeypatch.setattr(smoke, "OracleEvaluator", evaluator)
    result = smoke.run_smoke_trial(smoke.SmokeTrialConfig(seed_name="solar_system_atom", operator_name="isomorphic"))

    assert result.hit in (0, 1)
    assert len(calls) == 3
    assert all(isinstance(key, ScoringKey) for key in calls)


def test_description_length_is_recorded_separately_from_hit(monkeypatch):
    result = smoke.run_smoke_trial(smoke.SmokeTrialConfig(seed_name="water_heat_flow", operator_name="anti_analogy"))

    assert isinstance(result.description_length, float)
    assert result.description_length >= 0.0
    assert isinstance(result.hit, int)
    assert "description_length" in smoke.SmokeTrialResult.__dataclass_fields__
    assert "hit" in smoke.SmokeTrialResult.__dataclass_fields__


def test_abstain_uses_stage8_record_semantics():
    result = smoke.run_smoke_trial(
        smoke.SmokeTrialConfig(seed_name="solar_system_atom", operator_name="isomorphic", threshold=10**9)
    )

    assert result.prediction_kind == "Abstain"
    assert result.abstain_reason == "below_threshold"
    assert result.hit == 0
    assert result.coverage == 0


def test_baseline_records_are_trial_level():
    result = smoke.run_minimal_smoke_suite()

    assert all(row.frequency_baseline_record is not None for row in result.results)
    assert all(row.flat_matcher_baseline_record is not None for row in result.results)
    assert [row.frequency_baseline_record.baseline_name for row in result.results] == ["frequency"] * 4
    assert [row.flat_matcher_baseline_record.baseline_name for row in result.results] == ["flat_matcher"] * 4


def test_no_forbidden_stage_11b_or_later_entrypoints():
    public_names = {name for name, value in vars(smoke).items() if not name.startswith("_") and inspect.isfunction(value)}

    assert "run_sme" not in public_names
    assert "role_divergence" not in public_names
    assert not any("ecology" in name for name in public_names)
    assert not any("phase" in name for name in public_names)
    assert not any("sweep" in name for name in public_names)
    assert not any("plot" in name for name in public_names)
    assert not any("convergence" in name for name in public_names)


def test_smoke_suite_is_deterministic_across_repeated_runs():
    left = smoke.run_minimal_smoke_suite()
    right = smoke.run_minimal_smoke_suite()

    assert left == right
