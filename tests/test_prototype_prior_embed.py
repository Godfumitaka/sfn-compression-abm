import pytest

from abm.domains import Entity, Relation, RelationGraph, ScoringKey
from abm.gains import prediction_record
from abm.perturbations import (
    PerturbationParams,
    anti_analogy,
    isomorphic,
    opaque,
    role_divergence,
    role_reversal,
    surplus,
)
from abm.roles import OracleEvaluator
from abm.seeds import solar_system_atom, water_heat_flow
from abm.sme import PrototypePriorParams, map_graphs, project, prototype_prior_score

SEEDS = (solar_system_atom, water_heat_flow)
OPERATORS = (isomorphic, anti_analogy, role_reversal, role_divergence, surplus, opaque)
BASELINE_W0 = {
    ("isomorphic", "solar_system_atom"): ("EdgePrediction", ("revolves_around", ("electron", "nucleus")), 1, 26.5),
    ("isomorphic", "water_heat_flow"): ("EdgePrediction", ("flows_from_to", ("heat", "hot_object", "cold_object")), 1, 27.25),
    ("anti_analogy", "solar_system_atom"): ("EdgePrediction", ("revolves_around", ("electron", "nucleus")), 1, 26.5),
    ("anti_analogy", "water_heat_flow"): ("EdgePrediction", ("flows_from_to", ("heat", "hot_object", "cold_object")), 1, 27.25),
    ("role_reversal", "solar_system_atom"): ("Abstain", "ABSTAIN", 0, 16.0),
    ("role_reversal", "water_heat_flow"): ("Abstain", "ABSTAIN", 0, 16.75),
    ("role_divergence", "solar_system_atom"): ("Abstain", "ABSTAIN", 0, 16.0),
    ("role_divergence", "water_heat_flow"): ("Abstain", "ABSTAIN", 0, 16.75),
    ("surplus", "solar_system_atom"): ("EdgePrediction", ("revolves_around", ("electron", "nucleus")), 1, 26.5),
    ("surplus", "water_heat_flow"): ("EdgePrediction", ("flows_from_to", ("heat", "hot_object", "cold_object")), 1, 27.25),
    ("opaque", "solar_system_atom"): ("Abstain", "ABSTAIN", 0, 16.0),
    ("opaque", "water_heat_flow"): ("Abstain", "ABSTAIN", 0, 16.75),
}


def _run(operator, seed_ctor, weight=0.0):
    seed = seed_ctor()
    perturbation = operator(seed, PerturbationParams(instance_id="prototype_prior_embed_test"))
    mapping = map_graphs(
        perturbation.agent_input.base_graph,
        perturbation.agent_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=weight,
    )
    prediction = project(
        mapping.alignment,
        perturbation.agent_input.base_graph,
        perturbation.agent_input.target_graph_partial,
        prototype_prior_weight=weight,
    )
    record = prediction_record(
        prediction,
        evaluator=OracleEvaluator,
        scoring_key=ScoringKey(perturbation.oracle_view.held_out_edge),
    )
    return seed, perturbation, mapping, prediction, record


def test_prototype_prior_embed_w0_bit_identical():
    for operator in OPERATORS:
        for seed_ctor in SEEDS:
            seed, _perturbation, mapping, _prediction, record = _run(operator, seed_ctor, weight=0.0)
            assert (
                record.prediction_kind,
                record.prediction_category,
                int(record.hit),
                mapping.alignment.total_score,
            ) == BASELINE_W0[(operator.__name__, seed.seed_id)]


def test_prototype_prior_embed_opaque_breaks_tie():
    expected = {
        "solar_system_atom": ("solar_r3", "revolves_around", 2 / 3, {"solar_r5": 1 / 3, "solar_r6": 1 / 3}),
        "water_heat_flow": ("water_r3", "flows_from_to", 1.0, {"water_r6": 1 / 3, "water_r7": 1 / 3}),
    }
    for seed_ctor in SEEDS:
        seed, _perturbation, mapping, prediction, record = _run(opaque, seed_ctor, weight=1.0)
        relation_id, predicate, term, attribute_terms = expected[seed.seed_id]
        assert record.hit == 1
        assert prediction.edge.predicate == predicate
        assert mapping.alignment.prototype_prior_terms[relation_id] == pytest.approx(term)
        for candidate_id, candidate_term in attribute_terms.items():
            assert mapping.alignment.prototype_prior_terms[candidate_id] == pytest.approx(candidate_term)
        assert term > max(attribute_terms.values())


