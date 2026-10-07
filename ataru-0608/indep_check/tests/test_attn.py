"""(d) 注意の m・z・学びの参照の検査（受け箱 注意の係 指示 2 の 8 の手例）。"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from refcommon import mix_eps  # noqa: E402
from ref_attn_m import (grad_mixture, m_value, m_vector, mixture_loss_nat, softmax, update_a,  # noqa: E402
                        z_value)


def test_U_has_m_zero():
    """U の分布は基底と同じ（b̄＝P_U）なので m＝0。"""
    b = {"sig_n": 0.9, "sig_e": 0.1}
    for x in b:
        assert m_value(b[x], b[x], 0.01) == 0.0


def test_F_mismatch_m_is_one():
    """F の不一致：P＝εb(x)、b̄＝b → m°＝ln(1/ε)/(−ln ε)＝1（GPT 記憶の値段 §7 300–324 行）。"""
    b = {"f": 0.1, "x": 0.9}
    for eps in (0.005, 0.01, 0.02, 0.5):
        P = mix_eps({"f": 1.0}, b, eps)
        assert abs(m_value(P["x"], b["x"], eps) - 1.0) < 1e-12


def test_F_match_value():
    """F の一致：b(f)＝0.1、ε＝0.01 → P＝0.991、m°＝ln(0.1/0.991)/ln 100 ≈ −0.4980（未正規化で −2.294：GPT §7 308 行）。"""
    b = {"f": 0.1, "x": 0.9}
    P = mix_eps({"f": 1.0}, b, 0.01)
    m = m_value(P["f"], b["f"], 0.01)
    assert abs(m * math.log(100) - math.log(0.1 / 0.991)) < 1e-12
    assert abs(m * math.log(100) - (-2.2935)) < 1e-3


def test_unmapped_position_back_to_base():
    vis = {"j1": "a", "j2": "b"}
    bbar = {"j1": {"a": 0.5, "b": 0.5}, "j2": {"a": 0.5, "b": 0.5}}
    m = m_vector(vis, {"j1": {"a": 0.9, "b": 0.1}}, bbar, 0.01)
    assert m["j2"] == 0.0 and m["j1"] < 0


def test_common_base_cancels_in_softmax():
    """全候補が位置 j に席を対させているなら、b̄_j を替えても softmax は変わらない（GPT §5 263–270 行）。"""
    vis = {"j": "a"}
    Pd = {"d1": {"a": 0.8, "b": 0.2}, "d2": {"a": 0.3, "b": 0.7}}
    Q = {"d1": 0.4, "d2": 0.6}
    a = {"a": 2.0}
    out = []
    for base in ({"a": 0.5, "b": 0.5}, {"a": 0.05, "b": 0.95}):
        z = {d: z_value(Q[d], a, m_vector(vis, {"j": Pd[d]}, {"j": base}, 0.01), lambda j: vis[j]) for d in Pd}
        out.append(softmax(z))
    for d in Pd:
        assert abs(out[0][d] - out[1][d]) < 1e-12


def test_same_name_multiple_positions_add():
    """同じ名前（同じ鍵）の位置が二つあれば、z には両方の項が入る。"""
    m = {"j1": 0.5, "j2": 0.25}
    z = z_value(1.0, {"k": 2.0}, m, lambda j: "k")
    assert abs(z - (0.0 - 2.0 * 0.75)) < 1e-12


def test_a_zero_gives_argmax_Q_and_softmax_proportional_to_Q():
    Q = {"d1": 0.2, "d2": 0.5, "d3": 0.3}
    z = {d: z_value(q, {}, {"j": 1.0}, lambda j: "k") for d, q in Q.items()}
    pi = softmax(z)
    for d in Q:
        assert abs(pi[d] - Q[d] / sum(Q.values())) < 1e-12
    assert max(z, key=z.get) == "d2"


def test_all_Q_zero_no_softmax():
    z = {"d1": z_value(0.0, {}, {}, lambda j: j), "d2": z_value(None, {}, {}, lambda j: j)}
    assert softmax(z) is None


def test_gradient_finite_difference():
    """∂L̃/∂a を有限差分で確かめる（対応・候補を固定した滑らかな範囲：GPT 四つの判断 §8 7）。"""
    parts = {"d1": (math.log(0.4), {"j1": ("k1", 0.7), "j2": ("k2", -0.3)}),
             "d2": (math.log(0.6), {"j1": ("k1", -0.2), "j2": ("k2", 1.0)}),
             "d3": (math.log(0.1), {"j1": ("k1", 0.0), "j2": ("k1", 0.4)})}
    dists = {"d1": {"y": 0.7, "n": 0.3}, "d2": {"y": 0.1, "n": 0.9}, "d3": {"y": 0.5, "n": 0.5}}
    a = {"k1": 0.8, "k2": 1.5}

    def loss(a):
        z = {d: lq - sum(a[k] * m for _j, (k, m) in ms.items()) for d, (lq, ms) in parts.items()}
        return mixture_loss_nat(softmax(z), dists, "y")

    g = grad_mixture(parts, a, dists, "y")
    h = 1e-6
    for k in a:
        ap, am = dict(a), dict(a)
        ap[k] += h
        am[k] -= h
        fd = (loss(ap) - loss(am)) / (2 * h)
        assert abs(fd - g[k]) < 1e-7, (k, fd, g[k])


def test_update_clip_and_no_disclosure():
    a = {"k": 9.99, "j": 0.01}
    g = {"k": -1.0, "j": 1.0}
    new = update_a(a, g, disclosed=True)
    assert new["k"] == 10.0 and new["j"] == 0.0
    assert update_a(a, g, disclosed=False) == a
