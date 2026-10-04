"""独立した比べの学び手の情報の渡し方と時点を検査する。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/verb"))
from exception_learner import ExceptionLearner, run_sequence


def test_feedback_is_registered_after_answer():
    result = run_sequence([
        {"trial": 0, "verb": "x", "past_asked": True, "observed_past": "IRR_1"},
        {"trial": 1, "verb": "x", "past_asked": True, "observed_past": None}], [])
    assert [r["answer"] for r in result["answers"]] == ["REG", "IRR_1"]


def test_hidden_without_disclosure_does_not_register():
    result = run_sequence([
        {"trial": 0, "verb": "x", "past_asked": True, "observed_past": None},
        {"trial": 1, "verb": "x", "past_asked": True, "observed_past": None}], [])
    assert result["dictionary"] == {}


def test_visible_example_is_available_to_next_probe():
    result = run_sequence([{ "trial": 0, "verb": "x", "past_asked": False, "observed_past": "IRR_1"}],
                          [{"t": 1, "verb": "x"}, {"t": 1, "verb": "new"}])
    assert [r["answer"] for r in result["probes"]] == ["IRR_1", "REG"]
    assert result["dictionary"] == {"x": "IRR_1"}


def test_no_forgetting_and_regular_observation_does_not_overwrite():
    learner = ExceptionLearner()
    learner.observe("x", "IRR_2")
    learner.observe("x", None)
    learner.observe("x", "REG")
    assert learner.predict("x") == "IRR_2"


def test_prediction_does_not_update():
    learner = ExceptionLearner()
    for name in ("x", "new", "new"):
        learner.predict(name)
    assert learner.exceptions == {}
