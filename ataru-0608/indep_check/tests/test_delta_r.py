"""(b) 第二段 Δr の参照の検査。お店の扉の小さな図（例外の日のシール sig_e・通常の日 sig_n）。"""
import copy
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from refcommon import Definition, Question, Scene, Seat, code_lengths, L_of  # noqa: E402
from ref_delta_r import Knowledge, Params, delta_r, predict  # noqa: E402

BSEAL = {"sig_n": 0.9, "sig_e": 0.1}
BANS = {"open": 0.5, "closed": 0.5}
BGEN = {"at": 1 / 3, "lit": 1 / 3, "warm": 1 / 3}
PHAT = {"open": 6, "closed": 2, "sig_n": 9, "sig_e": 1, "at": 10, "lit": 10, "warm": 10}


def b_of(d, s):
    return BSEAL if s.key == "seal" else BANS if s.key in ("open", "open2") else BGEN


def bbar_of(sc, j):
    return BSEAL if j == "seal" else BGEN


KN = Knowledge(b_of=b_of, bbar_of=bbar_of, p_hat_counts=PHAT)


def F(k, args, name, n=1, slot=0):
    return Seat(k, args, "F", name, ((name, n),), slot=slot)


def defA(reg=1, name="A"):
    """通常の日の定義：seal(d)=sig_n、at(d,s)、lit(s)、open(d)=open（答える席）。"""
    return Definition(name, reg, ("d", "s"), (F("seal", ("d",), "sig_n", 3, 0), F("at", ("d", "s"), "at", 3, 1),
                                              F("lit", ("s",), "lit", 3, 2), F("open", ("d",), "open", 3, 3)))


def defB():
    """例外の日の定義：seal(d)=sig_e、at、lit、warm(s)、open(d)=closed。"""
    return Definition("B", 2, ("d", "s"), (F("seal", ("d",), "sig_e", 1, 0), F("at", ("d", "s"), "at", 1, 1),
                                           F("lit", ("s",), "lit", 1, 2), F("warm", ("s",), "warm", 1, 3),
                                           F("open", ("d",), "closed", 1, 4)))


NORMAL = Scene(("d", "s"), (("seal", "sig_n", ("d",)), ("at", "at", ("d", "s")), ("lit", "lit", ("s",)),
                            ("warm", "warm", ("s",))))
Q_OPEN = Question("q", ("d",), "open")


def rows_by(res):
    return {(r["R"], r["seat"]): r for r in res["rows"]}


def test_base_selection_hand_values():
    """手計算：A は seal・at・lit が合う：S＝.0015＋d 8·.001＋s 8·.001＝.0175、T(A)＝.022、T(x)＝.022 → Q＝.035/.044。
    B は seal が合わない（--match-eps 0 で q＝0）：S＝.0015＋d .004＋s 8·.0015＝.0175、T(B)＝.0265 → Q＝.035/.0485。
    A の門：支持 3／F＋H 4、必要 ceil(0.67·4)＝3 → 通る。答える席 open(d) の P＝.99＋.01·.5＝.995。"""
    out = predict([defA(), defB()], NORMAL, Q_OPEN, KN, Params())
    ev = {e["R"]: e for e in out["evals"]}
    assert abs(ev["A"]["Q"] - 0.035 / 0.044) < 1e-12
    assert abs(ev["B"]["Q"] - 0.035 / 0.0485) < 1e-12
    assert ev["A"]["gate"] and not ev["B"]["gate"]
    assert out["used"] == "A" and out["case"] == "one_seat"
    assert abs(out["r_top1"] + math.log2(0.995)) < 1e-12
    assert out["spoken"] == "open" and out["r_zero_ell"] == 0.0


