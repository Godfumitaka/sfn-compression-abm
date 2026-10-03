"""選び方 N3（tools/selectn3.py）の小さな例。2026-10-02 夜の委任書の関門 3。
例の場面：物 a・b・c。見えている関係 s1＝fold(a,b)、s2＝lock(b,c)、s3＝cause(s1,s2)。伏せた関係 hid（場面には無い）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from dataclasses import make_dataclass
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import selectn3 as N  # noqa: E402
import v39  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

SCENE = RelationGraph("x", (Entity("a"), Entity("b"), Entity("c")),
                      (Relation("s1", "fold", ("a", "b")), Relation("s2", "lock", ("b", "c")), Relation("s3", "cause", ("s1", "s2"))))
EM = {"x": "a", "y": "b", "z": "c"}


def al(rm, em=EM):
    return SimpleNamespace(relation_mapping=rm, entity_mapping=em)


def same_def():
    return T.definition(T.row(0, "fold", ("x", "y"), rid="r1"), T.row(1, "lock", ("y", "z"), rid="r2"),
                        T.row(2, "cause", ("r1", "r2"), rid="r3"))


HIST = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"cause": 1}}
ID = {"r1": "s1", "r2": "s2", "r3": "s3"}


def test_1_same_representation_is_one():
    T.setup()
    t = N.n3_terms(same_def(), HIST, al(ID), SCENE)
    assert t == (3, 6, 2, 11, 11) and N.n3_value(t) == 1


def test_2_U_name_gets_no_point():
    T.setup()
    d = T.definition(T.row(0, "fold", ("x", "y"), rid="r1"), T.row(1, v39.ERASED, ("y", "z"), alive=False, rid="r2"),
                     T.row(2, "cause", ("r1", "r2"), rid="r3"))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 2): {"cause": 1}}            # r2 は履歴なし → U
    assert v39.seat_state(d, d.constituents[1], hist) == "U"
    name, arg, link, s_dd, s_xx = N.n3_terms(d, hist, al(ID), SCENE)
    assert name == 2                                                    # U の席の名前は 0 点
    assert arg == 6 and link == 2                                       # 構造（引数・つながり）は U も数える
    assert s_dd == 2 + 6 + 2                                            # 自己の点の名前も U は 0
    assert N.n3_value((name, arg, link, s_dd, s_xx)) < 1


def test_3_hidden_relation_name_not_used():
    T.setup()
    # 伏せた関係 hid に写った席：名前・引数・つながりのどれにも入らない。S(x,x) は見えている関係だけ
    d = T.definition(T.row(0, "fold", ("x", "y"), rid="r1"), T.row(1, "push", ("y", "z"), rid="r2"),
                     T.row(2, "cause", ("r1", "r2"), rid="r3"))
    a = al({"r1": "s1", "r2": "hid", "r3": "s3"})
    t1 = N.n3_terms(d, HIST, a, SCENE)
    d2 = T.definition(T.row(0, "fold", ("x", "y"), rid="r1"), T.row(1, "pull", ("y", "z"), rid="r2"),
                      T.row(2, "cause", ("r1", "r2"), rid="r3"))
    t2 = N.n3_terms(d2, HIST, a, SCENE)
    assert t1 == t2                                                     # 伏せた位置の席の名前を変えても同じ
    assert t1[4] == 3 + 6 + 2                                           # S(x,x)：見えている 3 本だけ
    assert t1[0] == 2                                                   # 名前は見えている関係に写った F の 2 席


def test_4_mismatch_not_in_numerator():
    T.setup()
    # r1 の引数の対応が逆（x→b, y→a）：引数の点が入らないだけで、減点はしない
    t = N.n3_terms(same_def(), HIST, al(ID, {"x": "b", "y": "a", "z": "c"}), SCENE)
    assert t[0] == 3 and t[1] == 3 and t[2] == 2                       # r1 は 0、r2 は z だけ 1、r3 は 2：引数 3（合わない 3 か所は入らない）
    base = N.n3_terms(same_def(), HIST, al(ID), SCENE)
    assert all(x <= y for x, y in zip(t[:3], base[:3]))                  # 合わない所は分子に入らない（増えも減点もしない）


def test_5_bounded_0_1():
    T.setup()
    rnd = random.Random(7)
    preds = ["fold", "lock", "cause", "wrap"]
    for _ in range(300):
        rows = []
        for k in range(rnd.randint(1, 4)):
            alive = rnd.random() < 0.6
            rows.append(T.row(k, rnd.choice(preds) if alive else v39.ERASED, (rnd.choice("xyz"), rnd.choice("xyz")), alive=alive, rid=f"r{k}"))
        if rnd.random() < 0.5 and len(rows) >= 2:
            rows.append(T.row(len(rows), "cause", ("r0", "r1"), rid=f"r{len(rows)}"))
        d = T.definition(*rows)
        hist = {("R_x", r.slot_index): {"fold": 1} for r in rows if rnd.random() < 0.5}
        rm = {r.relation.relation_id: rnd.choice(["s1", "s2", "s3", "hid"]) for r in rows if rnd.random() < 0.8}
        em = {v: rnd.choice("abc") for v in "xyz"}
        q = N.n3_value(N.n3_terms(d, hist, al(rm, em), SCENE))
        assert q is not None and 0 <= q <= 1


def test_6_selects_max_N3_not_ratio_and_gate_unchanged():
    T.setup()
    # 定義 A：一席だけ、支持の割合 1（1／1）・N3 は小さい。定義 B：三席、支持 2／3・N3 は大きい
    dA = T.definition(T.row(0, "fold", ("x", "y"), rid="a1"), name="R_A")
    dB = T.definition(T.row(0, "fold", ("x", "y"), rid="b1"), T.row(1, "lock", ("y", "z"), rid="b2"),
                      T.row(2, "cause", ("b1", "b2"), rid="b3"), name="R_B")
    st = T.state([dA, dB], {("R_A", 0): {"fold": 1}, ("R_B", 0): {"fold": 1}, ("R_B", 1): {"lock": 1}, ("R_B", 2): {"cause": 1}}, {})
    maps = {"R_A": al({"a1": "s1"}), "R_B": al({"b1": "s1", "b3": "s3"})}
    real = v39.map_v39
    Al = make_dataclass("Al", ["relation_mapping", "entity_mapping", "candidate_projections"])
    v39.map_v39 = lambda d, sh, sc: (None, Al(maps[d.name].relation_mapping, maps[d.name].entity_mapping, ()))
    try:
        cfg = SimpleNamespace(tau_acc=0.67)
        now = real_select(st, cfg)
        res = N.select_definition_n3(st, SCENE, cfg)
    finally:
        v39.map_v39 = real
    assert now == "R_A"                                                  # 今の規則は支持の割合 1 の A
    assert res[2].name == "R_B" and res[1] == 2 and res[5] == 3           # N3 は B（支持 2／3 のまま返す）
    import abm.agent_runtime as ar
    assert res[1] < ar._need(0.67, res[5])                              # 門は今のまま：2 ＜ ceil(0.67×3)＝3 なので、予測ではこのまま黙る（次点は探さない）
    assert [p["R"] for p in res[7]] == ["R_A"] and not res[7][0]["selected"]     # 門を通る定義の一覧は今と同じ作り（選ばれたのは B）


def real_select(st, cfg):
    return v39.select_definition(st, SCENE, cfg)[2].name


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
