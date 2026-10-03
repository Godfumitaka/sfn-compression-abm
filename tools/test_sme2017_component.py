"""論文から独立に書いた期待値と、採用した対応の構造検査。"""
from dataclasses import replace
from itertools import permutations
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from sme2017 import Graph, Matcher, Node, Settings, validate


def graph(entities, rows):
    return Graph(tuple(Node(e, "entity") for e in entities) +
                 tuple(Node(k, kind, frozenset({name}), tuple(args)) for k, kind, name, args in rows))


def paper_water():
    # Falkenhainer et al. 1989, Appendix B.1（印刷ページ53）。
    base = graph(("water", "beaker", "vial", "pipe"), [
        ("wflow", "relation", "flow", ("beaker", "vial", "water", "pipe")),
        ("pressure-beaker", "function", "pressure", ("beaker",)),
        ("pressure-vial", "function", "pressure", ("vial",)),
        (">pressure", "relation", "greater", ("pressure-beaker", "pressure-vial")),
        ("diameter-beaker", "function", "diameter", ("beaker",)),
        ("diameter-vial", "function", "diameter", ("vial",)),
        (">diameter", "relation", "greater", ("diameter-beaker", "diameter-vial")),
        ("cause-flow", "relation", "cause", (">pressure", "wflow")),
        ("flat-water", "attribute", "flat-top", ("water",)),
        ("liquid-water", "attribute", "liquid", ("water",)),
    ])
    target = graph(("coffee", "ice-cube", "bar", "heat"), [
        ("hflow", "relation", "flow", ("coffee", "ice-cube", "heat", "bar")),
        ("temp-coffee", "function", "temperature", ("coffee",)),
        ("temp-ice-cube", "function", "temperature", ("ice-cube",)),
        (">temperature", "relation", "greater", ("temp-coffee", "temp-ice-cube")),
        ("flat-coffee", "attribute", "flat-top", ("coffee",)),
        ("liquid-coffee", "attribute", "liquid", ("coffee",)),
    ])
    return base, target


def paper_solar():
    # 同 Appendix B.2（印刷ページ53–54）。and は相手に無いため照合されない。
    base = graph(("sun", "planet"), [
        ("mass-sun", "function", "mass", ("sun",)),
        ("mass-planet", "function", "mass", ("planet",)),
        (">mass", "relation", "greater", ("mass-sun", "mass-planet")),
        ("attracts", "relation", "attracts", ("sun", "planet")),
        ("revolve", "relation", "revolve-around", ("planet", "sun")),
        ("and1", "relation", "and", (">mass", "attracts")),
        ("cause-revolve", "relation", "cause", ("and1", "revolve")),
        ("temp-sun", "function", "temperature", ("sun",)),
        ("temp-planet", "function", "temperature", ("planet",)),
        (">temp", "relation", "greater", ("temp-sun", "temp-planet")),
        ("force-gravity", "relation", "gravity", ("mass-sun", "mass-planet")),
        ("why-attracts", "relation", "cause", ("force-gravity", "attracts")),
    ])
    target = graph(("nucleus", "electron"), [
        ("mass-n", "function", "mass", ("nucleus",)),
        ("mass-e", "function", "mass", ("electron",)),
        (">mass", "relation", "greater", ("mass-n", "mass-e")),
        ("attracts", "relation", "attracts", ("nucleus", "electron")),
        ("revolve", "relation", "revolve-around", ("electron", "nucleus")),
        ("q-electron", "function", "charge", ("electron",)),
        ("q-nucleus", "function", "charge", ("nucleus",)),
        (">charge", "relation", "opposite-sign", ("q-nucleus", "q-electron")),
        ("why-attracts", "relation", "cause", (">charge", "attracts")),
    ])
    return base, target


@pytest.mark.parametrize("fixture,entities,relations", [
    (paper_water,
     {"beaker": "coffee", "vial": "ice-cube", "water": "heat", "pipe": "bar"},
     {"wflow": "hflow", "pressure-beaker": "temp-coffee", "pressure-vial": "temp-ice-cube", ">pressure": ">temperature"}),
    (paper_solar, {"sun": "nucleus", "planet": "electron"},
     {"mass-sun": "mass-n", "mass-planet": "mass-e", ">mass": ">mass", "attracts": "attracts", "revolve": "revolve"}),
])
def test_paper_final_mappings(fixture, entities, relations):
    left, right = fixture()
    result = Matcher().match(left, right)
    assert validate(left, right, result)
    assert dict(result.best.entity_mapping) == entities
    assert dict(result.best.relation_mapping) == relations
    if fixture is paper_water:
        expected = ("cause-flow", ("relation", ("cause",), (("mapped", ">temperature"), ("mapped", "hflow"))))
        assert expected in result.best.inferences


