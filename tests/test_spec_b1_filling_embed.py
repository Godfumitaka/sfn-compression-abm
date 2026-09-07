"""SPEC B1 の slot_history・充填B・fan_out の構造回帰試験。"""

from __future__ import annotations

from abm.definition import Constituent, EmbedState, FrequencyTable, FrozenPrice, NamedDefinition
from abm.deletion import _embed_immediately_before_deletion
from abm.domains import AgentState, Entity, Relation, RelationGraph
from abm.filling import fill_missing_slots, observe_slot


PRICE = FrozenPrice(1.0, 0, 0.0, 3)


def test_slot_history_is_shared_by_position_across_registrations() -> None:
    history = observe_slot({}, "R", 2, "carry")
    history = observe_slot(history, "R", 2, "lift")

    assert history == {("R", 2): frozenset({"carry", "lift"})}


def test_dangling_dependency_is_filled_before_its_parent() -> None:
    child = Constituent(0, 1, Relation("child", "hold", ("x", "y")), PRICE, False)
    parent = Constituent(1, 1, Relation("parent", "allow", ("child", "z")), PRICE)
    definition = NamedDefinition("R", (child, parent), 2, 1)
    target = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")), ())
    p_hat = FrequencyTable(
        {"hold": 3, "allow": 2}, 5, 0.1, frozenset({"hold", "allow"})
    )

    result = fill_missing_slots(
        definition,
        target,
        {"x": "a", "y": "b", "z": "c"},
        {},
        {("R", 0): frozenset({"hold"}), ("R", 1): frozenset({"allow"})},
        p_hat,
    )

    assert [relation.predicate for relation in result.relations] == ["hold", "allow"]
    assert result.relations[1].arguments == (result.relations[0].relation_id, "c")
    assert result.source_by_slot == ("slot_history", "slot_history")


def test_recursive_filling_rejects_cycles() -> None:
    left = Constituent(0, 1, Relation("left", "p", ("right",)), PRICE, False)
    right = Constituent(1, 1, Relation("right", "q", ("left",)), PRICE, False)
    definition = NamedDefinition("R", (left, right), 2, 1)
    p_hat = FrequencyTable({"p": 1, "q": 1}, 2, 0.1, frozenset({"p", "q"}))

    try:
        fill_missing_slots(
            definition,
            RelationGraph("scene"),
            {},
            {},
            {("R", 0): frozenset({"p"}), ("R", 1): frozenset({"q"})},
            p_hat,
        )
    except ValueError as error:
        assert str(error) == "def(R) の充填依存に循環がある"
    else:
        raise AssertionError("循環する def(R) が充填された")


def test_fan_out_counts_only_live_referenced_relations() -> None:
    first = Constituent(0, 1, Relation("first", "cause", ("a", "b")), PRICE)
    deleted = Constituent(1, 1, Relation("deleted", "require", ("a", "b")), PRICE, False)
    parent = Constituent(
        2, 1, Relation("parent", "allow", ("first", "deleted", "entity")), PRICE
    )
    definition = NamedDefinition("R", (first, deleted, parent), 3, 1)
    state = AgentState(
        definitions={"R": definition},
        embed={
            ("R", row.slot_index, row.registered_at): EmbedState(row.slot_index, 99.0, 99.0)
            for row in definition.constituents
        },
    )

    embed = _embed_immediately_before_deletion(state)

    assert embed[("R", 2, 1)] == EmbedState(2, 1.0, 0.0)
    assert embed[("R", 0, 1)] == EmbedState(0, 0.0, 0.0)
