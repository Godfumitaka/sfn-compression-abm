"""保持の誤り駆動（受け箱 注意の係 指示 5 の B）の参照の検査：関門 2〜6 を参照の側で独立に。"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from ref_error_driven import error_driven, increments, mixed_loss, pi_rho  # noqa: E402
from ref_delta_r import Params, delta_r, eval_definition, thinned_memory  # noqa: E402
from ref_cstar import T_scene  # noqa: E402
from refcommon import thin  # noqa: E402
from test_delta_r import KN, NORMAL, Q_OPEN, defA, defB  # noqa: E402


def test_gate2_hand_example():
    """関門 2：D_e（Q 0.6、P(y) 0.99）、D_n（Q 0.3、P(y) 0.01）、z＝ln Q。"""
    z = {"e": math.log(0.6), "n": math.log(0.3)}
    Py = {"e": 0.99, "n": 0.01}
    pi, rho = pi_rho(z, Py)
    assert abs(pi["e"] - 0.6666666667) < 1e-9 and abs(pi["n"] - 0.3333333333) < 1e-9
    assert abs(rho["e"] - 0.9949748744) < 1e-9 and abs(rho["n"] - 0.0050251256) < 1e-9
    inc = increments(z, Py,
                     {("n", "s1"): 0.5, ("e", "ans"): 0.0, ("e", "s2"): -0.2},
                     {("e", "ans"): -math.log(0.30) + math.log(0.99)})
    assert abs(inc[("n", "s1")]["nat"] - 0.1641541039) < 1e-9
    assert abs(inc[("e", "ans")]["nat"] - 1.1879228581) < 1e-9
    assert abs(inc[("e", "s2")]["nat"] - 0.0656616415) < 1e-9
    assert abs(inc[("e", "s2")]["bits"] - 0.0656616415 / math.log(2)) < 1e-9


def test_gate3_single_candidate_pure():
    """関門 3（純粋な形）：候補一つなら π＝ρ＝1、増分＝Δℓ（規則 A の log P の損の差）、選びの項は 0。"""
    z = {"d": 0.3}
    Py = {"d": 0.8}
    dl = -math.log(0.5) + math.log(0.8)
    inc = increments(z, Py, {("d", "ans"): -0.7, ("d", "other"): 1.3}, {("d", "ans"): dl})
    assert abs(inc[("d", "ans")]["nat"] - dl) < 1e-15 and inc[("d", "other")]["nat"] == 0.0


def test_gate3_single_candidate_model():
    """関門 3（模型の形）：定義 A だけ。答える席 open を F→H にした増分（ビット）が、規則 A の log P の
    「薄くした状態の損 − 今の状態の損」＝ −log₂(.99·3.5/4＋.005) ＋ log₂ .995 と一致。ほかの席は 0。"""
    out = error_driven([defA()], NORMAL, Q_OPEN, KN, Params())
    rows = {r["seat"]: r for r in out["rows"]}
    want = -math.log2(0.99 * 3.5 / 4 + 0.005) + math.log2(0.995)
    assert abs(rows["open"]["bits_formula"] - want) < 1e-12
    assert abs(rows["open"]["bits_answer_only"] - want) < 1e-12
    for k in ("seal", "at", "lit"):
        assert rows[k]["bits_formula"] == 0.0 and rows[k]["bits_answer_only"] == 0.0


def test_gate4_numerical_derivative():
    """関門 4：無作為の小さな例（候補 2〜5）で、(π_d − ρ_d) と −ρ_d が、L＝−ln Σ π_e P_e(y) の z_d と
    ln P_d(y) についての数値微分と 1e−6 で一致。"""
    rng = random.Random(5)
    h = 1e-6
    for _ in range(200):
        n = rng.randint(2, 5)
        z = {i: rng.uniform(-3, 3) for i in range(n)}
        Py = {i: rng.uniform(0.01, 1.0) for i in range(n)}
        pi, rho = pi_rho(z, Py)
        for d in z:
            zp, zm = dict(z), dict(z)
            zp[d] += h
            zm[d] -= h
            fd_z = (mixed_loss(zp, Py) - mixed_loss(zm, Py)) / (2 * h)
            Pp, Pm = dict(Py), dict(Py)
            Pp[d] *= math.exp(h)
            Pm[d] *= math.exp(-h)
            fd_l = (mixed_loss(z, Pp) - mixed_loss(z, Pm)) / (2 * h)
            assert abs(fd_z - (pi[d] - rho[d])) < 1e-6
            assert abs(fd_l - (-rho[d])) < 1e-6


def test_gate5_dz_same_as_stage2_rematch():
    """関門 5：Δz は第二段と同じ再照合の関数（eval_definition）で、d だけ照合し直した点の差。
    ref_delta_r の薄くした記憶の評価の z と一致する。"""
    mem = [defA(), defB()]
    out = error_driven(mem, NORMAL, Q_OPEN, KN, Params(tau=0.5))
    assert set(out["z"]) == {"A", "B"}                      # τ＝0.5 で両方が門を通る
    T_x = T_scene(NORMAL)
    for r in out["rows"]:
        alt = thinned_memory(mem, r["R"], r["seat"])
        d2 = next(d for d in alt if d.name == r["R"])
        ev = eval_definition(d2, NORMAL, Q_OPEN, KN, Params(tau=0.5), T_x)
        assert r["z_after"] == ev["z"] and r["dz"] == ev["z"] - out["z"][r["R"]]


def test_gate6_no_disclosure_or_abstain():
    """関門 6：開示の無い試行と、門を通った候補が無い試行（棄権）では何もしない。"""
    assert error_driven([defA()], NORMAL, Q_OPEN, KN, Params(), disclosed=False)["rows"] == []
    out = error_driven([defB()], NORMAL, Q_OPEN, KN, Params())     # B は門を通らない
    assert out["rows"] == [] and out["skipped"] == "abstain"


def test_two_candidates_selection_term():
    """二候補（τ＝0.5）：答える席でない席（B の at・lit・warm、A の at・lit・seal）の増分は選びの項 (π−ρ)Δz だけ。
    誤答 closed を言う B の席を薄くして z_B が下がれば、π_B＞ρ_B なので増分は負（薄くした方が混ぜた損が減る）。
    なお B のシール F[sig_e] は通常の日に対にならず、引数の写しが問いと同じ (d) なので、読み (b)-4 では
    答える席の一つになる（答える席は ['seal', 'open']）。"""
    out = error_driven([defA(), defB()], NORMAL, Q_OPEN, KN, Params(tau=0.5))
    rows = {(r["R"], r["seat"]): r for r in out["rows"]}
    assert out["pi"]["B"] > out["rho"]["B"]
    for k in (("B", "at"), ("B", "lit"), ("B", "warm"), ("A", "at"), ("A", "lit"), ("A", "seal")):
        r = rows[k]
        assert r["ans_formula"] == 0.0 and r["dl_differs"] is False
        assert abs(r["nat_formula"] - (out["pi"][k[0]] - out["rho"][k[0]]) * r["dz"]) < 1e-15
    assert rows[("B", "at")]["dz"] < 0 and rows[("B", "at")]["nat_formula"] < 0
    r = rows[("B", "seal")]
    assert abs(r["nat_formula"] - (r["sel"] + r["ans_formula"])) < 1e-15 and r["dz"] > 0


def test_dl_formula_vs_answer_only_case():
    """仕様の二つの文が分かれる例（spec_notes (E)-1、選んでいない）：答える席でない席 k(d,s) を F→H にすると、
    再照合で k が at(d,s) に写り、物 d が写って open(d) が答える席になる。式どおりの Δℓ は 0 でないが、
    「s が答える席のときだけ 0 でない」の文では 0。両方を出し、dl_differs で数える。"""
    from refcommon import Definition, Seat
    C = Definition("C", 1, ("d", "s"), (Seat("k", ("d", "s"), "F", "kx", (("kx", 1),), slot=0),
                                        Seat("lit", ("s",), "F", "lit", (("lit", 3),), slot=1),
                                        Seat("open", ("d",), "F", "open", (("open", 3),), slot=2)))
    out = error_driven([C], NORMAL, Q_OPEN, KN, Params(tau=0.3))
    r = next(r for r in out["rows"] if r["seat"] == "k")
    assert out["case"]["C"] == "p_hat" and r["case_after"] == "one_seat"
    assert r["dl_differs"] and r["dl_answer_only"] == 0.0
    assert abs(r["dl_formula"] - (-math.log(0.995) + math.log(6 / 48))) < 1e-12
