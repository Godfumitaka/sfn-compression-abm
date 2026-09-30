"""U の照合（--u-struct）の小例（tools/ustruct.py。2026-09-30 の委任書「U の照合の直し…」の 1・4）。
例：定義は cause(r1, r2)（F）・r1＝hold(x,y)（U：墓石で履歴の鍵が無い）・r2＝brk(x,y)（F）。場面は hold(a,b)・brk(a,b)・cause(hold, brk)。
今の照合では、cause の子 r1 が U なので、hold が見えていると cause は写らない。--u-struct では写り、U の席 r1 の対応先が hold になる。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v310_be as E  # noqa: E402
import test_v39_budget as T  # noqa: E402
import abm.abstraction as ab  # noqa: E402
import histrole  # noqa: E402
import ustruct  # noqa: E402
import v39  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402


def defn(r1_args=("x", "y"), r1_pred="hold"):
    return T.definition(T.row(0, "cause", ("r1", "r2"), rid="c1"), T.row(1, r1_pred, r1_args, alive=False, rid="r1"),
                        T.row(2, "brk", ("x", "y"), rid="r2"), name="R_u")


def scene(parent="cause", first_arg="s1", hide=()):
    rels = [Relation("s1", "hold", ("a", "b")), Relation("s2", "brk", ("a", "b")), Relation("s3", "wrap", ("a", "b")),
            Relation("t1", parent, (first_arg, "s2"))]
    return RelationGraph("scene", (Entity("a"), Entity("b")), tuple(r for r in rels if r.relation_id not in hide))


def mapping(d, sc, u=True):
    undo = ustruct.install_matching() if u else (lambda: None)
    try:
        return v39.map_v39(d, {}, sc)[1]
    finally:
        undo()


def test_1_parent_maps_and_u_seat_gets_its_position():
    T.setup()
    d = defn()
    off = mapping(d, scene(), u=False)
    assert "c1" not in off.relation_mapping                     # 今：U の子の hold が見えているので親は写らない
    on = mapping(d, scene())
    assert on.relation_mapping.get("c1") == "t1" and on.relation_mapping.get("r1") == "s1" and on.relation_mapping.get("r2") == "s2"
    assert on.entity_mapping == {"x": "a", "y": "b"}


def test_2_arity_must_match():
    T.setup()
    assert "c1" not in mapping(defn(r1_args=("x",)), scene()).relation_mapping     # U の席の行が一項、場面の子は二項


def test_3_no_contradiction_with_entity_mapping():
    T.setup()
    al = mapping(defn(r1_args=("y", "x")), scene())                                # U の行の引数が逆：x→b・y→a を要する
    both = al.relation_mapping.get("c1") == "t1" and al.relation_mapping.get("r2") == "s2"
    assert not both                                                                # brk(x,y)→brk(a,b) と同時には採らない
    assert len(set(al.entity_mapping.values())) == len(al.entity_mapping)


def test_4_relation_is_not_matched_to_entity():
    T.setup()
    assert "c1" not in mapping(defn(), scene(first_arg="a")).relation_mapping       # 親の子の位置が物


def test_5_parent_name_condition_unchanged_and_hidden_child_as_before():
    T.setup()
    assert "c1" not in mapping(defn(), scene(parent="enable")).relation_mapping     # 名前の違う親には当てはまらない
    off = mapping(defn(), scene(hide=("s1",)), u=False)
    on = mapping(defn(), scene(hide=("s1",)))
    assert off.relation_mapping == on.relation_mapping and on.relation_mapping.get("c1") == "t1"   # 子が見えていなければ今のまま


def test_6_u_seat_not_in_support():
    T.setup()
    d = defn()
    al = mapping(d, scene())
    sup = sum(1 for row in d.constituents if v39.seat_state(d, row, {}) != "U" and row.relation.relation_id in al.relation_mapping)
    assert sup == 2 and v39.n_FH(d, {}) == 2                                       # 分子にも分母にも U の席は入らない


def test_7_m1_observes_u_seat_from_parent_position():
    T.setup()
    d = defn()
    st = T.state([d], {("R_u", 0): {"cause": 1}, ("R_u", 2): {"brk": 1}}, {})
    base = scene()
    sc = scene()
    new = histrole.make(ab.m1.__wrapped__ if hasattr(ab.m1, "__wrapped__") else ab.m1, real=False)
    from abm.sme import map_graphs
    orig_dg, orig_ext = ab._definition_graph, ab._extend_definition
    ab._definition_graph = lambda definition, mode="all": v39.v39_graph(definition, st.slot_history)
    ab._extend_definition = lambda old, pairs, state, trial, **k: old          # 本番の --extend-rule none と同じ（行を足さない）
    histrole.CFG["u_all_orders"] = True
    histrole.STATS.clear()
    histrole.STATS.update(histrole._stats_zero())
    al = map_graphs(base, sc).alignment                                         # 土台と今の場面の写し（m1 の材料）
    undo = ustruct.install_matching()
    try:
        out, reg = new(st, base, sc, al, 9, name="R_u", **E.KW)
        out_off = None
    finally:
        undo()
    try:
        histrole.CFG.clear()
        out_off, _ = new(st, base, sc, al, 9, name="R_u", **E.KW)
    finally:
        ab._definition_graph, ab._extend_definition = orig_dg, orig_ext
    assert reg is not None and reg["was_extension"]
    assert out.slot_history.get(("R_u", 1)) == {"hold": 1}                        # U の席に観察一回（覚え直しのきっかけ）
    assert ("R_u", 1) not in out_off.slot_history                                 # 旗なし：親が写らないので観察なし


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
