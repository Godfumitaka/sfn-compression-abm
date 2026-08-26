from __future__ import annotations

import inspect

import pytest

from abm.feedback import evaluate_feedback_coin, f


def test_f_keeps_agent_and_time_signature() -> None:
    assert tuple(inspect.signature(f).parameters) == ("agent_id", "t")


def test_common_coin_is_reused_across_frequency_settings() -> None:
    low = evaluate_feedback_coin("agent", 7, 0.2, lambda agent_id, t: 0.1)
    high = evaluate_feedback_coin("agent", 7, 0.2, lambda agent_id, t: 0.3)

    assert low.u_t == high.u_t == 0.2
    assert low.f_setting == 0.1
    assert high.f_setting == 0.3
    assert low.f_fired is False
    assert high.f_fired is True


@pytest.mark.parametrize(("u_t", "setting"), ((-0.1, 0.2), (1.0, 0.2), (0.2, -0.1), (0.2, 1.1)))
def test_feedback_coin_rejects_invalid_probabilities(u_t: float, setting: float) -> None:
    with pytest.raises(ValueError):
        evaluate_feedback_coin("agent", 1, u_t, lambda agent_id, t: setting)
