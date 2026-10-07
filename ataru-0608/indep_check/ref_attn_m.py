"""(d) 全部入りの注意の m・z・混ぜた分布・注意の重み a の学びの参照の計算。

仕様の出どころ：
- 受け箱 注意の係_Codex2.md 指示 2（21–36 行）：
  2.「基底 b̄_j は、U がその位置で実際に使う分布（主の U と同じ、位置で条件づけない b。名前の適格範囲・絞り方・
     正規化・平滑化・予測前のスナップショットまで同じもの）。U は m＝0 になる。」
  3.「m_dj＝ln(b̄_j(x_j)／P_dj(x_j))／(−ln ε)（ε＝0.01）。負にもなる。0 で切らない。全候補で共通の可視位置を使い、
     対応の無い位置は P＝基底・m＝0。伏せた答えの位置は入れない。」
  4.「z_d＝ln Q_d − Σ_j a_j m_dj。a の初期値 0、範囲 0〜10、η＝0.1、自然対数。開示の無い試行では更新しない。
     全候補で Q＝0 のときは softmax を計算せず、42⁵ の背景への復帰。」
  5.「注意の学習の損は、各候補の答えの分布を softmax（温度 1）の重みで混ぜたもの（42′ の mixture と同じ）。」
- GPT 記憶の値段の返事 §5（227–270 行）：m の式、基底の共通項は argmax・softmax で打ち消し合う。
  §7（298–364 行）：m°＝ln[b̄/P]/L_ε、F の不一致で m°＝1、a(0)＝0、0≤a≤10、η＝0.1、p̃＝Σπ_d P_d(y)、L̃＝−ln p̃、
  a＝0・温度 1 では softmax(ln Q) は Q に比例。
- 委任書 42′ 5（938 行）：注意の重み a の学習は mixture の損を代理として使う。−ln と −log₂ の係数 1/ln 2 を記録。
- 委任書 42 ■1（848 行）：注意の基底の混ぜの ε も --logp-eps と同じ値に従う。

a の更新を「mixture の損の勾配を下る一歩を [0,10] へ射影」と読んだ（GPT 記憶の値段 §7 332–337 行の
「単純な勾配降下・同じ境界への射影」）。実装の第一段の更新がこれと同じかは仕様が実装に確かめさせている点で、
ここでは参照としてこの読みを置く（spec_notes (d)-曖昧 3）。
"""
from __future__ import annotations

import math
from typing import Callable, Mapping

A_MIN, A_MAX, ETA, EPS_M = 0.0, 10.0, 0.1, 0.01


def m_value(P_x: float, bbar_x: float, eps: float = EPS_M) -> float:
    """m°＝ln(b̄_j(x_j)／P_dj(x_j))／(−ln ε)。負にもなる（0 で切らない）。
    P＝0 なら +inf、b̄＝0 かつ P＞0 なら −inf、両方 0 なら nan（仕様に書かれていない場合。spec_notes (d)-曖昧 4）。"""
    if not 0 < eps < 1:
        raise ValueError(eps)
    L = -math.log(eps)
    if P_x > 0 and bbar_x > 0:
        return math.log(bbar_x / P_x) / L
    if P_x == 0 and bbar_x > 0:
        return math.inf
    if P_x > 0 and bbar_x == 0:
        return -math.inf
    return math.nan


def m_vector(visible: Mapping, mapped_dist: Mapping, bbar: Mapping, eps: float = EPS_M) -> dict:
    """全候補で共通の可視位置 j（visible：位置の鍵→見えている名前 x_j）について m_dj を作る。
    mapped_dist：位置の鍵→その位置に対した d の席の予測分布 P_dj（値付けと同じ P）。対の無い位置は入れない。
    bbar：位置の鍵→基底 b̄_j。対の無い位置は P＝基底なので m＝0。伏せた位置は visible に入れない。"""
    out = {}
    for j, x in visible.items():
        if j in mapped_dist:
            out[j] = m_value(mapped_dist[j].get(x, 0.0), bbar[j].get(x, 0.0), eps)
        else:
            out[j] = 0.0
    return out


