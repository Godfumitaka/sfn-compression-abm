"""保持の誤り駆動（受け箱 注意の係 指示 6、指示 5 の B を置き換え）の参照の検査：指示 6 の関門を参照の側で独立に。"""
import copy
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from ref_error_driven import (birth_init_error_driven, error_driven, exact_increment,  # noqa: E402
                              first_order_increment, increments, mixed_loss, pi_rho)
from ref_delta_r import Params, eval_definition, thinned_memory  # noqa: E402
from ref_birth_init import birth_init, door_kind_by_disclosed  # noqa: E402
from ref_cstar import T_scene  # noqa: E402
from refcommon import Definition, Scene, Seat  # noqa: E402
from test_delta_r import KN, NORMAL, PHAT, Q_OPEN, defA, defB  # noqa: E402

Z2 = {"e": math.log(0.6), "n": math.log(0.3)}
P2 = {"e": 0.99, "n": 0.01}


def test_hand_example_exact_and_first_order():
    """指示 6 の手例（二候補、注意 0、z＝ln Q）：π＝(2/3, 1/3)、ρ＝(0.9949748744, 0.0050251256)。
    D_n の席 Δz＝＋0.5：厳密 0.1925098768・一次 0.1641541039。D_e の答える席 P 0.99→0.30（Δz＝0）：厳密 1.1824309606。
    D_e の合っている席 Δz＝−0.2：厳密 0.0700926570・一次 0.0656616415。1e−9。"""
    pi, rho = pi_rho(Z2, P2)
    assert abs(pi["e"] - 0.6666666667) < 1e-9 and abs(rho["e"] - 0.9949748744) < 1e-9
    assert abs(rho["n"] - 0.0050251256) < 1e-9
    inc = increments(Z2, P2, {("n", "s1"): 0.5, ("e", "ans"): 0.0, ("e", "s2"): -0.2},
                     {("e", "ans"): -math.log(0.30) + math.log(0.99)})
    assert abs(inc[("n", "s1")]["exact_nat"] - 0.1925098768) < 1e-9
    assert abs(inc[("n", "s1")]["first_nat"] - 0.1641541039) < 1e-9
    assert abs(inc[("e", "ans")]["exact_nat"] - 1.1824309606) < 1e-9
    assert abs(inc[("e", "s2")]["exact_nat"] - 0.0700926570) < 1e-9
    assert abs(inc[("e", "s2")]["first_nat"] - 0.0656616415) < 1e-9
    assert abs(inc[("e", "s2")]["exact_bits"] - 0.0700926570 / math.log(2)) < 1e-9


def test_gpt_counterexample_sign():
    """指示 6 の 1 の理由の例：π＝0.2、P＝0.1→0.3、他の候補の P＝0.3、Δz＝3 で、一次は＋0.285、厳密は −0.143 ナット。"""
    z = {"d": math.log(0.2), "o": math.log(0.8)}
    p = {"d": 0.1, "o": 0.3}
    pi, rho = pi_rho(z, p)
    dl = -math.log(0.3) + math.log(0.1)
    assert abs(first_order_increment(pi["d"], rho["d"], 3.0, dl) - 0.285) < 1e-3
    assert abs(exact_increment(pi["d"], rho["d"], 3.0, dl) - (-0.143)) < 1e-3


def test_exact_equals_direct_recompute():
    """厳密な式の検査：無作為の例（候補 1〜5）で、softmax と混ぜた確率を直接計算し直した損の差と 1e−12 で一致。"""
    rng = random.Random(6)
    for _ in range(500):
        n = rng.randint(1, 5)
        z = {i: rng.uniform(-3, 3) for i in range(n)}
        p = {i: rng.uniform(0.001, 1.0) for i in range(n)}
        d = rng.randrange(n)
        dz, dl = rng.uniform(-3, 3), rng.uniform(-3, 3)
        pi, rho = pi_rho(z, p)
        z2, p2 = dict(z), dict(p)
        z2[d] += dz
        p2[d] *= math.exp(-dl)
        direct = mixed_loss(z2, p2) - mixed_loss(z, p)
        assert abs(exact_increment(pi[d], rho[d], dz, dl) - direct) < 1e-12