def test_unselected_definition_seal_gets_positive_value():
    """選ばれていない定義 B のシールを F→H にすると（履歴 {sig_e:1}、q_H(sig_n)＝.9/2＝.45）、
    B の S_P＝.0175＋.45·.0045 で Q_B＝2·.019525/.0485＝.8052 ＞ Q_A＝.7955 となって B が選ばれ、
    B は門を通らない（支持 3／5、必要 4）ので黙り、p̂ に戻る：Δr＝−log₂(6/38)＋log₂ .995＞0
    （GPT 四つの判断 §9 384–386 行：未選択だから 0 にはしない）。"""
    res = delta_r([defA(), defB()], NORMAL, Q_OPEN, KN, Params())
    r = rows_by(res)[("B", "seal")]
    assert r["selected_after"] == "B" and r["used_after"] is None and r["case_after"] == "no_gate_pass:p_hat"
    want = -math.log2(6 / 48) + math.log2(0.995)
    assert abs(r["delta"] - want) < 1e-12
    # A の答える席を F→H：P_H(open)＝.99·(3＋.5)/4＋.005
    r2 = rows_by(res)[("A", "open")]
    assert abs(r2["delta"] - (-math.log2(0.99 * 3.5 / 4 + 0.005) + math.log2(0.995))) < 1e-12
    # 選びが変わらず答えも変わらない席は 0
    assert rows_by(res)[("A", "lit")]["delta"] == 0.0


def test_redundant_two_seats_both_zero():
    """同じ役割の二席（同じ定義が二つ）：片方だけ薄くしても答えが変わらず、両方の Δr が 0（GPT 四つの判断 §6.3）。"""
    mem = [defA(1, "A1"), defA(2, "A2")]
    res = delta_r(mem, NORMAL, Q_OPEN, KN, Params())
    assert res["base"]["used"] == "A2"
    for k in ("seal", "at", "lit"):
        assert rows_by(res)[("A1", k)]["delta"] == 0.0
        assert rows_by(res)[("A2", k)]["delta"] == 0.0


def test_negative_delta_not_rounded():
    """例外の日（シール sig_e）に、大きな通常の定義 A′ が誤って選ばれる。A′ の warm を薄くすると B が選ばれ、
    正解 closed の損が減る（Δr＜0。0 に丸めない：42′ 2）。"""
    Abig = Definition("A", 3, ("d", "s"), (F("at", ("d", "s"), "at", 3, 1), F("lit", ("s",), "lit", 3, 2),
                                           F("warm", ("s",), "warm", 3, 3), F("open", ("d",), "open", 3, 4)))
    Bsmall = Definition("B", 2, ("d", "s"), (F("seal", ("d",), "sig_e", 1, 0), F("at", ("d", "s"), "at", 1, 1),
                                             F("lit", ("s",), "lit", 1, 2), F("open", ("d",), "closed", 1, 3)))
    exc = Scene(("d", "s"), (("seal", "sig_e", ("d",)), ("at", "at", ("d", "s")), ("lit", "lit", ("s",)),
                             ("warm", "warm", ("s",))))
    q = Question("q", ("d",), "closed")
    res = delta_r([Abig, Bsmall], exc, q, KN, Params())
    assert res["base"]["used"] == "A"
    neg = [r for r in res["rows"] if r["delta"] < 0]
    assert neg, res["rows"]
    # 同点の Q（.035/.044）を席数→新しさで A が取る（古い版の順）。A の at・lit・warm を薄くすると B に替わる。
    for r in neg:
        assert r["R"] == "A"
    assert {r["seat"] for r in neg if r["used_after"] == "B"} == {"at", "lit", "warm"}


def test_zero_probability_uses_escape_code():
    """P_{d*}(y)＝0（b(y)＝0 で εb(y)＝0）なら L_of の退避符号の長さで払い、差は有限（42″ 1）。"""
    kn = Knowledge(b_of=lambda d, s: ({"open": 1.0} if s.key == "open" else b_of(d, s)), bbar_of=bbar_of,
                   p_hat_counts=PHAT)
    q = Question("q", ("d",), "closed")
    out = predict([defA()], NORMAL, q, kn, Params())
    L = code_lengths(PHAT)
    assert out["r_top1_escaped"] and out["r_top1"] == L_of("closed", L)
    res = delta_r([defA()], NORMAL, q, kn, Params())
    assert all(math.isfinite(r["delta"]) for r in res["rows"])