def test_prototype_prior_embed_role_divergence_two_arm_preserved():
    expected = {
        "solar_system_atom": ("revolves_around", ("electron", "nucleus")),
        "water_heat_flow": ("flows_from_to", ("heat", "hot_object", "cold_object")),
    }
    for seed_ctor in SEEDS:
        seed, *_rest, record0 = _run(role_divergence, seed_ctor, weight=0.0)
        _seed, _perturbation, _mapping, _prediction, record1 = _run(role_divergence, seed_ctor, weight=1.0)
        assert record0.prediction_kind == "Abstain"
        assert record1.hit == 0
        assert record1.prediction_category == expected[seed.seed_id]


def test_prototype_prior_embed_role_reversal_only_w_positive():
    for seed_ctor in SEEDS:
        _seed, *_rest, record0 = _run(role_reversal, seed_ctor, weight=0.0)
        _seed, _perturbation, _mapping, _prediction, record1 = _run(role_reversal, seed_ctor, weight=1.0)
        assert record0.prediction_kind == "Abstain"
        assert record1.prediction_kind == "EdgePrediction"
        assert record1.hit == 0


def test_prototype_prior_embed_gamma_unit():
    for seed_ctor in SEEDS:
        seed, perturbation, mapping, _prediction, _record = _run(opaque, seed_ctor, weight=1.0)
        base_kwargs = dict(
            entity_mapping=mapping.alignment.entity_mapping,
            candidate_projections=mapping.alignment.candidate_projections,
            prototype=seed.target_graph,
            base_graph=perturbation.agent_input.base_graph,
            target_graph_partial=perturbation.agent_input.target_graph_partial,
        )
        winners = []
        for gamma in (0.5, 1.0, 5.0, 50.0):
            result = prototype_prior_score(**base_kwargs, params=PrototypePriorParams(gamma=gamma))
            winners.append(max(result.per_candidate.items(), key=lambda item: item[1])[0])
        assert len(set(winners)) == 1
        gamma0 = prototype_prior_score(**base_kwargs, params=PrototypePriorParams(gamma=0.0))
        for relation_id, term in gamma0.per_candidate.items():
            relation = {r.relation_id: r for r in perturbation.agent_input.base_graph.relations}[relation_id]
            size_weight = 1.0 / (sum(1 for graph in (seed.target_graph, perturbation.agent_input.base_graph) for r in graph.relations if r.predicate == relation.predicate) + 1.0)
            assert term == pytest.approx(size_weight)


def _graph(relations):
    return RelationGraph("fixture", (Entity("a"), Entity("b")), tuple(relations))


def _embed_term(prototype, embed_lambda=1.0, cap=3):
    base = _graph((Relation("r1", "p", ("a",)),))
    target = _graph(())
    result = prototype_prior_score(
        entity_mapping={"a": "a"},
        candidate_projections=("r1",),
        prototype=prototype,
        base_graph=base,
        target_graph_partial=target,
        params=PrototypePriorParams(theta=1.0, size_exponent=0.0, gamma=1.0, embed_lambda=embed_lambda, embed_depth_cap=cap),
    )
    return result.per_candidate["r1"] - 1.0


def test_embed_cascade_cap_cycle_and_diamond():
    assert _embed_term(_graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1",)), Relation("r3", "h", ("r2",)), Relation("r2_cycle", "h", ("r3",)),))) == pytest.approx(3.0)
    cycle = _graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1", "r3")), Relation("r3", "h", ("r2",))))
    assert _embed_term(cycle) == pytest.approx(2.0)
    chain4 = _graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1",)), Relation("r3", "h", ("r2",)), Relation("r4", "h", ("r3",)), Relation("r5", "h", ("r4",))))
    assert _embed_term(chain4, cap=3) == pytest.approx(3.0)
    assert _embed_term(chain4, cap=10) == pytest.approx(4.0)
    width = _graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1",)), Relation("r3", "h", ("r1",)), Relation("r4", "h", ("r2",)), Relation("r5", "h", ("r3",))))
    assert _embed_term(width, cap=3) == pytest.approx(4.0)
    diamond = _graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1",)), Relation("r3", "h", ("r1",)), Relation("r4", "h", ("r2", "r3"))))
    assert _embed_term(diamond, cap=3) == pytest.approx(4.0)


def test_prototype_prior_embed_lambda_unit():
    fixture = _graph((Relation("r1", "p", ("a",)), Relation("r2", "h", ("r1",)), Relation("r3", "h", ("r2",))))
    assert _embed_term(fixture, embed_lambda=0.0) == pytest.approx(1.0)
    assert _embed_term(fixture, embed_lambda=0.5) == pytest.approx(1.5)
    assert _embed_term(fixture, embed_lambda=1.0) == pytest.approx(2.0)


def test_prototype_pattern_to_id_uniqueness():
    duplicate = _graph((Relation("r1", "p", ("a",)), Relation("r1_dup", "p", ("a",))))
    with pytest.raises(ValueError, match="exactly one relation_id"):
        _embed_term(duplicate)
