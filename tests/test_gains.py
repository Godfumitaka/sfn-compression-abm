import pytest

from abm.domains import Abstain, AgentInput, EdgePrediction, Relation, RelationGraph, ScoringKey
from abm.gains import (
    ABSTAIN_CATEGORY,
    BaselineTrialRecord,
    TrialPredictionRecord,
    baseline_lift,
    coordination_gain,
    flat_matcher_baseline,
    frequency_baseline,
    prediction_category,
    prediction_record,
    transfer_metrics,
)


def rel(relation_id, predicate, *arguments):
    return Relation(relation_id=relation_id, predicate=predicate, arguments=arguments)


def graph(graph_id, relations):
    return RelationGraph(graph_id=graph_id, relations=tuple(relations))


def test_prediction_category_uses_content_not_relation_id():
    left = EdgePrediction(rel("sme_projection__a", "attracts", "sun", "planet"))
    right = EdgePrediction(rel("other", "attracts", "sun", "planet"))
    same_id_different_content = EdgePrediction(rel("sme_projection__a", "orbits", "planet", "sun"))

    assert prediction_category(left) == prediction_category(right)
    assert prediction_category(left) != prediction_category(same_id_different_content)


def test_abstain_category_collapses_reason_and_record_has_zero_coverage():
    first = Abstain("below_threshold")
    second = Abstain("ambiguous")

    assert prediction_category(first) == ABSTAIN_CATEGORY
    assert prediction_category(first) == prediction_category(second)
    record = prediction_record(first, scoring_key=ScoringKey(rel("answer", "p", "x")))
    assert record.hit == 0
    assert record.coverage == 0


def test_transfer_metrics_include_abstain_denominator_and_nullable_selective_accuracy():
    records = [
        prediction_record(EdgePrediction(rel("p1", "p", "x")), scoring_key=ScoringKey(rel("gold", "p", "x"))),
        prediction_record(Abstain("none"), scoring_key=ScoringKey(rel("gold", "q", "y"))),
    ]
    metrics = transfer_metrics(records)

    assert metrics.accuracy == pytest.approx(0.5)
    assert metrics.coverage == pytest.approx(0.5)
    assert metrics.selective_accuracy == pytest.approx(1.0)
    assert transfer_metrics([records[1]]).selective_accuracy is None


def test_hit_delegates_to_supplied_evaluator():
    calls = []

    def evaluator(agent_output, scoring_key):
        calls.append((agent_output.prediction, scoring_key))
        return type("Result", (), {"hit": 1, "coverage": 1})()

    key = ScoringKey(rel("gold", "different", "z"))
    record = prediction_record(EdgePrediction(rel("pred", "p", "x")), evaluator=evaluator, scoring_key=key)

    assert record.hit == 1
    assert len(calls) == 1


def test_frequency_and_flat_baselines_return_trial_level_predictions():
    agent_input = AgentInput(
        base_graph=graph("base", [rel("b1", "same", "a", "b"), rel("b2", "missing", "a")]),
        target_graph_partial=graph("target", [rel("t1", "same", "x", "y")]),
    )

    flat = flat_matcher_baseline(agent_input)
    assert prediction_category(flat) == ("missing", ("x",))

    freq = frequency_baseline(agent_input, {("freq", ("u",)): 3})
    assert prediction_category(freq) == ("freq", ("u",))


def test_baseline_lift_is_difference_not_ratio():
    agent_records = [
        TrialPredictionRecord(("a", ()), "EdgePrediction", ("a", ()), None, 1, 1),
        TrialPredictionRecord(("b", ()), "EdgePrediction", ("b", ()), None, 0, 1),
    ]
    baseline_records = [
        BaselineTrialRecord("frequency", ("a", ()), ("a", ()), None, 0, 1),
        BaselineTrialRecord("frequency", ("b", ()), ("b", ()), None, 0, 1),
    ]

    lift = baseline_lift(agent_records, baseline_records, "frequency")
    assert lift.lift == pytest.approx(0.5)


def test_coordination_gain_independent_multicategory_is_zero():
    categories_a = [("a", ("1",)), ("a", ("1",)), ("b", ("2",)), ("b", ("2",))]
    categories_b = [("x", ("1",)), ("y", ("2",)), ("x", ("1",)), ("y", ("2",))]

    result = coordination_gain(categories_a, categories_b)
    assert result.observed_agreement == pytest.approx(0.0)
    assert result.coordination_gain == pytest.approx(0.0)


def test_coordination_gain_shared_wrong_edge_positive_and_asymmetric_three_categories():
    shared = ("wrong", ("u", "v"))
    categories_a = [shared, shared, ("a", ("1",)), ABSTAIN_CATEGORY]
    categories_b = [shared, shared, ("b", ("2",)), ("b", ("2",))]

    result = coordination_gain(categories_a, categories_b)
    assert result.n_trials == 4
    assert result.observed_agreement == pytest.approx(0.5)
    assert result.chance_agreement == pytest.approx(0.25)
    assert result.coordination_gain == pytest.approx(0.25)