def test_multiple_answer_seats_mixed_equally():
    """答える席の候補が複数なら等しい重みで混ぜる（42⁵ 2）。"""
    d = Definition("M", 1, ("d", "s"), (F("seal", ("d",), "sig_n", 3, 0), F("at", ("d", "s"), "at", 3, 1),
                                        F("lit", ("s",), "lit", 3, 2), F("open", ("d",), "open", 3, 3),
                                        F("open2", ("d",), "closed", 3, 4)))
    out = predict([d], NORMAL, Q_OPEN, KN, Params(tau=0.5))   # 支持 3／5 で門を通すため τ＝0.5
    assert out["case"] == "mixed_seats"
    p_open = 0.5 * (0.99 + 0.005) + 0.5 * (0.005)
    assert abs(out["answer_dist"]["open"] - p_open) < 1e-12


def test_no_gate_pass_uses_p_hat_or_shape_b():
    """門を通る定義が無ければ p̂（42⁵ 1）。形と階が分かれば絞った b。"""
    out = predict([defB()], NORMAL, Q_OPEN, KN, Params())
    assert out["case"] == "no_gate_pass:p_hat"
    assert abs(out["r_top1"] + math.log2(6 / 48)) < 1e-12
    kn = Knowledge(b_of=b_of, bbar_of=bbar_of, p_hat_counts=PHAT, shape_b=lambda sc, q: BANS)
    out = predict([defB()], NORMAL, Q_OPEN, kn, Params())
    assert out["case"] == "no_gate_pass:b_shape" and abs(out["r_top1"] - 1.0) < 1e-12


def test_scope_chosen_matches_all_on_chosen_seats():
    """42⁗ の関門：chosen の Δr が all の Δr のうち選ばれた定義の席の分と一致する。"""
    mem = [defA(), defB()]
    all_ = rows_by(delta_r(mem, NORMAL, Q_OPEN, KN, Params(), scope="all"))
    ch = rows_by(delta_r(mem, NORMAL, Q_OPEN, KN, Params(), scope="chosen"))
    assert set(ch) == {k for k in all_ if k[0] == "A"}
    for k in ch:
        assert ch[k]["delta"] == all_[k]["delta"]


def test_counterfactual_does_not_change_inputs():
    """反実仮想で本体の記憶・知識を変えない（42′ 4）。"""
    mem = [defA(), defB()]
    before = copy.deepcopy((mem, PHAT))
    delta_r(mem, NORMAL, Q_OPEN, KN, Params())
    assert (mem, PHAT) == before


def test_top1_detects_probability_drop():
    """候補一つで正解の確率が下がれば top1 の損は増える（GPT 四つの判断 §8 2：0.99→0.51 を検知）。"""
    res = delta_r([defA()], NORMAL, Q_OPEN, KN, Params())
    assert rows_by(res)[("A", "open")]["delta_top1"] > 0
    assert rows_by(res)[("A", "open")]["delta_zero_ell"] == 0.0   # 最頻の答えは変わらない


def test_zero_ell_arm():
    """0/ℓ の腕：誤った定義が選ばれて違う答えを言えば ℓ(y)、黙っても ℓ(y)。"""
    res = delta_r([defA(), defB()], NORMAL, Q_OPEN, KN, Params(loss="zero_ell"))
    L = code_lengths(PHAT)
    assert rows_by(res)[("B", "seal")]["delta"] == L_of("open", L)


def test_fixed_mapping_approximation_misses_new_pair():
    """対応を固定する近似は、薄くして新しく対になる組を落とす（42 ■3、GPT 四つの判断 §8 4）。
    B のシール F[sig_e] は通常の日に対にならない（q＝0）。F→H で q_H(sig_n)＝.45＞0 となり、やり直しでは対になって
    B が選ばれるが、固定した対応（シールなし）では B の点は変わらない。"""
    full = rows_by(delta_r([defA(), defB()], NORMAL, Q_OPEN, KN, Params(), rematch="full"))
    fixed = rows_by(delta_r([defA(), defB()], NORMAL, Q_OPEN, KN, Params(), rematch="fixed"))
    assert full[("B", "seal")]["delta"] > 0 and fixed[("B", "seal")]["delta"] == 0.0