def test_first_order_derivative_and_h_squared():
    """一次の値の検査：(π−ρ) と −ρ が L の z_d・ln p_d についての数値微分と 1e−6 で一致。
    Δ を h 倍して h を小さくすると、厳密と一次の差がおおむね h² で小さくなる（h を半分にすると差は約 1/4）。"""
    rng = random.Random(7)
    hd = 1e-6
    for _ in range(200):
        n = rng.randint(2, 5)
        z = {i: rng.uniform(-3, 3) for i in range(n)}
        p = {i: rng.uniform(0.01, 1.0) for i in range(n)}
        pi, rho = pi_rho(z, p)
        for d in z:
            zp, zm = dict(z), dict(z)
            zp[d] += hd
            zm[d] -= hd
            assert abs((mixed_loss(zp, p) - mixed_loss(zm, p)) / (2 * hd) - (pi[d] - rho[d])) < 1e-6
            pp, pm = dict(p), dict(p)
            pp[d] *= math.exp(hd)
            pm[d] *= math.exp(-hd)
            assert abs((mixed_loss(z, pp) - mixed_loss(z, pm)) / (2 * hd) - (-rho[d])) < 1e-6
        d = 0
        dz, dl = rng.uniform(-1, 1), rng.uniform(-1, 1)
        gaps = []
        for h in (1e-2, 5e-3, 2.5e-3):
            gaps.append(abs(exact_increment(pi[d], rho[d], h * dz, h * dl) - first_order_increment(pi[d], rho[d], h * dz, h * dl)))
        if gaps[0] > 1e-12:
            assert 0.2 < gaps[1] / gaps[0] < 0.3 and 0.2 < gaps[2] / gaps[1] < 0.3, gaps


def test_single_candidate_equals_dl():
    """候補一つ：π＝ρ＝1 なので増分＝Δℓ（純粋な形と、模型の形の答える席）。"""
    for dz in (-2.0, 0.0, 1.5):
        assert abs(exact_increment(1.0, 1.0, dz, 0.7) - 0.7) < 1e-12
    out = error_driven([defA()], NORMAL, Q_OPEN, KN, Params())
    r = {x["seat"]: x for x in out["rows"]}
    want = -math.log(0.99 * 3.5 / 4 + 0.005) + math.log(0.995)
    assert abs(r["open"]["exact_nat"] - want) < 1e-12
    for k in ("seal", "at", "lit"):
        assert r[k]["exact_nat"] == 0.0


def test_context_seat_changes_answer_dl_nonzero():
    """文脈の席を薄くして対応・答えが変わる手例：席 k(d,s) を F→H にすると k が at(d,s) に写り、物 d が写って
    open(d) が答える席になる。Δℓ＝−ln .995＋ln(6/48)≠0（「答える席以外は必ず 0」を検出する）。候補一つなので増分＝Δℓ。"""
    C = Definition("C", 1, ("d", "s"), (Seat("k", ("d", "s"), "F", "kx", (("kx", 1),), slot=0),
                                        Seat("lit", ("s",), "F", "lit", (("lit", 3),), slot=1),
                                        Seat("open", ("d",), "F", "open", (("open", 3),), slot=2)))
    out = error_driven([C], NORMAL, Q_OPEN, KN, Params(tau=0.3))
    r = next(x for x in out["rows"] if x["seat"] == "k")
    want = -math.log(0.995) + math.log(6 / 48)
    assert r["case_before"] == "p_hat" and r["case_after"] == "one_seat"
    assert abs(r["dl"] - want) < 1e-12 and r["dl_from_non_answer_seat"]
    assert abs(r["exact_nat"] - want) < 1e-12


def test_same_P_only_z_changes_is_zero():
    """全候補の P_d(y) が同じで z だけが変わる例：ρ＝π、Δℓ＝0 なので増分は厳密にも 0。"""
    z = {"a": 0.1, "b": -0.4, "c": 1.0}
    p = {"a": 0.3, "b": 0.3, "c": 0.3}
    inc = increments(z, p, {("a", "s"): 2.0, ("c", "t"): -1.0}, {})
    for v in inc.values():
        assert abs(v["exact_nat"]) < 1e-15 and abs(v["first_nat"]) < 1e-15


def test_suppressing_seat_positive():
    """誤って選ばれうる候補 B（誤答 closed）を押さえる席（例外のシール）を薄くして Δz＞0 になると、増分は正。"""
    out = error_driven([defA(), defB()], NORMAL, Q_OPEN, KN, Params(tau=0.5))
    r = next(x for x in out["rows"] if (x["R"], x["seat"]) == ("B", "seal"))
    assert r["dz"] > 0 and r["exact_nat"] > 0