def z_value(Q: float | None, a: Mapping, m: Mapping, key_of: Callable) -> float:
    """z_d＝ln Q_d − Σ_j a_{k(j)} m_dj（自然対数）。key_of(j) は位置 j の注意の鍵（k2）。
    同じ鍵の位置が複数あれば各位置の項を全部足す（spec_notes (d)-曖昧 2）。Q＝0・None は −inf。"""
    if Q is None or Q <= 0:
        return -math.inf
    # a＝0 の項は m が無限でも 0 とする（0·∞ を nan にしない）。
    s = math.fsum(a.get(key_of(j), 0.0) * mj for j, mj in m.items() if a.get(key_of(j), 0.0) != 0.0)
    return math.log(Q) - s


def softmax(z: Mapping) -> dict | None:
    """温度 1 の softmax。全部 −inf（全候補で Q＝0）なら None（softmax を計算しない：指示 2 の 4）。"""
    finite = {k: v for k, v in z.items() if v != -math.inf}
    if not finite:
        return None
    mx = max(finite.values())
    w = {k: math.exp(v - mx) for k, v in finite.items()}
    s = math.fsum(w.values())
    return {k: (w.get(k, 0.0) / s) for k in z}


def mixture_prob(pi: Mapping, dists: Mapping, y: str) -> float:
    """p̃(y)＝Σ_k π_k P_k(y)（委任書 42′ 1、GPT 四つの判断 §3 187–189 行）。"""
    return math.fsum(pi[k] * dists[k].get(y, 0.0) for k in pi)


def mixture_loss_nat(pi, dists, y) -> float:
    """L̃＝−ln p̃(y)（自然対数。ビットにするには 1/ln 2 を掛ける）。"""
    p = mixture_prob(pi, dists, y)
    return math.inf if p <= 0 else -math.log(p)


def grad_mixture(z_parts: Mapping, a: Mapping, dists: Mapping, y: str) -> dict:
    """∂L̃/∂a_k（対応・候補・門を固定した滑らかな範囲での勾配）。
    z_parts：候補 d → (ln Q_d, {位置の鍵 j: (k(j), m_dj)})。
    z_d＝ln Q_d − Σ_j a_{k(j)} m_dj、π＝softmax(z)、p̃＝Σ π_d P_d(y)、L̃＝−ln p̃ から、
      ∂L̃/∂a_k＝(1/p̃) Σ_d P_d(y) π_d (M_dk − M̄_k)、M_dk＝Σ_{j:k(j)=k} m_dj、M̄_k＝Σ_e π_e M_ek。"""
    z = {}
    Mdk = {}
    for d, (lnQ, ms) in z_parts.items():
        acc = {}
        for _j, (k, mj) in ms.items():
            acc[k] = acc.get(k, 0.0) + mj
        Mdk[d] = acc
        z[d] = (lnQ - math.fsum(a.get(k, 0.0) * v for k, v in acc.items() if a.get(k, 0.0) != 0.0)
                if lnQ != -math.inf else -math.inf)
    pi = softmax(z)
    if pi is None:
        return {}
    p = mixture_prob(pi, dists, y)
    keys = set().union(*(set(v) for v in Mdk.values())) if Mdk else set()
    out = {}
    for k in keys:
        mbar = math.fsum(pi[e] * Mdk[e].get(k, 0.0) for e in pi)
        out[k] = math.fsum(dists[d].get(y, 0.0) * pi[d] * (Mdk[d].get(k, 0.0) - mbar) for d in pi) / p
    return out


def update_a(a: Mapping, grad: Mapping, *, disclosed: bool, eta: float = ETA, lo: float = A_MIN,
             hi: float = A_MAX) -> dict:
    """a_k ← clip(a_k − η ∂L̃/∂a_k, 0, 10)。開示の無い試行では更新しない（指示 2 の 4）。"""
    out = dict(a)
    if not disclosed:
        return out
    for k, g in grad.items():
        out[k] = min(hi, max(lo, out.get(k, 0.0) - eta * g))
    return out
