"""保持の誤り駆動の参照の計算（受け箱 注意の係 指示 6 で直した仕様。指示 5 の B を置き換え）。

仕様の出どころ（control/受け箱/注意の係_Codex2.md、151a5150 の版）：
- 指示 5 の B（65–118 行のうち B の部分）：開示のあった試行だけ、log P の腕だけ、門を通った候補が無い試行（棄権）では何もしない、
  候補の集合は注意の学習と同じ（門を通った候補）、z_d は注意の項を含む選びの点、P_d(y) は答える席の分布（席が無ければ
  全体の頻度表、複数なら等しい重みで混ぜる）、π＝softmax(z)（温度 1）、ρ_d＝π_d p_d／Σ π_e p_e、Δz は第二段と同じ再照合の
  関数で d だけを照合し直した点の差（注意の項の変化を含む）、負も切らない。
- 指示 6（119–148 行）で置き換えた所：
  1. 価値＝固定した候補の集合での混ぜた損の厳密な差：ln{1＋π_d(e^{Δz}−1)} − ln{1＋ρ_d(e^{Δz−Δℓ}−1)}（ナット、ln 2 で割ってビット）。
     一次の値 (π_d−ρ_d)Δz＋ρ_dΔℓ は診断として記録だけ。log1p・expm1 で計算する。
  2. Δℓ は、どの席を薄くしたときも、照合し直した d の答えの分布から取り直す：Δℓ＝−ln P′_d(y)＋ln P_d(y)。
  3. ℓ_d は第二段・A と同じ log_cost（確率 0 の名前は既存の逃げの符号の長さ）。混ぜるときの確率は p_d＝exp(−ℓ_d)（ナット）。
     Q′＝0 になったら止まって報告（参照では印を付けて返す）。
  4. 予測の直前の記憶・a・b・門・候補の集合を固定（参照は渡された Knowledge をそのまま使う純粋な関数）。
  5. 候補の集合は予測の時点の門で固定。薄くした d が門の下に落ちても集合に残して評価。門の下の競合は評価しない。
     診断：試行ごとに「薄くすると d が門の下に落ちる席の数」。
  6. 誕生の初期値は第二段の (b) と同じ仮の問い（42″ 2、42‴ 2・3）、価値だけ 1 の式。
導出：p̃＝Σπ_e p_e。d だけ z_d→z_d＋Δz、p_d→p_d e^{−Δℓ} とすると
  p̃′＝p̃·{1＋ρ_d(e^{Δz−Δℓ}−1)}／{1＋π_d(e^{Δz}−1)}、よって −ln p̃′＋ln p̃ が上の式。
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable, Mapping

from refcommon import bits_of, code_lengths, p_hat_dist, thin
from ref_delta_r import Knowledge, Params, _avg, eval_definition, predict
from ref_cstar import T_scene

LN2 = math.log(2)


# ---------------------------------------------------------------- 純粋な関数
def softmax_z(z: Mapping) -> dict:
    mx = max(z.values())
    w = {d: math.exp(v - mx) for d, v in z.items()}
    s = math.fsum(w.values())
    return {d: w[d] / s for d in z}


def pi_rho(z: Mapping, p: Mapping) -> tuple[dict, dict]:
    """π＝softmax(z)（温度 1）、ρ_d＝π_d p_d／Σ π_e p_e（p_d＝exp(−ℓ_d)）。"""
    pi = softmax_z(z)
    den = math.fsum(pi[d] * p[d] for d in z)
    return pi, {d: pi[d] * p[d] / den for d in z}


def mixed_loss(z: Mapping, p: Mapping) -> float:
    """L＝−ln Σ π_e p_e（ナット）。直接の計算（検査用）。"""
    pi = softmax_z(z)
    return -math.log(math.fsum(pi[d] * p[d] for d in z))


def exact_increment(pi_d: float, rho_d: float, dz: float, dl: float) -> float:
    """厳密な差（ナット）＝log1p(π·expm1(Δz)) − log1p(ρ·expm1(Δz−Δℓ))（指示 6 の 1）。"""
    return math.log1p(pi_d * math.expm1(dz)) - math.log1p(rho_d * math.expm1(dz - dl))


def first_order_increment(pi_d: float, rho_d: float, dz: float, dl: float) -> float:
    """一次の値（診断）＝(π−ρ)Δz＋ρΔℓ。"""
    return (pi_d - rho_d) * dz + rho_d * dl


def increments(z: Mapping, p: Mapping, dz: Mapping, dl: Mapping) -> dict:
    """席ごと（鍵は (候補 d, 席 s)）の厳密な増分と一次の値。p は p_d＝exp(−ℓ_d)。"""
    pi, rho = pi_rho(z, p)
    out = {}
    for key in set(dz) | set(dl):
        d = key[0]
        a, b = dz.get(key, 0.0), dl.get(key, 0.0)
        ex = exact_increment(pi[d], rho[d], a, b)
        fo = first_order_increment(pi[d], rho[d], a, b)
        out[key] = {"exact_nat": ex, "exact_bits": ex / LN2, "first_nat": fo, "first_bits": fo / LN2,
                    "sel": (pi[d] - rho[d]) * a, "ans": rho[d] * b}
    return out


# ---------------------------------------------------------------- 模型の形の上で
def answer_cost_nat(ev: dict, y: str, kn: Knowledge) -> tuple[float, str, bool]:
    """ℓ_d（ナット）：答える席の分布（一つ・複数は等しい重みで混ぜる・無ければ全体の頻度表 p̂）の log_cost。
    確率 0 の名前は L_of の逃げの符号の長さ（ビット）×ln 2。返り値 (ℓ, 場合, 逃げたか)。"""
    if ev["answer_dists"]:
        P, case = _avg(ev["answer_dists"]), ("one_seat" if len(ev["answer_dists"]) == 1 else "mixed_seats")
    else:
        P, case = p_hat_dist(kn.p_hat_counts), "p_hat"
    bits, esc = bits_of(P, y, code_lengths(kn.p_hat_counts))
    return bits * LN2, case, esc


def error_driven(memory: list, scene, question, kn: Knowledge, params: Params, *, disclosed: bool = True) -> dict:
    """一試行の誤り駆動の増分。開示が無い・門を通った候補が無い（棄権）なら空。
    候補（予測の時点で門を通り z が有限の定義）の F/H の席 s ごとに、d だけを薄くして eval_definition（第二段の再照合）で
    評価し直し、Δz・Δℓ・厳密な増分・一次の値を出す。候補の集合・門は固定（選び直し・門の判定し直しをしない）。"""
    if not disclosed:
        return {"rows": [], "skipped": "no_disclosure", "n_below_gate": 0, "n_Q_zero": 0}
    base = predict(memory, scene, question, kn, params)
    cands = [e for e in base["evals"] if e["gate"] and e["z"] != -math.inf]
    if not cands:
        return {"rows": [], "skipped": "abstain", "n_below_gate": 0, "n_Q_zero": 0}
    y = question.y
    z = {e["R"]: e["z"] for e in cands}
    ell, case = {}, {}
    for e in cands:
        ell[e["R"]], case[e["R"]], _esc = answer_cost_nat(e, y, kn)
    p = {d: math.exp(-v) for d, v in ell.items()}
    pi, rho = pi_rho(z, p)
    T_x = T_scene(scene)
    by_name = {d.name: d for d in memory}
    rows = []
    for e in cands:
        d = by_name[e["R"]]
        for s in d.seats:
            t = thin(s)
            if t is None:
                continue
            ev2 = eval_definition(d.replace_seat(t), scene, question, kn, params, T_x)
            l2, case2, esc2 = answer_cost_nat(ev2, y, kn)
            q_zero = ev2["z"] == -math.inf
            dz = ev2["z"] - e["z"] if not q_zero else -math.inf
            dl = l2 - ell[d.name]
            ex = exact_increment(pi[d.name], rho[d.name], dz, dl)
            fo = first_order_increment(pi[d.name], rho[d.name], dz, dl) if not q_zero else -math.inf
            rows.append({"R": d.name, "seat": s.key, "state": s.state, "thinned_to": t.state,
                         "pi": pi[d.name], "rho": rho[d.name], "z_before": e["z"], "z_after": ev2["z"], "dz": dz,
                         "ell_before": ell[d.name], "ell_after": l2, "dl": dl, "escaped_after": esc2,
                         "case_before": case[d.name], "case_after": case2,
                         "answer_seats_before": e["answer_seats"], "answer_seats_after": ev2["answer_seats"],
                         "exact_nat": ex, "exact_bits": ex / LN2, "first_nat": fo, "first_bits": fo / LN2,
                         "below_gate_after": not ev2["gate"], "Q_zero_after": q_zero,
                         # 診断：答える席でない席を薄くして Δℓ が 0 でない（指示 5 の旧い分岐とは分かれる所）
                         "dl_from_non_answer_seat": (s.key not in e["answer_seats"]) and dl != 0.0})
    return {"rows": rows, "pi": pi, "rho": rho, "z": z, "ell": ell, "case": case, "base": base,
            "n_below_gate": sum(r["below_gate_after"] for r in rows),
            "n_Q_zero": sum(r["Q_zero_after"] for r in rows)}


def birth_init_error_driven(memory: list, shape, names1: Mapping, material2, kn: Knowledge, params: Params, *,
                            asked: Mapping, is_door: Callable, unseen_state: str = "H_empty") -> dict:
    """誕生の初期値（指示 6 の 6）：第二段の (b)（ref_birth_init.birth_init）と同じ仮の定義・仮の問い・重みで、
    価値だけ厳密な差の式にする。各仮の問いの候補の集合（門を通った定義）で固定。
    仮の定義が、その仮の問いで門を通った候補に入らなければ、その問いからの寄与は 0（π＝ρ＝0 と同じ。spec_notes (E)-8）。"""
    from ref_birth_init import provisional_definition, provisional_questions, question_weights
    prov = provisional_definition(shape, names1, unseen_state=unseen_state)
    qs = provisional_questions(material2)
    kinds = ["door" if is_door(sc, q) else "nondoor" for sc, q in qs]
    ws = question_weights(qs, kinds, asked)
    init = {s.key: 0.0 for s in prov.seats}
    table = []
    for (sc, q), kind, w in zip(qs, kinds, ws):
        out = error_driven(list(memory) + [prov], sc, q, kn, replace(params, loss="top1"))
        mine = [r for r in out["rows"] if r["R"] == prov.name]
        for r in mine:
            init[r["seat"]] += w * r["exact_nat"]
            table.append({"question": q.key, "y": q.y, "kind": kind, "w": w, **r})
        if not mine:
            table.append({"question": q.key, "y": q.y, "kind": kind, "w": w, "R": prov.name, "seat": None,
                          "note": out.get("skipped") or "仮の定義が候補に入らない"})
    return {"init_nat": init, "init_bits": {k: v / LN2 for k, v in init.items()}, "table": table}
