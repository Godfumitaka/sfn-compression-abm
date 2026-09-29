"""v3.10hs（旗 --score-role、tools/v310be.py の role_target・three_answers_role・score_answers_role）の小例。
2026-09-30 の追加・置換の指示 3 の最低限の検査 1・2・4（3 は T02、5 は旗なしの一致、6 は既存の検査で、走行・別の検査で確かめる）。
例：物 a・b の上に push と fold（同じ物の組）。定義は push(x,y)・fold(x,y) と、その親 cause(push, fold)。場面で push が伏せられ、開示される。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v310_be as E  # noqa: E402
import test_v39_budget as T  # noqa: E402
import v39  # noqa: E402
import v310be as B  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
from abm.sme import Alignment  # noqa: E402

DEF = T.definition(T.row(0, "push", ("x", "y"), rid="r_push"), T.row(1, "fold", ("x", "y"), rid="r_fold"),
                   T.row(2, "cause", ("r_push", "r_fold"), rid="r_c"), name="R_x")
# 場面：push（s_push）は伏せられて見えない。親 t_c は見えていて、引数に s_push の ID を持つ
SCENE = RelationGraph("scene", (Entity("a"), Entity("b")),
                      (Relation("s_fold", "fold", ("a", "b")), Relation("s_wrap", "wrap", ("a", "b")),
                       Relation("t_c", "cause", ("s_push", "s_fold"))))


def al(rm):
    return Alignment({"x": "a", "y": "b"}, rm, 0.0, {}, 0.0, 0, 0)


AL = al({"r_c": "t_c", "r_fold": "s_fold", "r_push": "s_push"})


def setup():
    E.setup()
    for k in ("score_role_scored", "score_role_scored_pos_differs", "score_role_other_target",
              "score_role_old_would_score_other", "score_role_old_would_score_no_target"):
        B.STATS[k] = 0


def items(alignment, st_=("F", "F", "F")):
    s = E.st([DEF], {}, {("R_x", i): E.seat(st_[i]) for i in range(3)})
    f = B.three_answers_role(v39.three_answers)
    return s, {"R": "R_x", "items": f(DEF, alignment, s, E.CONFIG, SCENE)}


def test_role_target():
    assert B.role_target(DEF, DEF.constituents[0], AL, SCENE) == ("s_push", None)
    assert B.role_target(DEF, DEF.constituents[1], AL, SCENE) == ("s_fold", None)
    assert B.role_target(DEF, DEF.constituents[2], AL, SCENE) == (None, "親が無い")


# 1 同じ物の組に push と fold があっても、push の開示で fold の席を採点しない
def test_1_other_seat_on_same_pair_not_scored():
    setup()
    s, ans = items(AL)
    assert ans["items"][1]["pos"] == ["a", "b"]                            # 物の組では fold の席も開示と同じ位置
    out_old, sc_old = B.score_answers(s.v39_seats, ans, Relation("s_push", "push", ("a", "b")), 11)
    assert {x[0] for x in sc_old} == {0, 1}                                  # 今の決め方：二席とも採点（混線）
    setup()
    out, sc = B.score_answers_role(s.v39_seats, ans, Relation("s_push", "push", ("a", "b")), 11)
    assert [x[0] for x in sc] == [0]                                         # 直した後：push の席だけ
    assert out[("R_x", 1)] is s.v39_seats[("R_x", 1)]                        # fold の席は全列不更新
    assert B.STATS["score_role_scored"] == 1 and B.STATS["score_role_other_target"] == 1
    assert B.STATS["score_role_old_would_score_other"] == 1


# 2 同じ役割の席で push と答え、正解が pull なら、外れとして採点する（正解の名前で対応を選び直さない）
def test_2_same_role_wrong_name_is_a_miss():
    setup()
    s, ans = items(AL)
    out, sc = B.score_answers_role(s.v39_seats, ans, Relation("s_push", "pull", ("a", "b")), 11)
    assert [x[0] for x in sc] == [0]
    lp = v39.code_lengths(T.p_hat(**E.PH))["pull"]
    RF, RH, RU, n = v39.rec_means(out[("R_x", 0)], 11)
    assert abs(RF - lp) < 1e-12 and n > 0                                    # F の答え push は外れ：r_F＝ℓ(pull)
    assert out[("R_x", 1)] is s.v39_seats[("R_x", 1)]                        # 名前の一致する別の席へ付け替えない


# 4 対応が分からない席には採点の証拠を足さない（物の組だけの判定に戻さない）
def test_4_unknown_target_gets_no_evidence():
    setup()
    s, ans = items(al({"r_fold": "s_fold", "r_push": "s_push"}))       # 親 cause が場面の関係に対応していない
    assert [it["cid_why"] for it in ans["items"]] == ["親が対応しない", "親が対応しない", "親が無い"]
    out, sc = B.score_answers_role(s.v39_seats, ans, Relation("s_push", "push", ("a", "b")), 11)
    assert sc == [] and all(out[k] is s.v39_seats[k] for k in s.v39_seats)
    assert B.STATS["score_role_no_target_一階_親が対応しない"] == 2
    assert B.STATS["score_role_old_would_score_no_target"] == 2            # 今の決め方なら二席とも採点していた


def test_4b_not_unique_gets_no_evidence():
    setup()
    d = T.definition(T.row(0, "push", ("x", "y"), rid="r_push"), T.row(1, "fold", ("x", "y"), rid="r_fold"),
                     T.row(2, "cause", ("r_push", "r_fold"), rid="r_c"), T.row(3, "cause", ("r_fold", "r_push"), rid="r_d"),
                     name="R_x")
    sc2 = RelationGraph("scene", SCENE.entities, SCENE.relations + (Relation("t_d", "cause", ("s_wrap", "s_push")),))
    a = al({"r_c": "t_c", "r_d": "t_d", "r_fold": "s_fold", "r_push": "s_push"})
    assert B.role_target(d, d.constituents[0], a, sc2) == ("s_push", None)      # 二つの親が同じ子を指す：一意
    assert B.role_target(d, d.constituents[1], a, sc2) == (None, "対応先が一意でない")   # s_fold と s_wrap


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
