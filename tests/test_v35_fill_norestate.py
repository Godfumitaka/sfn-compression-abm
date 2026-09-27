"""v3.5 の穴埋めの直し（旗 --fill-norestate、tools/fillnorestate.py、案 B）の小さな例（2026-09-27、control/判断_0927_1250.md の 1）。

選んだ述語が、写した位置で見えている関係と同じときだけ埋めない。同じ物の組にほかの関係が見えていても、選んだ述語が見えていなければ埋める。
旗オフ（abm.filling.fill_missing_slots）の動きも並べて確かめる。
"""

from __future__ import annotations

import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fillnorestate  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
from abm.filling import fill_missing_slots as fill_off  # noqa: E402

fill_on = fillnorestate.fill_missing_slots
PRICE = FrozenPrice(1.0, 0, 0.0, 3)
VISIBLE_AB = ("hold", "push", "carry", "lift", "drag", "lock", "bend")
PREDS = frozenset(VISIBLE_AB + ("pull", "allow"))
P_HAT = FrequencyTable({p: 1 for p in PREDS}, len(PREDS), 0.1, PREDS)
# 調べの係の試行 1 の例：伏せ辺は pull(a, b)。a と b の間には hold・push・carry・lift・drag・lock・bend が見えている。(a, c) には何も見えていない。
SCENE = RelationGraph(
    "scene", (Entity("a"), Entity("b"), Entity("c")),
    tuple(Relation(f"s_{p}", p, ("a", "b")) for p in VISIBLE_AB),
)
EMAP = {"x": "a", "y": "b", "z": "c"}


def _run(fill, definition, history, relation_mapping=None, selection="most_frequent", rng=None, higher=frozenset()):
    return fill(definition, SCENE, EMAP, relation_mapping or {}, history, P_HAT, selection, rng,
                higher_order_predicates=higher)


def test_held_out_position_with_other_visible_relations_is_filled() -> None:
    # 定義：生きている行 hold(x, y)（場面の hold に写る）、墓石の行 pull(x, y)（メモ帳 {pull}）。写しは x→a、y→b。
    live = Constituent(0, 1, Relation("r_hold", "hold", ("x", "y")), PRICE, True)
    tomb = Constituent(1, 1, Relation("r_pull", "pull", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (live, tomb), 1, 1)
    history = {("R", 1): frozenset({"pull"})}
    rmap = {"r_hold": "s_hold"}

    off = _run(fill_off, definition, history, rmap)
    on = _run(fill_on, definition, history, rmap)

    assert [(r.predicate, r.arguments) for r in off.relations] == [("pull", ("a", "b"))]   # 伏せ辺そのもの
    assert on == off                                                                      # 旗オンでも埋める（v3.4 の --fill-unseen は埋めなかった）


def test_chosen_predicate_visible_at_position_is_not_filled() -> None:
    # 墓石の行 pull(x, y) の席のメモ帳は push だけ。push(a, b) は見えている（言い直し）。
    tomb = Constituent(0, 1, Relation("r_pull", "pull", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"push"})}

    off = _run(fill_off, definition, history)
    on = _run(fill_on, definition, history)

    assert [(r.predicate, r.arguments) for r in off.relations] == [("push", ("a", "b"))]   # 旗オフ：言い直しを埋める
    assert on.relations == ()                                                              # 旗オン：埋めない
    assert on.candidate_distribution == off.candidate_distribution                        # 選ぶ段は今のまま（選び直さない）


def test_unseen_position_is_filled_as_before() -> None:
    # 墓石の行 pull(x, z) を写すと (a, c)。何も見えていない。
    tomb = Constituent(0, 1, Relation("r_pull", "pull", ("x", "z")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"push"})}

    on = _run(fill_on, definition, history)
    assert [(r.predicate, r.arguments) for r in on.relations] == [("push", ("a", "c"))]
    assert on == _run(fill_off, definition, history)


def test_same_original_predicate_visible_is_unchanged() -> None:
    # 行の元の述語と同じ push(a, b) が見えているときは、今のまま（見えている関係を返し、埋めた行には入れない）。
    tomb = Constituent(0, 1, Relation("r_push", "push", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"pull"})}

    assert _run(fill_on, definition, history) == _run(fill_off, definition, history)
    assert _run(fill_on, definition, history).relations == ()


def test_sample_draw_is_kept_and_restatement_is_dropped() -> None:
    # 抽出でも乱数の引きは今のまま。引いた述語が見えている関係と同じなら埋めない。
    tomb = Constituent(0, 1, Relation("r_pull", "pull", ("x", "y")), PRICE, False)
    definition = NamedDefinition("R", (tomb,), 0, 1)
    history = {("R", 0): frozenset({"push", "pull"})}
    for seed in range(20):
        r_off, r_on = Random(seed), Random(seed)
        off = _run(fill_off, definition, history, selection="sample", rng=r_off)
        on = _run(fill_on, definition, history, selection="sample", rng=r_on)
        assert r_off.random() == r_on.random()                                             # 引いた回数が同じ
        if off.relations[0].predicate == "pull":
            assert on == off                                                              # 見えていない述語は埋める
        else:
            assert off.relations[0].predicate == "push" and on.relations == ()           # 言い直しは埋めない
