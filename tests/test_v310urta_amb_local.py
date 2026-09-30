"""候補ごとの棄権（--amb-local、tools/v39.py amb_blocks・fill_decision）の小例。2026-09-30 夕の指示の 2 の検査。
例の場面：物 a・b の上に fold(a,b)（見えている）。定義の物 x・y は a・b に写る。
全体の頻度は fold・wrap・lock・push・pull が同じ回数（U の席の型に合う名が同点になる）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import v39  # noqa: E402
from abm.domains import Abstain, EdgePrediction, Entity, Relation, RelationGraph  # noqa: E402

SCENE = RelationGraph("scene", (Entity("a"), Entity("b")), (Relation("s_fold", "fold", ("a", "b")),))
PH = T.p_hat(fold=2, wrap=2, lock=2, push=2, pull=2, cause=2)
HOP = frozenset({"cause"})


def fill(d, hist, rm=None):
    return v39.fill_v39(d, SCENE, {"x": "a", "y": "b"}, rm or {"r0": "s_fold"}, hist, PH, "most_frequent", None,
                        higher_order_predicates=HOP, local_lambda=1.0)


def setup(on):
    T.setup()
    v39.CFG["amb_local"] = on


def the_def(h_hist=None):
    # r0 fold（F、見えている）・r1 H（履歴で push が決まる／同点）・r2 U（型に合う名が同点）。r1 と r2 は同じ物の組 (x,y) の上
    d = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, v39.ERASED, ("x", "y"), alive=False, rid="r1"),
                     T.row(2, v39.ERASED, ("x", "y"), alive=False, rid="r2"), name="R_a")
    return d, {("R_a", 0): {"fold": 1}, ("R_a", 1): h_hist or {"push": 2}}


def test_1_other_seat_tie_does_not_stop_determined_H():
    setup(False)
    d, hist = the_def()
    f = fill(d, hist)
    assert f.ambiguous and [r.predicate for r in f.relations] == ["push"]      # U の席 r2 は同点で埋まらない。H の席 r1 は push
    setup(False)
    p, _ = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
    assert isinstance(p, Abstain) and p.reason == "ambiguous_projection"        # 今：答え全体が止まる
    setup(True)
    p, path = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
    assert isinstance(p, EdgePrediction) and p.edge.predicate == "push" and path == "filling_tombstone"
    # 同じ物の組 (a,b) の上にあるだけで、U の席の迷いを H の席にまとめない（上と同じ例）


def test_2_parent_not_a_candidate_when_needed_child_undetermined():
    setup(True)
    d = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, v39.ERASED, ("x", "y"), alive=False, rid="r1"),
                     T.row(2, "cause", ("r1", "r0"), rid="c1"), name="R_a")
    f = fill(d, {("R_a", 0): {"fold": 1}})                                     # r1 は U（同点）、c1 はそれに頼る親
    assert f.ambiguous and f.relations == ()
    p, _ = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
    assert isinstance(p, Abstain) and p.reason == "ambiguous_projection"        # 候補が無ければ今までどおり黙る


def test_3_tied_H_itself_gives_no_answer():
    setup(True)
    d, hist = the_def(h_hist={"push": 1, "lock": 1})                            # H 自身が同点
    f = fill(d, hist)
    assert f.relations == ()
    p, _ = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
    assert isinstance(p, Abstain)


def test_4_projection_priority_and_selection_unchanged():
    setup(False)
    d, hist = the_def()
    f = fill(d, hist)
    proj = EdgePrediction(Relation("sme_projection__r9", "wrap", ("a", "b")))
    for on in (False, True):
        setup(on)
        p, path = v39.fill_decision(proj, f, None)
        assert p is proj and path == "projection"                               # 投影があれば投影（今のまま）
    # 候補が二つあるときは、今と同じく最初に埋まった関係（席の番号の順）
    d2 = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, v39.ERASED, ("x", "y"), alive=False, rid="r1"),
                      T.row(2, v39.ERASED, ("y", "x"), alive=False, rid="r2"), T.row(3, v39.ERASED, ("x", "y"), alive=False, rid="r3"),
                      name="R_a")
    f2 = fill(d2, {("R_a", 0): {"fold": 1}, ("R_a", 1): {"push": 2}, ("R_a", 2): {"lock": 2}})
    assert f2.ambiguous and [r.predicate for r in f2.relations] == ["push", "lock"]
    setup(True)
    p, _ = v39.fill_decision(Abstain(reason="no_projectable_relation"), f2, None)
    assert p.edge.predicate == "push"


def test_5_off_is_unchanged_without_ambiguity():
    for on in (False, True):
        setup(on)
        d = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, v39.ERASED, ("x", "y"), alive=False, rid="r1"), name="R_a")
        f = fill(d, {("R_a", 0): {"fold": 1}, ("R_a", 1): {"push": 2}})
        assert not f.ambiguous
        p, path = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
        assert p.edge.predicate == "push" and path == "filling_tombstone"


def test_6_same_under_u_abstain():
    for on in (False, True):
        T.setup(u="abstain")
        v39.CFG["amb_local"] = on
        # r1 H は push で決まる・r2 H は同点・r3 U は常に棄権（埋めない）
        d = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, v39.ERASED, ("x", "y"), alive=False, rid="r1"),
                         T.row(2, v39.ERASED, ("y", "x"), alive=False, rid="r2"), T.row(3, v39.ERASED, ("x", "y"), alive=False, rid="r3"),
                         name="R_a")
        f = fill(d, {("R_a", 0): {"fold": 1}, ("R_a", 1): {"push": 2}, ("R_a", 2): {"lock": 1, "wrap": 1}})
        assert f.ambiguous and [r.predicate for r in f.relations] == ["push"]
        p, _ = v39.fill_decision(Abstain(reason="no_projectable_relation"), f, None)
        assert (isinstance(p, EdgePrediction) and p.edge.predicate == "push") if on else (p.reason == "ambiguous_projection")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
