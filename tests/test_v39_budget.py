"""v3.9（旗 --v39、tools/v39.py）の受入検査の小例（仕様 control/sfn_budget_implementation_spec_2026-09-29.md の 10 節 ①〜⑯）。
走行を使う検査（⑭ 有限／無限で同じ、⑮ 旗なしで v3.8 と同じ、⑯ 選択が一試行一回）は tools/v39_checks/ の台本で別に確かめる。
例の場面：物 a・b・c。見えている関係 fold(a,b)、lock(b,c)。写し x→a・y→b・z→c。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import v39  # noqa: E402
from abm.accounting import decay_ladder  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

PRICE = FrozenPrice(1.0, 0, 0.0, 3)
DICT = ["fold", "wrap", "lock", "push", "pull", "allow"]
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")),
                      (Relation("s_fold", "fold", ("a", "b")), Relation("s_lock", "lock", ("b", "c"))))
v39._install_candidates()
S39 = v39._state_class()


MODE = {"decay": "uniform"}   # ★ v3.10：同じ検査を --v39-decay actr でも通す（下の __main__ で両方回す）


def setup(budget=None, init="two", a=0.5, u="global", T=100, price=None):
    for d in (v39.STATS, v39.CFG, v39.CTX, v39.REG, v39._POW):
        d.clear()
    v39.CFG.update(seed=1, T=T, budget=budget, init=init, a=a, u_abstain=(u == "abstain"), decay=decay_ladder(T),
                   D=len(DICT), dict_index={p: i for i, p in enumerate(DICT)}, rho=None, argmax=False, commons=False)
    if MODE["decay"] == "actr":
        v39.CFG["mean_weights"] = v39.actr_weights(T)
    if price is not None:
        v39.CFG["price"] = price
    v39.CTX.update(struct_cache={}, births_rec=[], relearn=[], drift=[], cost_mismatch=[])


def p_hat(**counts):
    counts = counts or {"fold": 5, "wrap": 3, "lock": 2, "push": 1}
    return FrequencyTable(dict(counts), sum(counts.values()), 0.1, frozenset(counts))


def row(slot, pred, args, alive=True, rid=None):
    return Constituent(slot, 3, Relation(rid or f"r{slot}", pred, args), PRICE, alive)


def definition(*rows, name="R_x"):
    return NamedDefinition(name, tuple(rows), len(rows), 3)


def rec(st="F", sf=0.0, sh=0.0, su=0.0, e=0.0, t0=10):
    col = lambda v: (float(v),) * 16  # noqa: E731
    return v39.SeatRec(0, st, 3, t0, v39.ZERO4, (col(sf), col(sh), col(su), col(e)))


def state(defs, hist, seats, ph=None):
    return S39(definitions={d.name: d for d in defs}, slot_history=hist, p_hat=ph or p_hat(), v39_seats=seats)


# ① 同じ答えは差 0、写しが決まらない席は全列を更新しない
def test_01_same_answer_zero_difference_and_unknown_not_updated():
    setup()
    seats = {("R_x", 0): rec("F"), ("R_x", 1): rec("F")}
    ans = {"R": "R_x", "items": [
        {"slot": 0, "st": "F", "pos": ["a", "b"], "gen": 0, "ans": {"F": "wrap", "H": "wrap", "U": "fold"}},
        {"slot": 1, "st": "F", "pos": None, "gen": 0}]}
    out, scored = v39.score_answers(seats, ans, Relation("h", "wrap", ("a", "b")), 11)
    SF, SH, SU, E = v39.rec_means(out[("R_x", 0)], 11)
    assert SF == SH and SF > 0 and SU == 0.0 and E > 0          # 同じ答え：差 0
    assert out[("R_x", 1)] is seats[("R_x", 1)]                 # 写しが決まらない：全列そのまま
    assert scored == [[0, "F", 1, 1, 0]]


# ② 採点するのは、正解を見る前に作った三答え（控えた答え）
def test_02_scores_answers_made_before_disclosure():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1, "wrap": 3}, ("R_x", 1): {"lock": 1}}
    st = state([d], hist, {("R_x", 0): rec("F"), ("R_x", 1): rec("F")})
    al = SimpleNamespace(entity_mapping={"x": "a", "y": "b", "z": "c"}, relation_mapping={})
    cfg = SimpleNamespace(local_lambda=1.0, higher_order_predicates=frozenset())
    items = v39.three_answers(d, al, st, cfg, SCENE)
    assert items[0]["ans"]["H"] == "wrap"                       # 開示前の記憶での H の答え
    # 開示のあとで履歴が変わっても（学習）、控えた答えで採点する
    ans = {"R": "R_x", "items": items}
    out, scored = v39.score_answers(st.v39_seats, ans, Relation("h", "wrap", ("a", "b")), 11)
    assert scored[0] == [0, "F", 0, 1, 0]


# ③ 誕生の初期成績：材料を二重に数えない（履歴・全体頻度を変えない）。初期分と誕生後の分を分けて持つ
def test_03_birth_init_no_double_count_and_separate():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1, "push": 1}}
    st = state([d], hist, {})
    cfg = SimpleNamespace(local_lambda=1.0, higher_order_predicates=frozenset())
    v39.CTX["config"] = cfg
    before_hist = {k: dict(v) for k, v in st.slot_history.items()}
    before_counts = dict(st.p_hat.counts)
    r0 = v39._init_rec(d, d.constituents[0], st, SCENE, SCENE, trial=20, base_age=5, config=cfg)
    assert {k: dict(v) for k, v in st.slot_history.items()} == before_hist and dict(st.p_hat.counts) == before_counts
    assert r0.post == v39.ZERO4                                   # 誕生後の分は 0 から
    phi = v39.CFG["decay"]
    assert r0.init[3] == tuple(f ** 5 + 1.0 for f in phi)         # E ＝ φ^年齢 ＋ 1（実効 2 回とはしない）
    assert r0.init[0] == tuple(f ** 5 + 1.0 for f in phi)         # F は二場面とも 1
    setup(init="zero")
    r1 = v39._init_rec(d, d.constituents[0], st, SCENE, SCENE, trial=20, base_age=5, config=cfg)
    assert r1.init == v39.ZERO4 and r1.post == v39.ZERO4            # 比べ：初期成績 0


# ④ Q なしでも差が負なら、容量無限でも手放す
def test_04_negative_difference_released_with_infinite_budget():
    setup(budget=None)
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1, "wrap": 2}, ("R_x", 1): {"lock": 1}}
    st = state([d], hist, {("R_x", 0): rec("F", sf=0.0, sh=1.0, e=1.0), ("R_x", 1): rec("F", sf=1.0, sh=1.0, e=1.0)})
    out, events, before, after, ties, boundary = v39.run_conversions(st, 10)
    kinds = [(e["v39"], e["slot_index"]) for e in events]
    assert ("FH", 0) in kinds and ("FH", 1) not in kinds  # V＝0 は残す
    assert not out.definitions["R_x"].constituents[0].alive and out.definitions["R_x"].constituents[1].alive


# ⑤ U が常に棄権なら H→U の点は負にならない
def test_05_u_abstain_makes_HU_nonnegative():
    setup(u="abstain")
    d = definition(row(0, "fold", ("x", "y"), alive=False), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}}
    cfg = SimpleNamespace(local_lambda=1.0, higher_order_predicates=frozenset())
    assert v39.u_answer(d, d.constituents[0], SCENE, p_hat(), frozenset())[0] is None
    st = state([d], hist, {("R_x", 0): rec("H", sh=0.0, su=0.0, e=3.0), ("R_x", 1): rec("F", sf=1, sh=1, e=1)})
    cands = v39._candidates(st, d, 10, v39.code_lengths(st.p_hat), 1)
    assert all(c[0] >= 0 for c in cands if c[1] == "HU")
    _ = cfg


# ⑥ 同じ引数に真の関係が二つあっても、互いに排他にしない（開示された関係とだけ比べる）
def test_06_two_truths_same_arguments_not_exclusive():
    setup()
    seats = {("R_x", 0): rec("F")}
    ans = {"R": "R_x", "items": [{"slot": 0, "st": "F", "pos": ["a", "b"], "gen": 0,
                                   "ans": {"F": "fold", "H": "wrap", "U": "fold"}}]}
    out, scored = v39.score_answers(seats, ans, Relation("h", "wrap", ("a", "b")), 11)
    assert scored == [[0, "F", 0, 1, 0]]                           # fold(a,b) も真（見えている）だが、罰も「偽」も付けない
    SF, SH, SU, E = v39.rec_means(out[("R_x", 0)], 11)
    assert SF == 0.0 and SH > 0 and E > 0


# ⑦ F→H と H→U の残る情報と、解放量（費用の差）が一致する
def test_07_release_matches_cost_difference_and_remaining_information():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")), row(2, "push", ("x", "z")))
    hist = {("R_x", 0): {"fold": 1, "wrap": 2}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 2}}
    st = state([d], hist, {("R_x", i): rec("F") for i in range(3)})
    L = v39.code_lengths(st.p_hat)
    c0 = v39.total_bits(st, L)
    dFH = v39.fixed_spec_bits("fold", hist[("R_x", 0)], L)
    st1, _ = v39._convert(st, "FH", "R_x", 0, 10)
    assert c0 - v39.total_bits(st1, L) == dFH
    assert st1.slot_history[("R_x", 0)] == {"fold": 1, "wrap": 2}   # 候補名と回数は残る
    dHU = v39.hcost(st1.slot_history[("R_x", 0)], L)
    st2, _ = v39._convert(st1, "HU", "R_x", 0, 10)
    assert v39.total_bits(st1, L) - v39.total_bits(st2, L) == dHU
    assert ("R_x", 0) not in st2.slot_history                      # 履歴欄全体を外す
    assert dFH >= 1 and dHU >= 1


# ⑦′ 履歴欄の無い F 席：F→H で空の表の H（I(0)＝1 ビット）になり、H→U で空の表も外す（解放量は正）
def test_07b_empty_table_H():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 1): {"lock": 1}}
    st = state([d], hist, {("R_x", 0): rec("F"), ("R_x", 1): rec("F")})
    L = v39.code_lengths(st.p_hat)
    c0 = v39.total_bits(st, L)
    dFH = v39.fixed_spec_bits("fold", None, L)
    st1, _ = v39._convert(st, "FH", "R_x", 0, 10)
    assert v39.seat_state(st1.definitions["R_x"], st1.definitions["R_x"].constituents[0], st1.slot_history) == "H"
    assert st1.slot_history[("R_x", 0)] == {} and c0 - v39.total_bits(st1, L) == dFH == v39.I(0) + L["fold"]
    st2, _ = v39._convert(st1, "HU", "R_x", 0, 10)
    assert v39.total_bits(st1, L) - v39.total_bits(st2, L) == v39.I(0) == 1
    assert v39.h_answer(st1.definitions["R_x"], st1.definitions["R_x"].constituents[0], st1.slot_history,
                        st1.p_hat, 1.0, frozenset())[0] is None


# ⑧ 消した名は、照合・親・履歴・識別子から読めない
def test_08_erased_name_unreadable():
    setup()
    d = definition(row(0, "lock", ("x", "y")), row(1, "fold", ("y", "z")))
    hist = {("R_x", 0): {"wrap": 2}, ("R_x", 1): {"fold": 1}}      # 固定名 lock は履歴に無い
    st = state([d], hist, {("R_x", 0): rec("F"), ("R_x", 1): rec("F")})
    st1, _ = v39._convert(st, "FH", "R_x", 0, 10)
    assert "lock" not in repr(st1.definitions)                     # 行の述語は消えている
    g = v39.v39_graph(st1.definitions["R_x"], st1.slot_history)
    try:
        assert all(r.predicate != "lock" for r in g.relations)
        scene = RelationGraph("s", (Entity("a"), Entity("b"), Entity("c")),
                              (Relation("s1", "lock", ("a", "b")), Relation("s2", "fold", ("b", "c"))))
        import abm.sme as sme
        al = sme.map_graphs(g, scene).alignment
        assert "r0" not in al.relation_mapping                     # lock(a,b) は、消した名では当てはまらない
    finally:
        v39.unregister(g)


# ⑨ 覚え直しは新しい観察だけ・すぐ課金する（古い名・回数・成績は戻らない）
def test_09_relearn_new_observations_only_charged_now():
    setup()
    d = definition(row(0, "fold", ("x", "y"), alive=False), row(1, "lock", ("y", "z")))
    hist = {("R_x", 1): {"lock": 1}}
    old = v39.SeatRec(2, "U", 3, 5, v39.ZERO4, v39.ZERO4)
    st = state([d], hist, {("R_x", 0): old, ("R_x", 1): rec("F")})
    L = v39.code_lengths(st.p_hat)
    c0 = v39.total_bits(st, L)
    from abm.filling import observe_slot
    st = v39.replace(st, slot_history=observe_slot(st.slot_history, "R_x", 0, "push", 1.0))
    st = v39.reconcile(st, 12, "m1")
    r = st.v39_seats[("R_x", 0)]
    assert r.gen == 3 and r.state == "H" and r.init == v39.ZERO4 and r.post == v39.ZERO4
    assert st.slot_history[("R_x", 0)] == {"push": 1}
    assert v39.total_bits(st, L) - c0 == v39.hcost({"push": 1}, L)  # 新しい履歴をすぐ課金


# ⑩ F がゼロでも H があれば残る。全部 U なら退役
def test_10_zero_F_with_H_survives_all_U_retires():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}}
    st = state([d], hist, {("R_x", 0): rec("F"), ("R_x", 1): rec("F")})
    st, _ = v39._convert(st, "FH", "R_x", 0, 10)
    st, _ = v39._convert(st, "FH", "R_x", 1, 10)
    assert "R_x" in st.definitions and v39.n_FH(st.definitions["R_x"], st.slot_history) == 2
    st, ev = v39._convert(st, "HU", "R_x", 0, 10)
    assert ev is None and "R_x" in st.definitions
    st, ev = v39._convert(st, "HU", "R_x", 1, 10)
    assert ev["kind"] == "definition_removed" and ev["v39"] == "retire" and "R_x" not in st.definitions and not any(k[0] == "R_x" for k in st.slot_history)


# ⑪ 同点は独立した乱数で選び、世界の乱数を変えない。予算に収まれば止める
def test_11_ties_independent_rng_and_stop_when_fit():
    setup()
    defs = [definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")), name=f"R_{i}") for i in range(3)]
    hist = {(f"R_{i}", j): {"fold": 1, "lock": 1} for i in range(3) for j in range(2)}
    seats = {(f"R_{i}", j): rec("F", sf=1, sh=1, e=1) for i in range(3) for j in range(2)}   # 全部 V＝0（同点）
    st = state(defs, hist, seats)
    L = v39.code_lengths(st.p_hat)
    total = v39.total_bits(st, L)
    one = v39.fixed_spec_bits("fold", {"fold": 1, "lock": 1}, L)
    setup(budget=total - 1)
    random.seed(12345)
    g0 = random.getstate()
    out, events, before, after, ties, boundary = v39.run_conversions(st, 10)
    assert random.getstate() == g0                                  # 世界・開示の乱数（random の状態）は消費しない
    conv = [e for e in events if e.get("v39") in ("FH", "HU")]
    assert len(conv) == 1 and after <= total - 1 and after == total - conv[0]["dC"]   # 一件で収まれば止める
    assert conv[0]["tie_n"] == 6 and ties == 1
    out2, events2, *_ = v39.run_conversions(st, 10)
    assert [(e["R"], e["slot_index"]) for e in events2] == [(e["R"], e["slot_index"]) for e in events]   # 同じ試行なら同じ選び
    _ = one


# ⑫ 容量処理は有限回で終わり、不適合を隠さない
def test_12_finite_and_unfit_raised():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}}
    st = state([d], hist, {("R_x", 0): rec("F", sf=1, sh=1, e=1), ("R_x", 1): rec("F", sf=1, sh=1, e=1)})
    setup(budget=5)                                                 # 全体の回数表だけでも足りない
    try:
        v39.run_conversions(st, 10)
    except v39.Unfit as e:
        assert '"budget": 5' in str(e)
    else:
        raise AssertionError("容量不適合が出ない")
    setup(budget=v39.global_table_bits(st.p_hat) + v39.I(0))        # 全部を手放せば収まる
    out, events, before, after, *_ = v39.run_conversions(st, 10)
    assert not out.definitions and after == v39.CFG["budget"]
    assert sum(1 for e in events if e.get("v39") in ("FH", "HU")) == 4   # 席 2 × 二段


# ⑬ 門の二つの条件（支持数 ≧ ceil(0.67 ×（F＋H））・構造の整合）と、名前の条件がゼロの定義
def test_13_gate_two_conditions_and_zero_name_condition():
    setup()
    cfg = SimpleNamespace(tau_acc=0.67)
    # F 2 席（fold(x,y)・lock(y,z)）と H 1 席（履歴 wrap）。場面で H が当てはまらなければ 2/3 ＜ ceil(0.67×3)＝3
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")), row(2, "push", ("x", "z"), alive=False))
    hist = {("R_x", 2): {"wrap": 1}}
    sel = v39.select_definition(state([d], hist, {}), SCENE, cfg)
    assert sel[1] == 2 and sel[5] == 3 and sel[7] == []            # 支持 2、F＋H 3、門を通らない
    scene2 = RelationGraph("s", SCENE.entities, SCENE.relations + (Relation("s3", "wrap", ("a", "c")),))
    sel = v39.select_definition(state([d], hist, {}), scene2, cfg)
    assert sel[1] == 3 and sel[7] and sel[7][0]["R"] == "R_x"      # H が履歴の名で当てはまり、門を通る
    scene3 = RelationGraph("s", SCENE.entities, SCENE.relations + (Relation("s3", "wrap", ("c", "a")),))
    sel = v39.select_definition(state([d], hist, {}), scene3, cfg)
    assert sel[1] == 2                                             # 名が合っても引数の構造が合わなければ当てはまらない
    u_only = definition(row(0, "fold", ("x", "y"), alive=False), row(1, "lock", ("y", "z"), alive=False), name="R_u")
    assert v39.select_definition(state([u_only], {}, {}), SCENE, cfg) is None   # 名前の条件 0（全部 U）の定義は選ばない


# ⑯ 局所の採点は、選んだ定義の席だけ（ほかの定義へ証拠を配らない）
def test_16_local_scoring_touches_only_used_definition():
    setup()
    seats = {("R_x", 0): rec("F"), ("R_y", 0): rec("F")}
    ans = {"R": "R_x", "items": [{"slot": 0, "st": "F", "pos": ["a", "b"], "gen": 0,
                                   "ans": {"F": "wrap", "H": "wrap", "U": "fold"}}]}
    out, _ = v39.score_answers(seats, ans, Relation("h", "wrap", ("a", "b")), 11)
    assert out[("R_y", 0)] is seats[("R_y", 0)]


# v3.10 λ＞0：V＜λ の変換を、候補がなくなるまで低い点から一段ずつ（負の点数を含む）。λ＝0 は V＜0 だけ
def test_17_price_converts_below_lambda_until_none():
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")), row(2, "push", ("x", "z")))
    hist = {("R_x", 0): {"fold": 1, "wrap": 2}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 2}}
    seats = {("R_x", 0): rec("F", sf=0.0, sh=1.0, e=1.0),            # V_FH＜0
             ("R_x", 1): rec("F", sf=1.0, sh=1.0, su=1.0, e=1.0),    # V_FH＝0、H→U も 0
             ("R_x", 2): rec("F", sf=3.0, sh=0.0, e=3.0)}            # V_FH＞0（大きい）
    st = state([d], hist, seats)
    setup(price=0.0)
    v39.CFG.pop("price")
    out0, ev0, *_ = v39.run_conversions(st, 10)
    assert [(e["v39"], e["slot_index"]) for e in ev0 if e.get("v39") in ("FH", "HU")] == [("FH", 0)]   # λ＝0：V＜0 だけ
    setup(price=1e-9)
    out, ev, *_ = v39.run_conversions(st, 10)
    conv = [(e["v39"], e["slot_index"], e["why"]) for e in ev if e.get("v39") in ("FH", "HU")]
    assert conv[0] == ("FH", 0, "neg")                                # 低い点から
    assert ("FH", 1, "price") in conv and ("HU", 1, "price") in conv  # V＝0＜λ：一つ変換するごとに次の段も計算し直す
    assert all(s != 2 for _, s, _ in conv)                           # V＞λ は残す
    cands = [c for c in v39._candidates(out, out.definitions["R_x"], 10, v39.code_lengths(out.p_hat), 1)]
    assert all(c[0] >= 1e-9 for c in cands)                           # 候補がなくなるまで


# D：ACT-R の基礎の活性 B(t) ＝ ln Σⱼ max(t − tⱼ, 1)^(−0.5)（手計算と照らす）
def test_18_actr_activation_hand_calc():
    import math
    # 使用 0・5・9、t＝10：10^(−0.5)＝0.316228、5^(−0.5)＝0.447214、1^(−0.5)＝1 → 和 1.763441 → ln ＝ 0.567267
    assert abs(v39.activation([0, 5, 9], 10) - 0.567267) < 1e-6
    assert v39.activation([10], 10) == 0.0                          # 生まれた試行：max(0, 1)＝1 → ln 1 ＝ 0
    assert abs(v39.activation([0], 100) - math.log(0.1)) < 1e-12     # 一度も使われない：−0.5 ln(t−t₀)
    assert abs(v39.activation([3, 3], 4) - math.log(2.0)) < 1e-12    # 同じ試行の二つの記録は二回数える


if __name__ == "__main__":
    for mode in ("uniform", "actr"):
        MODE["decay"] = mode
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn()
                print("ok", mode, name)
