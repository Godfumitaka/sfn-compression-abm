"""(c) 誕生の初期値（42″・42‴）と (c′) 誕生の採点（41 ■5・41′ 2）の参照の検査。"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from refcommon import Definition, Question, Scene, Seat  # noqa: E402
from ref_birth_init import (birth_init, birth_local_bits, door_kind_by_disclosed, provisional_definition,  # noqa: E402
                            provisional_questions, question_weights)
from ref_delta_r import Knowledge, Params  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
from test_delta_r import KN, defA  # noqa: E402

B = {"sig_n": 0.11, "other": 0.89}


def test_birth_score_numbers_eps_half():
    """41 ■5：b(sig_n)＝0.11、ε＝1/2、α＝1、二つの sig_n の材料：1 材料あたり F 0.849・H 1.298・U 3.184（fit）、
    F 3.184＋0.849・H 3.184＋1.589・U 3.184×2（seq）。"""
    per = {st: birth_local_bits(st, "sig_n", "sig_n", B, eps=0.5, mode="fit") / 2 for st in "FHU"}
    assert abs(per["F"] - 0.849) < 5e-4 and abs(per["H"] - 1.298) < 5e-4 and abs(per["U"] - 3.184) < 5e-4
    seq = {st: birth_local_bits(st, "sig_n", "sig_n", B, eps=0.5, mode="seq") for st in "FHU"}
    assert abs(seq["F"] - (3.184 + 0.849)) < 1e-3
    assert abs(seq["H"] - (3.184 + 1.589)) < 1e-3
    assert abs(seq["U"] - 3.184 * 2) < 1e-3
    # GPT 四つの判断 §2 の表（ε＝0.5：4.0339・4.7730・6.3688、fit 1.6989・2.5962・6.3688）
    assert abs(seq["F"] - 4.0339) < 1e-4 and abs(seq["H"] - 4.7730) < 1e-4 and abs(seq["U"] - 6.3688) < 1e-4
    fit = {st: birth_local_bits(st, "sig_n", "sig_n", B, eps=0.5, mode="fit") for st in "FHU"}
    assert abs(fit["F"] - 1.6989) < 1e-4 and abs(fit["H"] - 2.5962) < 1e-4


def test_birth_score_numbers_eps_small():
    """ε＝0.01：seq F 3.1973・H 4.0455・U 6.3688（GPT 四つの判断 §2 88–89 行）。手の式：
    F＝−log₂ .11 − log₂(.99＋.0011)、H＝−log₂ .11 − log₂(.99·(1＋.11)/2＋.0011)。"""
    f = -math.log2(0.11) - math.log2(0.99 + 0.0011)
    h = -math.log2(0.11) - math.log2(0.99 * (1.11 / 2) + 0.0011)
    assert abs(birth_local_bits("F", "sig_n", "sig_n", B, eps=0.01) - f) < 1e-12
    assert abs(birth_local_bits("H", "sig_n", "sig_n", B, eps=0.01) - h) < 1e-12
    assert abs(f - 3.1973) < 1e-4 and abs(h - 4.0455) < 1e-4
    # ε＝0.005・0.02 は桁と符号だけ（41′ 1）：F の二つ目の損は ε が小さいほど小さい
    vals = [birth_local_bits("F", "sig_n", "sig_n", B, eps=e) for e in (0.005, 0.01, 0.02, 0.5)]
    assert vals == sorted(vals) and all(v > -math.log2(0.11) for v in vals)


def test_first_material_cancels_between_states():
    """一つ目の材料は全状態が b なので、状態の間の差では打ち消し合う（41′ 2、GPT §2 107 行）：
    古い材料の重み w1 を替えても F−U・H−U の差は変わらない。"""
    d = []
    for w1 in (1.0, 0.3, 0.01):
        bits = {st: birth_local_bits(st, "sig_n", "sig_n", B, eps=0.01, w1=w1) for st in "FHU"}
        d.append((bits["F"] - bits["U"], bits["H"] - bits["U"]))
    for x in d[1:]:
        assert abs(x[0] - d[0][0]) < 1e-12 and abs(x[1] - d[0][1]) < 1e-12


def test_same_information_birth():
    """同じ情報の誕生：二つ目の名前を替えても一つ目までの F/H の予測確率は変わらない（41′ 5、GPT §8 1）。
    仮の定義は names1 だけから作る。二つ目が違う名前なら F は外れの損を払う。"""
    shape = defA()
    p1 = provisional_definition(shape, {"seal": "sig_n", "at": "at", "lit": "lit", "open": "open"})
    assert [s.fixed for s in p1.seats] == ["sig_n", "at", "lit", "open"]
    same = birth_local_bits("F", "sig_n", "sig_n", B, eps=0.01)
    diff = birth_local_bits("F", "sig_n", "other", B, eps=0.01)
    assert abs(diff - (-math.log2(0.11) - math.log2(0.01 * 0.89))) < 1e-12 and diff > same


def test_unseen_first_material_back_to_b():
    """一つ目で名前が見えていなかった席は仮の F に名前を入れず b に戻す（41′ 2）。"""
    p = provisional_definition(defA(), {"seal": None, "at": "at", "lit": "lit", "open": "open"})
    assert p.seat("seal").state == "H" and p.seat("seal").hist == ()
    assert birth_local_bits("F", None, "sig_n", B, eps=0.01) == -math.log2(0.11)


def test_question_weights():
    """42‴ 3：問いの記録が無ければ一様。ドア 3・非ドア 1 なら、ドアの 0.75 をドアの仮の問いで等分。
    一度も問われていない種類は 0。"""
    qs = [1, 2, 3, 4]
    kinds = ["door", "nondoor", "nondoor", "nondoor"]
    assert question_weights(qs, kinds, {}) == [0.25] * 4
    w = question_weights(qs, kinds, {"door": 3, "nondoor": 1})
    assert w == [0.75, 1 / 12, 1 / 12, 1 / 12]
    w = question_weights(qs, kinds, {"door": 2, "nondoor": 0})
    assert w == [1.0, 0.0, 0.0, 0.0]


def test_birth_init_sums_table():
    """初期値＝Σ w·Δ。仮の問いの答えは見えていた名前だけ（本人が見ていない名前は使わない）。"""
    material2 = Scene(("d", "s"), (("seal", "sig_e", ("d",)), ("at", "at", ("d", "s")), ("lit", "lit", ("s",)),
                                   ("open", "closed", ("d",))))
    shape = Definition("N", 9, ("d", "s"), (Seat("seal", ("d",), "U", slot=0), Seat("at", ("d", "s"), "U", slot=1),
                                            Seat("lit", ("s",), "U", slot=2), Seat("open", ("d",), "U", slot=3)))
    names1 = {"seal": "sig_e", "at": "at", "lit": "lit", "open": "closed"}
    out = birth_init([defA()], shape, names1, material2, KN, Params(), asked={"door": 2, "nondoor": 2},
                     is_door=door_kind_by_disclosed({"open", "closed"}))
    assert out["kinds"] == {"seal": "nondoor", "at": "nondoor", "lit": "nondoor", "open": "door"}
    assert abs(out["weights"]["open"] - 0.5) < 1e-12 and abs(out["weights"]["seal"] - 0.5 / 3) < 1e-12
    for k, v in out["init"].items():
        assert abs(v - sum(r["w"] * r["delta"] for r in out["table"] if r["seat"] == k)) < 1e-12
    assert {r["y"] for r in out["table"]} == {"sig_e", "at", "lit", "closed"}
    # 仮の問いの場面には伏せた関係の名前が入っていない
    for sc, q in provisional_questions(material2):
        assert q.key not in sc.visible_keys
