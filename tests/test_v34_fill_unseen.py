"""v3.4 の穴埋めの直し（旗 --fill-unseen、tools/fillunseen.py）の小さな例（2026-09-27 委任書 1）。

見えている位置の墓石は埋めない／伏せ辺の位置（見えていない位置）の墓石は埋める／選んだ述語が見えている関係と同じでも埋めない。
旗オフ（abm.filling.fill_missing_slots）の動きも並べて確かめる（直しが変えるのは、見えている位置の席だけ）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fillunseen  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
from abm.filling import fill_missing_slots as fill_off  # noqa: E402

fill_on = fillunseen.fill_missing_slots
PRICE = FrozenPrice(1.0, 0, 0.0, 3)
P_HAT = FrequencyTable({"hold": 3, "push": 2, "allow": 1}, 6, 0.1, frozenset({"hold", "push", "allow"}))
# 見えている関係は push(a, b) だけ。伏せ辺の位置は (a, c) とする（場面に関係が無い）。
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")), (Relation("s1", "push", ("a", "b")),))
EMAP = {"x": "a", "y": "b", "z": "c"}


def _run(fill, definition, history, selection="most_frequent", rng=None, higher=frozenset()):
    return fill(definition, SCENE, EMAP, {}, history, P_HAT, selection, rng, higher_order_predicates=higher)


def test_tombstone_at_visible_position_is_not_filled() -> None:
    # 墓石 hold(x, y) を写すと (a, b)。そこには push(a, b) が見えている（述語は違う）。
    row = Constituent(0, 1, Relation("t0", "hold", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (row,), 0, 1)
    history = {("R", 0): frozenset({"hold"})}

    off = _run(fill_off, definition, history)
    on = _run(fill_on, definition, history)

    assert [(r.predicate, r.arguments) for r in off.relations] == [("hold", ("a", "b"))]  # 旗オフ：埋める
    assert on.relations == ()                                                           # 旗オン：埋めない
    assert on.candidate_distribution == () and on.slot_history_size == 0


def test_tombstone_at_held_out_position_is_filled() -> None:
    # 墓石 hold(x, z) を写すと (a, c)。そこには何も見えていない（伏せ辺の位置）。
    row = Constituent(0, 1, Relation("t0", "hold", ("x", "z")), PRICE, False)
    definition = NamedDefinition("R", (row,), 0, 1)
    history = {("R", 0): frozenset({"hold"})}

    off = _run(fill_off, definition, history)
    on = _run(fill_on, definition, history)

    assert [(r.predicate, r.arguments) for r in on.relations] == [("hold", ("a", "c"))]
    assert on == off                                                                    # 旗オン・オフで同じ


def test_chosen_predicate_equal_to_visible_relation_is_not_filled() -> None:
    # 墓石 hold(x, y) の席のメモ帳は push だけ。旗オフでは push(a, b) を作る（見えている push(a, b) の言い直し）。
    row = Constituent(0, 1, Relation("t0", "hold", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (row,), 0, 1)
    history = {("R", 0): frozenset({"push"})}

    off = _run(fill_off, definition, history)
    on = _run(fill_on, definition, history)

    assert [(r.predicate, r.arguments) for r in off.relations] == [("push", ("a", "b"))]
    assert on.relations == ()


def test_same_predicate_visible_is_unchanged() -> None:
    # 行の元の述語と同じ push(a, b) が見えているときは、今のまま（見えている関係を返し、埋めた行には入れない）。
    row = Constituent(0, 1, Relation("t0", "push", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (row,), 0, 1)
    history = {("R", 0): frozenset({"hold"})}

    assert _run(fill_on, definition, history) == _run(fill_off, definition, history)
    assert _run(fill_on, definition, history).relations == ()


def test_parent_of_unfilled_child_is_not_filled_and_rng_is_not_drawn() -> None:
    # 子（墓石 hold(x, y)、見えている位置）を埋めないので、子を引数に取る親 allow(t0, z) も埋まらない。
    # 抽出（sample）でも、埋めない席の分は乱数を引かない。
    child = Constituent(0, 1, Relation("t0", "hold", ("x", "y")), PRICE, False)
    parent = Constituent(1, 1, Relation("t1", "allow", ("t0", "z")), PRICE, False)
    definition = NamedDefinition("R", (child, parent), 0, 1)
    history = {("R", 0): frozenset({"hold", "push"}), ("R", 1): frozenset({"allow"})}

    off = _run(fill_off, definition, history, "sample", Random(3), frozenset({"allow"}))
    rng = Random(3)
    on = _run(fill_on, definition, history, "sample", rng, frozenset({"allow"}))

    assert len(off.relations) == 2
    assert on.relations == ()
    assert rng.random() == Random(3).random()
