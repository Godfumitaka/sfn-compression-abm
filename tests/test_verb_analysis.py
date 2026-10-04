"""研究者側の分母・欠測・時間順序を検査する。模型の誤答方向は検査しない。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/verb"))
from analyze import count_answer, rates, recovery_step
from collections import Counter


def test_denominators_include_only_correct_and_reg():
    c = Counter()
    for answer in ("IRR_2", "REG", None, "IRR_3", "REG"):
        count_answer(c, answer, "IRR_2")
    r = rates(c)
    assert r["queries"] == 5
    assert r["marcus_denominator"] == 3
    assert r["marcus_rate"] == 2 / 3
    assert r["REG_all_queries_rate"] == 2 / 5


def test_no_observation_is_missing_not_zero():
    assert rates(Counter())["marcus_rate"] is None
    assert rates(Counter(abstain=3, queries=3))["marcus_rate"] is None


def test_recovery_is_ordered_and_nonoverlapping():
    state = {}
    stream = [(0, "REG"), (1, "correct"), (2, "correct"), (3, "other"),
              (4, "REG"), (5, "REG"), (6, "other"), (7, "correct"), (8, "correct")]
    events = [e for t, label in stream if (e := recovery_step(state, t, label)) is not None]
    assert events == [[2, 4, 7]]


def test_response_counts_partition_queries():
    c = Counter()
    for answer in (None, "REG", "IRR_1", "IRR_7", "push"):
        count_answer(c, answer, "IRR_1")
    assert sum(c[k] for k in ("correct", "REG", "abstain", "other")) == c["queries"]