def fixture(prefix, variant):
    entities = tuple(prefix + k for k in ("u", "a", "b", "v", "o"))
    u, a, b, v, o = entities
    rows = [("p", "fold", (u, a)), ("r", "fold", (u, b)),
            ("cueA", "break", (a if variant == "A" else b, v)),
            ("cueB", "break_b", (b if variant == "A" else a, v)),
            ("anchor", "carry", (o, a)), ("other1", "lift", (v, o)),
            ("other2", "press", (o, u))]
    return graph(entities, [(prefix + k, "relation", name, args) for k, name, args in rows])


def independent_exact_maps(left, right):
    # 照合器の候補作成・点を使わない五物の全列挙。
    le = [n.key for n in left.nodes if n.kind == "entity"]
    re = [n.key for n in right.nodes if n.kind == "entity"]
    target = Counter((tuple(n.names), n.args) for n in right.nodes if n.kind != "entity")
    out = []
    for order in permutations(re):
        em = dict(zip(le, order))
        translated = Counter((tuple(n.names), tuple(em[a] for a in n.args)) for n in left.nodes if n.kind != "entity")
        if translated == target:
            out.append(em)
    return out


@pytest.mark.parametrize("variant", ["A", "B"])
def test_competitive_names_use_entity_connections(variant):
    left, right = fixture("d", variant), fixture("s", variant)
    result = Matcher().match(left, right)
    assert validate(left, right, result)
    exact = independent_exact_maps(left, right)
    assert len(exact) == 1
    assert dict(result.best.entity_mapping) == exact[0]
    assert len(result.best.relation_mapping) == 7
    other = fixture("s", "B" if variant == "A" else "A")
    assert not independent_exact_maps(left, other)
    assert Counter(n.names for n in right.nodes) == Counter(n.names for n in other.nodes)


def test_h_names_once_and_one_to_one():
    left = Graph((Node("a", "entity"), Node("h", "relation", frozenset({"p", "q"}), ("a",), "H")))
    right = Graph((Node("b", "entity"), Node("h2", "relation", frozenset({"q", "r"}), ("b",), "H")))
    m = Matcher()
    result = m.match(left, right)
    assert validate(left, right, result)
    assert dict(result.best.relation_mapping) == {"h": "h2"}
    self_result = m.match(left, left)
    assert validate(left, left, self_result)
    assert sum(local for _, _, local, _ in self_result.best.breakdown) == Settings().same_functor
    assert m.self_score(left) == self_result.best.score


@pytest.mark.parametrize("u_parent", [False, True])
def test_u_structure_and_named_children(u_parent):
    leaf = Node("leaf", "relation", frozenset({"p"}) if u_parent else frozenset(), ("a",), "F" if u_parent else "U")
    parent = Node("parent", "relation", frozenset() if u_parent else frozenset({"cause"}), ("leaf",), "U" if u_parent else "F")
    left = Graph((Node("a", "entity"), leaf, parent))
    right = graph(("b",), [("l", "relation", "p", ("b",)), ("c", "relation", "cause", ("l",))])
    result = Matcher().match(left, right)
    assert validate(left, right, result)
    assert dict(result.best.relation_mapping) == {"leaf": "l", "parent": "c"}
    assert sum(local for _, _, local, _ in result.best.breakdown) == Settings().same_functor


def test_unknown_no_name_no_hidden_arguments():
    left = graph(("a",), [("l", "relation", "p", ("a",)), ("c", "relation", "cause", ("l",))])
    right = Graph((Node("hole", "unknown", args=None), Node("c2", "relation", frozenset({"cause"}), ("hole",))))
    result = Matcher().match(left, right)
    assert validate(left, right, result)
    assert dict(result.best.relation_mapping) == {"c": "c2", "l": "hole"}
    assert result.best.entity_mapping == ()
    with pytest.raises(ValueError):
        Node("hole", "unknown", frozenset({"p"}), None)


def test_u_unknown_only_no_positive_evidence():
    left = Graph((Node("a", "entity"), Node("u", "relation", args=("a",), state="U")))
    right = Graph((Node("hole", "unknown", args=None),))
    assert Matcher().match(left, right).best is None


def rename(graph_, prefix, predicate_names):
    ids = {n.key: prefix + str(i * 7 + 5) for i, n in enumerate(reversed(graph_.nodes))}
    return Graph(tuple(replace(n, key=ids[n.key], names=frozenset(predicate_names[p] for p in n.names),
                               args=None if n.args is None else tuple(ids[a] for a in n.args))
                       for n in reversed(graph_.nodes))), ids


