"""比べの腕 C（旗 --fill-norestate --fill-exclude-visible、tools/fillnorestate.py の exclude_visible）の小さな例
（2026-09-27、control/判断_0927_1950.md の 5）。

席を写した位置で見えている述語を先に候補から外し、残りから選ぶ。見えている候補しか無ければ埋めない。
一番の候補が見えていない席は B（v3.5）と同じ。
"""

from __future__ import annotations

import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fillnorestate  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

PRICE = FrozenPrice(1.0, 0, 0.0, 3)
# 重み（λ＝0 では p̂）：push 4 > pull 3 > hold 2 > drag 1
P_HAT = FrequencyTable({"push": 4, "pull": 3, "hold": 2, "drag": 1}, 10, 0.1, frozenset({"push", "pull", "hold", "drag"}))
# 見えている関係：push(a, b)。(a, c) には何も見えていない。
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")), (Relation("s_push", "push", ("a", "b")),))
EMAP = {"x": "a", "y": "b", "z": "c"}


def _run(exclude, definition, history, selection="most_frequent", rng=None):
    fillnorestate.CFG["exclude_visible"] = exclude
    try:
        return fillnorestate.fill_missing_slots(definition, SCENE, EMAP, {}, history, P_HAT, selection, rng,
                                                higher_order_predicates=frozenset())
    finally:
        fillnorestate.CFG["exclude_visible"] = False


def _tomb(args=("x", "y")):
    return NamedDefinition("R", (Constituent(0, 1, Relation("r_t", "lift", args), PRICE, False),), 0, 1)


def test_top_candidate_visible_says_the_next_one() -> None:
    # メモ帳 {push, pull}。一番の候補 push は (a, b) で見えている。
    history = {("R", 0): frozenset({"push", "pull"})}
    b = _run(False, _tomb(), history)
    c = _run(True, _tomb(), history)
    assert b.relations == ()                                                        # B：push を選び、見えているので埋めない
    assert [(r.predicate, r.arguments) for r in c.relations] == [("pull", ("a", "b"))]   # C：push を外し、残りの一番上 pull を言う
    assert [x for x, _ in c.candidate_distribution[0]["candidates"]] == ["pull"]


def test_only_visible_candidates_is_not_filled() -> None:
    history = {("R", 0): frozenset({"push"})}
    c = _run(True, _tomb(), history)
    assert c.relations == () and c.candidate_distribution[0]["candidates"] == []
    assert _run(False, _tomb(), history).relations == ()


def test_top_candidate_not_visible_is_same_as_b() -> None:
    # メモ帳 {pull, hold}。一番の候補 pull は見えていない。
    history = {("R", 0): frozenset({"pull", "hold"})}
    assert _run(True, _tomb(), history) == _run(False, _tomb(), history)
    assert [(r.predicate, r.arguments) for r in _run(True, _tomb(), history).relations] == [("pull", ("a", "b"))]


def test_unseen_position_is_unchanged() -> None:
    # (a, c) には何も見えていない：外す述語が無いので B と同じ。
    history = {("R", 0): frozenset({"push", "pull"})}
    assert _run(True, _tomb(("x", "z")), history) == _run(False, _tomb(("x", "z")), history)
    assert _run(True, _tomb(("x", "z")), history).relations[0].predicate == "push"


def test_sample_draws_from_the_rest_in_proportion() -> None:
    # 抽出：残り（pull 3・hold 2）の割合で引く。push は引かれない。
    history = {("R", 0): frozenset({"push", "pull", "hold"})}
    c = _run(True, _tomb(), history, "sample", Random(0))
    assert c.candidate_distribution[0]["candidates"] == [["hold", 0.4], ["pull", 0.6]]
    got = {_run(True, _tomb(), history, "sample", Random(s)).relations[0].predicate for s in range(40)}
    assert got == {"pull", "hold"}
