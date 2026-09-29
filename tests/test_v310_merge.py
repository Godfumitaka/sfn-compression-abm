"""v3.10 E（旗 --v310-merge、tools/v310merge.py）の小例（委任書「D と E」第 2 部の 3 検査）。
走行を使う検査（旗なしで v3.10 と同じ・T02）は tools/v310_checks/ で別に確かめる。
例：定義一つ R_x（F fold(x,y) 履歴 {fold:2, wrap:1}、F lock(y,z) 履歴 {lock:1}、H push(x,z) 履歴 {push:1}）、
    場面の共通構造 C＝fold(a,b)・lock(b,c)・pull(a,c)。全体の表 fold 5・wrap 3・lock 2・push 1・pull 1（計 12）。
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import v39  # noqa: E402
import v310merge as E  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

C = RelationGraph("commons", (Entity("a"), Entity("b"), Entity("c")),
                  (Relation("s_fold", "fold", ("a", "b")), Relation("s_lock", "lock", ("b", "c")),
                   Relation("s_pull", "pull", ("a", "c"))))
PH = dict(fold=5, wrap=3, lock=2, push=1, pull=1)
OPTS = "q1=a,q2=a,q3=a,q4=a,q5=a,q6=a"


def setup(alpha=1.0, select="argmin", opts=OPTS):
    T.setup()
    for d in (E.STATS, E.CFG, E.CTX):
        d.clear()
    E.CFG.update(seed=1, alpha=alpha, select=select, opts=E.parse_opts(opts))
    E.STATS.update(calls=0, commons_lt2=0, chose_new=0, chose_existing=0, ties=0, new_excluded=0, use_counted=0, assim_counted=0)
    return E._install_state_class()


def make_state(cls, defs, hist, pres=None, seats=None):
    return cls(definitions={d.name: d for d in defs}, slot_history=hist, p_hat=T.p_hat(**PH), v39_seats=seats or {},
               v310_pres=pres or {})


def the_def():
    return T.definition(T.row(0, "fold", ("x", "y")), T.row(1, "lock", ("y", "z")), T.row(2, "push", ("x", "z"), alive=False))


HIST = {("R_x", 0): {"fold": 2, "wrap": 1}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 1}}


# 費用の手計算（定義一つ、場面一つ）
def test_01_cost_existing_by_hand():
    cls = setup()
    st = make_state(cls, [the_def()], HIST)
    L = v39.code_lengths(st.p_hat)
    c, parts, mapped = E.cost_existing(st, st.definitions["R_x"], C, 1, 10, L, {r.relation_id for r in C.relations})
    assert mapped == {0, 1}                                       # fold・lock が写り、H の push は C の pull に写らない
    choose = -math.log2(1 / (1 + 1))                              # n_k＝1、N＝1、α＝1 → 1 ビット
    fit = -math.log2((2 + 5 / 12) / (3 + 1)) - math.log2((1 + 2 / 12) / (1 + 1))
    absent = -math.log2(1 - 0.5)                                  # 記録なし：p_在＝0.5／1＝0.5 → 1 ビット
    unm = 4 + (3 + 2 * (1 + 2))                                   # L(pull)＝ceil(log2 12)＝4、I(2)＝3、物 3 つ → ceil(log2 3)＝2
    assert abs(parts["選ぶ"] - choose) < 1e-12 and abs(parts["当てはまり"] - fit) < 1e-12
    assert parts["無い席"] == absent and parts["写らない関係"] == unm
    assert abs(c - (choose + fit + unm + absent)) < 1e-12


def test_02_cost_new_by_hand():
    setup()
    rows = [Relation("b_fold", "fold", ("a", "b")), Relation("b_lock", "lock", ("b", "c"))]
    L = v39.code_lengths(T.p_hat(**PH))
    c, parts = E.cost_new(rows, 1, L)
    # 構造：ceil(log2 100)＝7 ＋ I(2)＝3 ＋ I(3)＝5 ＋ 2 行 × (I(2)＝3 ＋ 2 × (1 ＋ 2))＝18 → 33
    # 席：2 ＋ Hcost(I(1)＋L＋I(1)) ＋ 指定 I(1)。fold L＝2 → 2＋8＋3＝13、lock L＝3 → 2＋9＋3＝14
    assert parts["定義のビット"] == 33 + 13 + 14
    assert parts["選ぶ"] == 1.0 and c == 61.0


def test_03_all_terms_finite_with_unseen_predicate():
    cls = setup()
    st = make_state(cls, [the_def()], HIST)
    L = v39.code_lengths(st.p_hat)
    C2 = RelationGraph("c2", C.entities, C.relations + (Relation("s_new", "never_seen", ("c", "a")),))
    c, parts, _ = E.cost_existing(st, st.definitions["R_x"], C2, 1, 10, L, {r.relation_id for r in C2.relations})
    assert all(math.isfinite(v) for v in parts.values()) and math.isfinite(c)
    c_new, parts_new = E.cost_new([Relation("n1", "never_seen", ("a", "b")), Relation("n2", "fold", ("b", "c"))], 1, L)
    assert math.isfinite(c_new) and all(math.isfinite(v) for v in parts_new.values())
    # 在った・数えたが多くても有限（p_在 ＜ 1）
    rec = E.PresRec(0, 10, (1e9,) * 16, (1e9,) * 16)
    assert math.isfinite(-math.log2(1 - E.p_present(rec, 10)))


def _choice_inputs(cls, defs, hist):
    import abm.sme as sme
    # 共通構造は構造の行（高階の関係とその子）だけなので、cause(fold, lock) を置く
    base = RelationGraph("base", (Entity("p"), Entity("q"), Entity("r")),
                         (Relation("b_fold", "fold", ("p", "q")), Relation("b_lock", "lock", ("q", "r")),
                          Relation("b_cause", "cause", ("b_fold", "b_lock"))))
    scene = RelationGraph("scene", C.entities, C.relations + (Relation("s_cause", "cause", ("s_fold", "s_lock")),))
    al = sme.map_graphs(base, scene).alignment
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base, "alignment": al})
    return make_state(cls, defs, hist), scene


# argmin は乱数を使わない。sample は世界の乱数（random の状態）を動かさず、同じ種・試行で同じ選択
def test_04_argmin_no_rng_sample_reproducible():
    import v32  # noqa: F401
    cls = setup()
    st, scene = _choice_inputs(cls, [the_def()], HIST)
    real = E.Random
    E.Random = lambda *a, **k: (_ for _ in ()).throw(AssertionError("argmin で乱数を作った"))
    try:
        r1 = E.choose(st, scene, 10)
    finally:
        E.Random = real
    side = E.CTX["side"]
    assert side["n_opts"] == 2 and side["new_ok"]
    import v32
    assert [r.predicate for r in v32.commons_graph(scene, v39.CTX["output"]).relations] == ["fold", "lock", "cause"]
    assert r1 == min(side["costs"], key=lambda x: x[1])[0]
    setup(select="sample")
    st, scene = _choice_inputs(cls, [the_def()], HIST)
    g0 = random.getstate()
    picks = [E.choose(st, scene, t) for t in range(20)]
    assert random.getstate() == g0
    assert picks == [E.choose(st, scene, t) for t in range(20)]


# 在った・数えた：使われた席を数え、写った席は在った。U→H の覚え直し（世代が変わる）では q2 に従う
def test_05_presence_counts_and_relearn():
    cls = setup()
    st = make_state(cls, [the_def()], HIST, seats={("R_x", s): v39.SeatRec(0, "F", 3, 3, v39.ZERO4, v39.ZERO4) for s in range(3)})
    da = SimpleNamespace(relation_mapping={"r0": "s_fold"})
    out = SimpleNamespace(trace={"R_used": "R_x", "definition_alignment": da})
    st2 = E.count_use(st, out, C, 10)
    pr0, cn0 = E.pres_values(st2.v310_pres[("R_x", 0)], 10)
    pr1, cn1 = E.pres_values(st2.v310_pres[("R_x", 1)], 10)
    ok = lambda x, y: abs(x - y) < 1e-12  # noqa: E731
    assert ok(pr0, 1.0) and ok(cn0, 1.0) and pr1 == 0.0 and ok(cn1, 1.0)   # 同じ試行は減衰なし・mean16 は重みの和 1
    assert ok(E.p_present(st2.v310_pres[("R_x", 0)], 10), 1.5 / 2.0)
    assert E.count_use(st2, out, C, 10) != st2                         # 呼ぶたびに数える（決まった入力だけで決まる）
    assert E.count_use(st, out, C, 10) == st2                          # 同じ入力なら同じ結果
    relearned = {**st2.v39_seats, ("R_x", 0): v39.SeatRec(1, "H", 20, 20, v39.ZERO4, v39.ZERO4)}
    st3 = E.replace(st2, v39_seats=relearned)
    assert E.seat_rec(st3, "R_x", 0)[0] is None                        # q2＝a：0 から
    setup(opts="q1=a,q2=b,q3=a,q4=a,q5=a,q6=a")
    assert E.seat_rec(st3, "R_x", 0)[0].counted == st2.v310_pres[("R_x", 0)].counted   # q2＝b：持ち越す


# 共通構造が 2 行未満なら今までどおり（名前なし）
def test_06_commons_lt2_returns_none():
    import abm.sme as sme
    cls = setup()
    base = RelationGraph("base", (Entity("p"), Entity("q")), (Relation("b_fold", "fold", ("p", "q")),))
    scene = RelationGraph("scene", C.entities, C.relations)
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base, "alignment": sme.map_graphs(base, scene).alignment})
    assert E.choose(make_state(cls, [the_def()], HIST), scene, 10) is None and E.STATS["commons_lt2"] == 1


if __name__ == "__main__":
    for mode in ("uniform", "actr"):
        T.MODE["decay"] = mode
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn()
                print("ok", mode, name)