def test_renaming_and_input_order_unique_mapping():
    left, right = fixture("d", "A"), fixture("s", "A")
    names = {p: f"n{19-i}" for i, p in enumerate(sorted({p for n in left.nodes + right.nodes for p in n.names}))}
    l2, lm = rename(left, "L", names)
    r2, rm = rename(right, "R", names)
    old, new = Matcher().match(left, right), Matcher().match(l2, r2)
    assert validate(l2, r2, new)
    assert dict(new.best.entity_mapping) == {lm[a]: rm[b] for a, b in old.best.entity_mapping}
    assert dict(new.best.relation_mapping) == {lm[a]: rm[b] for a, b in old.best.relation_mapping}
    assert new.best.score == old.best.score


def test_repeat_snapshot_and_cache_keys():
    left, right = fixture("d", "A"), fixture("s", "A")
    matcher = Matcher()
    snap = matcher.snapshot()
    first = matcher.match(left, right)
    assert matcher.match(left, right) is first
    matcher.restore(snap)
    assert matcher.match(left, right) == first
    changed = Graph(tuple(replace(n, names=frozenset({"new"})) if n.key == "danchor" else n for n in left.nodes))
    matcher.match(changed, right)
    assert len(matcher.cache) == 2
    fresh = Matcher().match(changed, right)
    assert matcher.match(changed, right).best == fresh.best


def test_validator_rejects_entity_swap_and_double_h_score():
    left, right = fixture("d", "A"), fixture("s", "A")
    result = Matcher().match(left, right)
    c = result.best
    em = dict(c.entity_mapping)
    em["da"], em["db"] = em["db"], em["da"]
    bad = replace(result, candidates=(replace(c, entity_mapping=tuple(em.items())),))
    with pytest.raises(AssertionError):
        validate(left, right, bad)
    bad = replace(result, candidates=(replace(c, breakdown=c.breakdown + (c.breakdown[0],)),))
    with pytest.raises(AssertionError):
        validate(left, right, bad)


def test_repeated_unknown_reference_is_one_target():
    left = graph(("a",), [("l", "relation", "p", ("a",)), ("c", "relation", "cause", ("l", "l"))])
    right = Graph((Node("hole", "unknown", args=None), Node("c2", "relation", frozenset({"cause"}), ("hole", "hole"))))
    result = Matcher().match(left, right)
    assert validate(left, right, result)
    assert dict(result.best.relation_mapping) == {"c": "c2", "l": "hole"}


def test_true_tie_set_survives_renaming_and_cache():
    left = graph(("a",), [("l", "relation", "p", ("a",))])
    right = graph(("b", "c"), [("r1", "relation", "p", ("b",)), ("r2", "relation", "p", ("c",))])
    matcher = Matcher(tie_seed=17)
    result = matcher.match(left, right)
    assert validate(left, right, result)
    assert len(result.tied) == 2
    assert matcher.match(left, right) is result
    assert result.choices
    l2, lm = rename(left, "L", {"p": "renamed"})
    r2, rm = rename(right, "R", {"p": "renamed"})
    renamed = Matcher(tie_seed=17).match(l2, r2)
    assert {tuple(sorted((lm[a], rm[b]) for a, b in c.relation_mapping)) for c in result.candidates} == {
        c.relation_mapping for c in renamed.candidates}
    assert len(renamed.tied) == 2


@pytest.mark.parametrize("change", ["H_names", "U_state", "arguments", "settings"])
def test_cache_changes_with_each_required_state_item(change):
    left = Graph((Node("a", "entity"), Node("b", "entity"),
                  Node("l", "relation", frozenset({"p", "q"}), ("a", "b"), "H")))
    right = graph(("x", "y"), [("r", "relation", "p", ("x", "y"))])
    matcher = Matcher()
    first = matcher.match(left, right)
    if change == "settings":
        matcher.settings = replace(matcher.settings, trickle_down=16)
    else:
        row = left.by_id["l"]
        changed = {"H_names": replace(row, names=frozenset({"q"})),
                   "U_state": replace(row, names=frozenset(), state="U"),
                   "arguments": replace(row, args=("b", "a"))}[change]
        left = Graph(tuple(changed if n.key == "l" else n for n in left.nodes))
    new = matcher.match(left, right)
    assert len(matcher.cache) == 2
    fresh = Matcher(matcher.settings).match(left, right)
    assert new.best == fresh.best
    assert new is not first