def test_counterfactual_does_not_change_inputs():
    """仮の変換で、履歴・全体の頻度・注意・本当の記憶が変わらない（参照は純粋な関数）。"""
    mem = [defA(), defB()]
    a = dict(KN.a)
    before = copy.deepcopy((mem, PHAT, a))
    error_driven(mem, NORMAL, Q_OPEN, KN, Params(tau=0.5))
    assert (mem, PHAT, dict(KN.a)) == before


def test_dz_same_as_stage2_rematch_and_gate_fixed():
    """Δz は第二段と同じ再照合の関数の点の差（指示 5 の B の関門 5）。候補の集合は予測の時点で固定し、
    薄くした d が門の下に落ちても集合に残す（指示 6 の 5）。"""
    mem = [defA(), defB()]
    params = Params(tau=0.5)
    out = error_driven(mem, NORMAL, Q_OPEN, KN, params)
    T_x = T_scene(NORMAL)
    for r in out["rows"]:
        d2 = next(d for d in thinned_memory(mem, r["R"], r["seat"]) if d.name == r["R"])
        assert r["z_after"] == eval_definition(d2, NORMAL, Q_OPEN, KN, params, T_x)["z"]
    assert out["n_below_gate"] == sum(r["below_gate_after"] for r in out["rows"])
    assert set(out["z"]) == {"A", "B"} and out["n_Q_zero"] == 0


def test_no_disclosure_or_abstain():
    """開示の無い試行と、門を通った候補が無い試行（棄権）では何もしない。"""
    assert error_driven([defA()], NORMAL, Q_OPEN, KN, Params(), disclosed=False)["rows"] == []
    out = error_driven([defB()], NORMAL, Q_OPEN, KN, Params())
    assert out["rows"] == [] and out["skipped"] == "abstain"


def test_zero_probability_uses_escape_and_is_finite():
    """ℓ は log_cost：確率 0 の名前は逃げの符号の長さ（ビット）×ln 2 で、常に有限（指示 6 の 3）。"""
    from ref_delta_r import Knowledge
    from test_delta_r import b_of, bbar_of
    from refcommon import code_lengths, L_of, Question
    kn = Knowledge(b_of=lambda d, s: ({"open": 1.0} if s.key == "open" else b_of(d, s)), bbar_of=bbar_of,
                   p_hat_counts=PHAT)
    q = Question("q", ("d",), "closed")
    out = error_driven([defA()], NORMAL, q, kn, Params())
    assert abs(out["ell"]["A"] - L_of("closed", code_lengths(PHAT)) * math.log(2)) < 1e-12
    assert all(math.isfinite(r["exact_nat"]) for r in out["rows"])


def test_birth_same_questions_as_stage2():
    """誕生の初期値：第二段の (b) と同じ仮の問い・重みで、価値だけ厳密な差（指示 6 の 6）。初期値＝Σ w·増分。"""
    material2 = Scene(("d", "s"), (("seal", "sig_e", ("d",)), ("at", "at", ("d", "s")), ("lit", "lit", ("s",)),
                                   ("open", "closed", ("d",))))
    shape = Definition("N", 9, ("d", "s"), (Seat("seal", ("d",), "U", slot=0), Seat("at", ("d", "s"), "U", slot=1),
                                            Seat("lit", ("s",), "U", slot=2), Seat("open", ("d",), "U", slot=3)))
    names1 = {"seal": "sig_e", "at": "at", "lit": "lit", "open": "closed"}
    kw = dict(asked={"door": 2, "nondoor": 2}, is_door=door_kind_by_disclosed({"open", "closed"}))
    ed = birth_init_error_driven([defA()], shape, names1, material2, KN, Params(), **kw)
    s2 = birth_init([defA()], shape, names1, material2, KN, Params(), **kw)
    assert {r["question"] for r in ed["table"]} == set(s2["weights"])
    for r in ed["table"]:
        if r["seat"] is not None:
            assert r["w"] == s2["weights"][r["question"]]
    for k, v in ed["init_nat"].items():
        assert abs(v - sum(r["w"] * r["exact_nat"] for r in ed["table"] if r["seat"] == k)) < 1e-12
