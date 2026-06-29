from __future__ import annotations

import inspect

import abm.smoke as smoke
from abm.domains import OracleView, ScoringKey


def test_stage_11a_suite_still_has_exact_four_trials():
    result = smoke.run_minimal_smoke_suite()

    assert tuple(row.trial_id for row in result.results) == (
        "stage_11a::solar_system_atom::isomorphic",
        "stage_11a::solar_system_atom::anti_analogy",
        "stage_11a::water_heat_flow::isomorphic",
        "stage_11a::water_heat_flow::anti_analogy",
    )
    assert result.transfer_metrics.n_trials == 4


def test_stage_11a_entrypoint_still_rejects_role_divergence():
    try:
        smoke.run_smoke_trial(smoke.SmokeTrialConfig(seed_name="solar_system_atom", operator_name="role_divergence"))
    except ValueError as exc:
        assert "unsupported Stage 11a operator" in str(exc)
    else:  # pragma: no cover - this branch documents the frozen Stage 11a boundary.
        raise AssertionError("Stage 11a run_smoke_trial accepted role_divergence")


def test_role_divergence_two_arm_order_and_immediate_preparation():
    result = smoke.run_role_divergence_two_arm_smoke(
        smoke.RoleDivergenceSmokeConfig(seed_name="solar_system_atom")
    )

    assert result.absent_arm.role_divergence_trial.trial_id.endswith("::prototype_absent::role_divergence")
    assert result.present_arm.preparation_trial is not None
    assert result.present_arm.preparation_trial.trial_id.endswith("::prototype_present::isomorphic_preparation")
    assert result.present_arm.role_divergence_trial.trial_id.endswith("::prototype_present::role_divergence")
    assert result.present_arm.preparation_trial.operator_name == "isomorphic"
    assert result.present_arm.role_divergence_trial.operator_name == "role_divergence"


def test_role_divergence_two_arm_records_inert_prototype_without_effect_label():
    result = smoke.run_role_divergence_two_arm_smoke(
        smoke.RoleDivergenceSmokeConfig(seed_name="water_heat_flow")
    )

    assert result.absent_arm.prototype_present_at_presentation is False
    assert result.present_arm.prototype_present_at_presentation is True
    assert result.absent_arm.prototype_inert is True
    assert result.present_arm.prototype_inert is True
    assert any("prototype-to-prediction path" in note for note in result.present_arm.notes)
    assert hasattr(result, "arm_difference")
    assert not hasattr(result, "prototype_effect")
    assert "prototype_effect" not in smoke.RoleDivergenceSmokeResult.__dataclass_fields__


def test_arm_difference_is_neutral_delta_only():
    result = smoke.run_role_divergence_two_arm_smoke(
        smoke.RoleDivergenceSmokeConfig(seed_name="solar_system_atom")
    )
    diff = result.arm_difference

    assert set(smoke.RoleDivergenceArmDifference.__dataclass_fields__) == {
        "hit_delta",
        "coverage_delta",
        "description_length_delta",
        "sme_total_score_delta",
    }
    assert diff.hit_delta == result.present_arm.role_divergence_trial.hit - result.absent_arm.role_divergence_trial.hit
    assert diff.coverage_delta == (
        result.present_arm.role_divergence_trial.coverage - result.absent_arm.role_divergence_trial.coverage
    )


def test_role_divergence_leak_spy_blocks_oracle_objects_from_agent_side_calls(monkeypatch):
    violations: list[str] = []
    forbidden_attrs = {"G_star", "held_out_edge", "target_type", "seed_id", "oracle_view", "scoring_key"}

    def assert_oracle_free(name: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        for value in (*args, *kwargs.values()):
            if isinstance(value, (OracleView, ScoringKey)):
                violations.append(f"{name} received {type(value).__name__}")
            exposed = forbidden_attrs.intersection(dir(value))
            if exposed:
                violations.append(f"{name} received object exposing {sorted(exposed)}")

    originals = {
        "map_graphs": smoke.map_graphs,
        "project": smoke.project,
        "description_length": smoke.description_length,
        "frequency_baseline": smoke.frequency_baseline,
        "flat_matcher_baseline": smoke.flat_matcher_baseline,
    }

    def wrap(name):
        def spy(*args, **kwargs):
            assert_oracle_free(name, args, kwargs)
            return originals[name](*args, **kwargs)

        return spy

    for name in originals:
        monkeypatch.setattr(smoke, name, wrap(name))

    smoke.run_role_divergence_two_arm_smoke(smoke.RoleDivergenceSmokeConfig(seed_name="solar_system_atom"))

    assert violations == []


def test_no_result_filtering_or_ecology_later_stage_entrypoints():
    public_functions = {name for name, value in vars(smoke).items() if not name.startswith("_") and inspect.isfunction(value)}

    assert "run_role_divergence_smoke_trial" in public_functions
    assert "run_role_divergence_two_arm_smoke" in public_functions
    assert not any("ecology" in name for name in public_functions)
    assert not any("phase" in name for name in public_functions)
    assert not any("sweep" in name for name in public_functions)
    assert not any("plot" in name for name in public_functions)
    assert not any("convergence" in name for name in public_functions)
    assert not any("population" in name for name in public_functions)


def test_role_divergence_smoke_is_deterministic_across_repeated_runs():
    config = smoke.RoleDivergenceSmokeConfig(seed_name="solar_system_atom")

    assert smoke.run_role_divergence_two_arm_smoke(config) == smoke.run_role_divergence_two_arm_smoke(config)
