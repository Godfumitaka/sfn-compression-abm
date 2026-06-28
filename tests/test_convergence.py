import inspect
import os
import subprocess
import sys

import pytest

from abm.gains import ABSTAIN_CATEGORY, coordination_gain
from abm.convergence import (
    ErrorAgreement,
    OutputAgreement,
    PairPredictability,
    TransmissionComparison,
    agreement_from_categories,
    compare_transmission_conditions,
    error_agreement,
    pair_predictability,
)


def test_pair_predictability_equals_stage8_coordination_gain():
    categories_a = [("same", ("x",)), ("shared", ("u",)), ABSTAIN_CATEGORY, ("a", ("1",))]
    categories_b = [("same", ("x",)), ("shared", ("u",)), ("b", ("2",)), ("b", ("2",))]

    expected = coordination_gain(categories_a, categories_b)
    result = pair_predictability(categories_a, categories_b)

    assert isinstance(result, PairPredictability)
    assert result.observed_agreement == pytest.approx(expected.observed_agreement)
    assert result.chance_agreement == pytest.approx(expected.chance_agreement)
    assert result.pair_predictability == pytest.approx(expected.coordination_gain)
    assert result.n_items == expected.n_trials


def test_agreement_handles_asymmetric_marginals_and_three_categories():
    categories_a = [("a", ("1",)), ("a", ("1",)), ("b", ("2",)), ("c", ("3",))]
    categories_b = [("a", ("1",)), ("b", ("2",)), ("b", ("2",)), ("b", ("2",))]

    result = agreement_from_categories(categories_a, categories_b)

    assert isinstance(result, OutputAgreement)
    assert result.observed_agreement == pytest.approx(0.5)
    assert result.chance_agreement == pytest.approx((2 / 4) * (1 / 4) + (1 / 4) * (3 / 4))
    assert result.agreement_gain == pytest.approx(0.1875)
    assert result.n_items == 4


def test_independent_balanced_multicategory_sequences_have_zero_gain():
    categories_a = [("a", ("1",)), ("a", ("1",)), ("b", ("2",)), ("b", ("2",))]
    categories_b = [("x", ("1",)), ("y", ("2",)), ("x", ("1",)), ("y", ("2",))]

    result = pair_predictability(categories_a, categories_b)

    assert result.observed_agreement == pytest.approx(0.0)
    assert result.pair_predictability == pytest.approx(0.0)


def test_shared_same_output_category_positive_beyond_marginals():
    shared = ("wrong_edge", ("u", "v"))
    categories_a = [shared, shared, ("a", ("1",)), ("c", ("3",))]
    categories_b = [shared, shared, ("b", ("2",)), ("d", ("4",))]

    result = pair_predictability(categories_a, categories_b)

    assert result.observed_agreement == pytest.approx(0.5)
    assert result.chance_agreement == pytest.approx(0.25)
    assert result.pair_predictability == pytest.approx(0.25)


def test_error_agreement_preserves_prefiltered_output_categories():
    edge_one = ("wrong_edge_one", ("u",))
    edge_two = ("wrong_edge_two", ("v",))
    categories_a = [edge_one, edge_two, edge_two, ABSTAIN_CATEGORY]
    categories_b = [edge_one, edge_one, edge_two, ABSTAIN_CATEGORY]

    result = error_agreement(categories_a, categories_b)

    assert isinstance(result, ErrorAgreement)
    assert result.observed_agreement == pytest.approx(0.75)
    assert result.chance_agreement == pytest.approx(0.3125)
    assert result.error_agreement == pytest.approx(0.4375)
    assert result.n_items == 4


def test_error_agreement_rejects_empty_prefiltered_inputs():
    with pytest.raises(ValueError, match="prefiltered category"):
        error_agreement([], [])


def test_error_agreement_signature_accepts_categories_only():
    signature = inspect.signature(error_agreement)

    assert list(signature.parameters) == ["error_categories_a", "error_categories_b"]


def test_transmission_comparison_is_pure_difference_dto():
    result = compare_transmission_conditions(off_metric=0.1, on_metric=0.4)

    assert isinstance(result, TransmissionComparison)
    assert result.off_value == pytest.approx(0.1)
    assert result.on_value == pytest.approx(0.4)
    assert result.delta == pytest.approx(0.3)


def test_hash_seed_does_not_change_pair_predictability():
    code = (
        "from abm.convergence import pair_predictability; "
        "cats_a=[('b',('2',)),('a',('1',)),('b',('2',)), 'ABSTAIN']; "
        "cats_b=[('b',('2',)),('c',('3',)),('b',('2',)), 'ABSTAIN']; "
        "r=pair_predictability(cats_a, cats_b); "
        "print(f'{r.observed_agreement:.12f},{r.chance_agreement:.12f},{r.pair_predictability:.12f},{r.n_items}')"
    )
    outputs = []
    for seed in ("1", "98765"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        outputs.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True).strip())

    assert outputs[0] == outputs[1]
