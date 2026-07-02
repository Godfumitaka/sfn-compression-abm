from __future__ import annotations

import inspect
import json
import subprocess
import sys

from abm import perturbations, seeds
from abm.domains import AgentConfig, CorrectionMode, RelationGraph
from abm.sme import apply_threshold, map_graphs, prototype_prior_score


def _solar_inputs():
    seed = seeds.solar_system_atom()
    params = perturbations.PerturbationParams()
    return (
        seed,
        perturbations.isomorphic(seed, params).agent_input,
        perturbations.role_divergence(seed, params).agent_input,
    )


def test_agent_config_adds_inert_prototype_prior_weight():
    config = AgentConfig(threshold=1.0, correction_mode=CorrectionMode.NONE)

    assert config.lambda_ == 1.0
    assert config.prototype_prior_weight == 0.0


def test_map_graphs_backward_compatible_reduction_and_breakdown_identity():
    _, canonical_input, _ = _solar_inputs()

    old_style = map_graphs(canonical_input.base_graph, canonical_input.target_graph_partial)
    no_prototype = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=None,
        prototype_prior_weight=1.0,
    )
    zero_weight = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=canonical_input.target_graph_partial,
        prototype_prior_weight=0.0,
    )
    empty_prototype = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=RelationGraph("empty"),
        prototype_prior_weight=2.0,
    )

    assert no_prototype.alignment.total_score == old_style.alignment.total_score
    assert zero_weight.alignment.total_score == old_style.alignment.total_score
    assert empty_prototype.alignment.score_breakdown["prototype_prior_score"] == 0.0
    assert empty_prototype.alignment.total_score == old_style.alignment.total_score

    breakdown = old_style.alignment.score_breakdown
    assert breakdown["structural_score"] == (
        breakdown["predicate_match"]
        + breakdown["argument_consistency"]
        + breakdown["systematicity"]
        - breakdown["unmatched_penalty"]
    )
    assert old_style.alignment.total_score == breakdown["structural_score"]


def test_total_score_uses_single_final_prototype_prior_contribution_for_threshold():
    seed, canonical_input, _ = _solar_inputs()
    weighted = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=3.0,
    )
    breakdown = weighted.alignment.score_breakdown

    assert weighted.alignment.total_score == (
        breakdown["structural_score"]
        + breakdown["prototype_prior_weight"] * breakdown["prototype_prior_score"]
    )
    assert breakdown["prototype_prior_contribution"] == 3.0 * breakdown["prototype_prior_score"]
    assert breakdown["total_score"] == weighted.alignment.total_score

    threshold_between = breakdown["structural_score"] + 0.5 * breakdown["prototype_prior_contribution"]
    assert apply_threshold(weighted, threshold_between).accepted is True


def test_prototype_prior_is_per_candidate_decomposable_and_inspectable():
    seed, canonical_input, _ = _solar_inputs()
    mapping = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=1.0,
    )
    terms = mapping.alignment.prototype_prior_terms

    assert set(terms) == set(mapping.alignment.candidate_projections)
    assert mapping.alignment.score_breakdown["prototype_prior_score"] == sum(terms.values())
    assert any(value != 0.0 for value in terms.values())


def test_role_correspondence_prior_discriminates_canonical_from_role_diverged_without_labels():
    seed, canonical_input, role_diverged_input = _solar_inputs()
    canonical = map_graphs(
        canonical_input.base_graph,
        canonical_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=1.0,
    )
    role_diverged = map_graphs(
        role_diverged_input.base_graph,
        role_diverged_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=1.0,
    )

    assert canonical.alignment.score_breakdown["prototype_prior_score"] != role_diverged.alignment.score_breakdown[
        "prototype_prior_score"
    ]
    assert canonical.alignment.prototype_prior_terms != role_diverged.alignment.prototype_prior_terms


def test_prototype_prior_signature_is_oracle_safe_and_sme_source_has_no_forbidden_tokens():
    signature = inspect.signature(prototype_prior_score)

    assert "prototype" in signature.parameters
    assert "base_graph" in signature.parameters
    assert "target_graph_partial" in signature.parameters
    forbidden_parameters = {
        "oracle_view",
        "scoring_key",
        "G_star",
        "held_out_edge",
        "target_type",
        "seed_id",
        "hit",
        "accuracy",
        "baseline_results",
    }
    assert forbidden_parameters.isdisjoint(signature.parameters)

    source = inspect.getsource(sys.modules["abm.sme"])
    assert not any(token in source for token in ("OracleView", "ScoringKey", "G_star", "held_out_edge", "target_type", "seed_id"))


def test_score_breakdown_is_stable_across_python_hash_seeds():
    code = """
import json
from abm import perturbations, seeds
from abm.sme import map_graphs
seed = seeds.solar_system_atom()
ai = perturbations.isomorphic(seed, perturbations.PerturbationParams()).agent_input
m = map_graphs(ai.base_graph, ai.target_graph_partial, prototype=seed.target_graph, prototype_prior_weight=1.0)
print(json.dumps({"breakdown": m.alignment.score_breakdown, "terms": m.alignment.prototype_prior_terms}, sort_keys=True))
"""
    outputs = []
    for hash_seed in ("1", "37"):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": hash_seed, "PYTHONPATH": "."},
        )
        outputs.append(json.loads(completed.stdout))

    assert outputs[0] == outputs[1]
