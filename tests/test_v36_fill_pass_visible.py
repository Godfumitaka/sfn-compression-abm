"""v3.6 の穴埋めの直し（旗 --fill-norestate --fill-pass-visible、tools/fillnorestate.py の pass_visible）の小さな例
（2026-09-27、control/判断_0927_1630.md の 1）。

言い直しで埋めなかった席の見えている関係を、その席を引数に持つ高階の行に子として渡す。
選んだ述語が見えていない席は B（v3.5）と同じ。行の元の述語が見えている場合は今のまま。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fillnorestate  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
from abm.filling import fill_missing_slots as fill_off  # noqa: E402

PRICE = FrozenPrice(1.0, 0, 0.0, 3)
PREDS = frozenset({"hold", "push", "pull", "allow"})
P_HAT = FrequencyTable({p: 1 for p in PREDS}, len(PREDS), 0.1, PREDS)
# 見えている関係：push(a, b)（s_push）と hold(a, b)（s_hold）。(a, c) には何も見えていない。
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")),
                      (Relation("s_push", "push", ("a", "b")), Relation("s_hold", "hold", ("a", "b"))))
EMAP = {"x": "a", "y": "b", "z": "c"}
HIGHER = frozenset({"allow"})


def _run(pass_visible, definition, history):
    fillnorestate.CFG["pass_visible"] = pass_visible
    try:
        return fillnorestate.fill_missing_slots(definition, SCENE, EMAP, {}, history, P_HAT,
                                                higher_order_predicates=HIGHER)
    finally:
        fillnorestate.CFG["pass_visible"] = False


@pytest.fixture
def parent_definition():
    # 子：墓石の行 pull(x, y)（メモ帳 {push}、写すと (a, b)、push(a, b) は見えている）。親：墓石の行 allow(子, z)（メモ帳 {allow}）。
    child = Constituent(0, 1, Relation("r_child", "pull", ("x", "y")), PRICE, False)
    parent = Constituent(1, 1, Relation("r_parent", "allow", ("r_child", "z")), PRICE, False)
    return NamedDefinition("R", (child, parent), 0, 1), {("R", 0): frozenset({"push"}), ("R", 1): frozenset({"allow"})}


def test_parent_uses_visible_relation_as_child(parent_definition) -> None:
    definition, history = parent_definition
    v35 = _run(False, definition, history)
    v36 = _run(True, definition, history)
    off = fill_off(definition, SCENE, EMAP, {}, history, P_HAT, higher_order_predicates=HIGHER)

    assert [(r.predicate, r.arguments) for r in off.relations][0] == ("push", ("a", "b"))   # 旗オフ：子を言い直しで埋め、親はその子を使う
    assert off.relations[1].predicate == "allow" and off.relations[1].arguments[1] == "c"
    assert v35.relations == ()                                                              # v3.5：子を埋めないので、親も埋まらない
    assert [(r.predicate, r.arguments) for r in v36.relations] == [("allow", ("s_push", "c"))]   # v3.6：親が見えている関係 push(a,b) を子に使う
    assert v36.slot_indices == (1,)                                                         # 子の席は埋めた行に入らない


def test_chosen_predicate_not_visible_is_same_as_b() -> None:
    # 墓石の行 pull(x, y) のメモ帳は {pull}。pull(a, b) は見えていない（同じ組に push・hold は見えている）→ 埋める。
    tomb = Constituent(0, 1, Relation("r_pull", "pull", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"pull"})}
    v36 = _run(True, definition, history)
    assert [(r.predicate, r.arguments) for r in v36.relations] == [("pull", ("a", "b"))]
    assert v36 == _run(False, definition, history)


def test_restated_slot_without_parent_is_not_filled() -> None:
    # 親の無い言い直しの席は、v3.6 でも埋めた行に入らない（予測にならない）。
    tomb = Constituent(0, 1, Relation("r_pull", "pull", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"push"})}
    assert _run(True, definition, history).relations == ()
    assert _run(True, definition, history) == _run(False, definition, history)


def test_original_predicate_visible_is_unchanged(parent_definition) -> None:
    # 子の行の元の述語 push が見えている（abm/filling.py:190-200 の今の扱い）：旗オフ・v3.5・v3.6 で同じ。
    child = Constituent(0, 1, Relation("r_child", "push", ("x", "y")), PRICE, False)
    parent = Constituent(1, 1, Relation("r_parent", "allow", ("r_child", "z")), PRICE, False)
    definition = NamedDefinition("R", (child, parent), 0, 1)
    history = {("R", 0): frozenset({"pull"}), ("R", 1): frozenset({"allow"})}
    off = fill_off(definition, SCENE, EMAP, {}, history, P_HAT, higher_order_predicates=HIGHER)
    assert _run(True, definition, history) == off
    assert _run(False, definition, history) == off
    assert [(r.predicate, r.arguments) for r in off.relations] == [("allow", ("s_push", "c"))]
