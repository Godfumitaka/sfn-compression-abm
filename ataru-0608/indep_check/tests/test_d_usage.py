"""保持 D の使用（今の D・C* のもとでの D・D＋注意）の参照の検査（受け箱 注意の係 指示 4）。"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from refcommon import Definition, Scene, Seat  # noqa: E402
from ref_cstar import match_dists, q_from_dists  # noqa: E402
from ref_d_usage import (actr_weights, add_use, attn_weight, birth, decay_ladder, forget_targets, step,  # noqa: E402
                         strength, trial_uses, uses_from_prediction)
from ref_delta_r import Params, predict  # noqa: E402
from test_delta_r import KN, NORMAL, Q_OPEN, defA, defB  # noqa: E402

T = 1740
DEC = decay_ladder(T)

SC = Scene(("d", "s"), (("seal", "sig_n", ("d",)), ("at", "at", ("d", "s")), ("lit", "lit", ("s",))), ("hid",))
D = Definition("D", 1, ("d", "s"), (
    Seat("seal", ("d",), "H", None, (("sig_n", 2), ("sig_e", 1)), slot=0),   # H、場面の名は履歴にある
    Seat("at", ("d", "s"), "F", "at", (("at", 3),), slot=1),               # F、一致
    Seat("lit", ("s",), "F", "warm", (("warm", 1),), slot=2),              # F、不一致
    Seat("u", ("s",), "U", slot=3),                                        # U は数えない
    Seat("open", ("d",), "F", "open", (("open", 3),), slot=4)))            # 対なし（答えの席）
M = {"seal": "seal", "at": "at", "lit": "lit", "u": "hid"}
B = {"sig_n": 0.9, "sig_e": 0.1, "at": 1 / 3, "lit": 1 / 3, "warm": 1 / 3}


def test_decay_ladder_and_strength():
    """古い版の式：係数 exp(−1/τ_k)、τ_k＝0.3·(3T/0.3)^(k/15)。一回使った直後の S＝1、dt 後は 16 本の f^dt の平均。"""
    assert abs(DEC[0] - math.exp(-1 / 0.3)) < 1e-15 and abs(DEC[15] - math.exp(-1 / (3 * T))) < 1e-15
    r = add_use(None, 10, 1.0, DEC)
    assert strength(r, 10, DEC) == 1.0
    assert abs(strength(r, 25, DEC) - sum(f ** 15 for f in DEC) / 16) < 1e-15
    w = actr_weights(T)
    assert abs(sum(w) - 1) < 1e-12 and strength(r, 10, DEC, w) == sum(w)
    # 使用のたびに今へ減衰させてから足す
    r2 = add_use(r, 13, 1.0, DEC)
    assert all(abs(x - (f ** 3 + 1)) < 1e-15 for x, f in zip(r2.vec, DEC))


def test_old_D_uses():
    """今の D：F 一致 1、F 不一致 0、H は場面の名が履歴にあれば 1、伏せた位置・U は数えない、答えの席 1、一試行に一回まで。"""
    u = trial_uses(D, M, SC, mode="old", answer_seat="open")
    assert u == {"seal": 1.0, "at": 1.0, "lit": 0.0, "open": 1.0}
    u = trial_uses(D, M, SC, mode="old", answer_seat="at")
    assert u["at"] == 1.0


def test_cstar_D_uses_q():
    """C* のもとの D（--match-eps 0）：F は q∈{0,1}（今の D と同じ）、H は q_H(sig_n)＝(2＋.9)/(3＋1)＝.725。"""
    q = q_from_dists(D, SC, M, match_dists(D, lambda d, s: B, eps=0.01, match_eps="0"))
    u = trial_uses(D, M, SC, mode="cstar", q=q, answer_seat="open")
    assert abs(u["seal"] - 2.9 / 4) < 1e-15
    assert u["at"] == 1.0 and u["lit"] == 0.0 and u["open"] == 1.0
    # --match-eps shared：F の一致は (1−ε)＋εb、不一致は εb
    q2 = q_from_dists(D, SC, M, match_dists(D, lambda d, s: B, eps=0.01, match_eps="shared"))
    u2 = trial_uses(D, M, SC, mode="cstar", q=q2)
    assert abs(u2["at"] - (0.99 + 0.01 / 3)) < 1e-15 and abs(u2["lit"] - 0.01 / 3) < 1e-15


def test_cstar_equals_old_when_q_is_zero_one():
    """旗の関門の参照側：F だけの定義・--match-eps 0 なら C* の使用は今の D と同じ。"""
    Fonly = Definition("Fo", 1, D.entities, tuple(s for s in D.seats if s.state == "F"))
    Mf = {"at": "at", "lit": "lit"}
    q = q_from_dists(Fonly, SC, Mf, match_dists(Fonly, lambda d, s: B, eps=0.01, match_eps="0"))
    assert trial_uses(Fonly, Mf, SC, mode="cstar", q=q, answer_seat="open") == \
        trial_uses(Fonly, Mf, SC, mode="old", answer_seat="open")


def test_attn_all_zero_equals_D():
    """a が全部 0 なら D と同じ（w＝1）。"""
    a = {"sig_n": 0.0, "at": 0.0, "lit": 0.0}
    key = lambda sc, j: sc.name_of(j)
    for mode, q in (("old", None), ("cstar", {"seal": 0.725, "at": 1.0, "lit": 0.0})):
        assert trial_uses(D, M, SC, mode=mode, q=q, answer_seat="open", a=a, key_of=key) == \
            trial_uses(D, M, SC, mode=mode, q=q, answer_seat="open")


def test_attn_raise_one_key_mean_fixed():
    """a の平均を変えずに一つの鍵の a を上げると、その鍵の席だけ使用（＝強さ）が増える。
    a＝{sig_n:1, at:1, lit:1}（ā＝1）→ {sig_n:2, at:0.5, lit:0.5}（ā＝1）：seal の w は 1→1.5、at の w は 1→0.75。"""
    key = lambda sc, j: sc.name_of(j)
    a0 = {"sig_n": 1.0, "at": 1.0, "lit": 1.0}
    a1 = {"sig_n": 2.0, "at": 0.5, "lit": 0.5}
    u0 = trial_uses(D, M, SC, mode="old", answer_seat="open", a=a0, key_of=key)
    u1 = trial_uses(D, M, SC, mode="old", answer_seat="open", a=a1, key_of=key)
    assert u0["seal"] == 1.0 and u1["seal"] == 1.5 and u1["at"] == 0.75
    assert [k for k in u1 if u1[k] > u0[k]] == ["seal"]
    # 平均の重みは 1
    assert abs(sum(attn_weight(k, a1) for k in a1) / len(a1) - 1.0) < 1e-15


def test_attn_with_cstar_and_answer_weight():
    """C*＋注意：使用＝w·q。答えの使用は既定 1（重みを掛けない）、"zero_key" なら 1/(1＋ā)。"""
    key = lambda sc, j: sc.name_of(j)
    a = {"sig_n": 3.0, "at": 1.0}
    q = {"seal": 0.725, "at": 1.0, "lit": 0.0}
    u = trial_uses(D, M, SC, mode="cstar", q=q, answer_seat="open", a=a, key_of=key)
    assert abs(u["seal"] - 0.725 * 4 / 3) < 1e-15 and abs(u["at"] - 2 / 3) < 1e-15 and u["open"] == 1.0
    u = trial_uses(D, M, SC, mode="cstar", q=q, answer_seat="open", a=a, key_of=key, answer_weight="zero_key")
    assert abs(u["open"] - 1 / 3) < 1e-15


def test_birth_and_forget():
    """誕生の試行に量 1 の使用、その試行は判断しない。次の試行から S＜τ の席を U まで落とす対象にする。"""
    rec = birth({}, 5, "D", ["seal", "at", "lit", "open"], DEC)
    born = {("D", k): 5 for k in ("seal", "at", "lit", "open")}
    assert forget_targets([D], rec, 5, 2.0, DEC, born=born) == []
    rec = step(rec, 6, {"seal": 1.0, "at": 0.725, "lit": 0.0}, DEC, "D")
    tau = strength(rec[("D", "at")], 6, DEC) + 1e-9          # at と lit と open は τ 未満、seal は τ 以上
    got = {k for _R, k, _S, _to in forget_targets([D], rec, 6, tau, DEC, born=born)}
    assert got == {"at", "lit", "open"}
    assert abs(strength(rec[("D", "seal")], 6, DEC) - (sum(DEC) / 16 + 1)) < 1e-12


def test_uses_from_prediction_selected_before_gate():
    """選ばれた定義は門の判定の前の一位（門で黙っても数える）。答えの席は門を通って答えた定義のとき。"""
    pred = predict([defA(), defB()], NORMAL, Q_OPEN, KN, Params())
    R, u = uses_from_prediction(pred, [defA(), defB()], NORMAL, mode="old")
    assert R == "A" and u == {"seal": 1.0, "at": 1.0, "lit": 1.0, "open": 1.0}
    pred = predict([defB()], NORMAL, Q_OPEN, KN, Params())      # B は門を通らない
    R, u = uses_from_prediction(pred, [defB()], NORMAL, mode="old")
    assert R == "B" and pred["used"] is None
    assert u == {"seal": 0.0, "at": 1.0, "lit": 1.0, "warm": 1.0, "open": 0.0}
