"""保持の誤り駆動（受け箱 注意の係 指示 5 の B、走行の列 #14）の参照の計算。

仕様の出どころ（control/受け箱/注意の係_Codex2.md、指示 5 の B、81b19f2e の版の 82–113 行）：
- 開示のあった試行で、注意の学習と同じ「混ぜた損」の勾配を、注意の重みの代わりに席の保持の価値へ流す。
  選び直しも門の判定し直しもしない。log P の腕だけ。
- 対象：開示のあった試行だけ。門を通った候補が無い試行（棄権）では何もしない。候補の集合：注意の学習と同じ（門を通った候補）。
- 候補 d：z_d（注意の項を含む選びの点）、P_d(y)（答える席の分布。席が無ければ全体の頻度表、複数なら等しい重みで混ぜる）。
- π_d＝exp(z_d)／Σ_e exp(z_e)、ρ_d＝π_d P_d(y)／Σ_e π_e P_e(y)。
- 席 s を一段薄くしたとき：Δz_{d,s}＝（薄くした d の選びの点）−（今の d の選びの点）（第二段と同じ再照合の関数で d だけ照合し直す。
  注意の項の変化も含む）、Δℓ_{d,s}＝−ln P_d^薄(y)＋ln P_d(y)。
- 価値の増分（ナット）＝(π_d − ρ_d)·Δz_{d,s} ＋ ρ_d·Δℓ_{d,s}。ln 2 で割ってビット。負も切らない。
- 関門 2〜5（手例、候補一つで規則 A と一致、数値微分、Δz は第二段の再照合と同じ関数）。

導出の確かめ：L＝−ln Σ_e π_e P_e(y) について ∂L/∂z_d＝π_d − ρ_d、∂L/∂ln P_d(y)＝−ρ_d。
よって増分は L の一次の変化（Δz と Δln P＝−Δℓ による）。
"""
from __future__ import annotations

import math
from typing import Mapping

from refcommon import p_hat_dist, thin
from ref_delta_r import Knowledge, Params, _avg, eval_definition, predict
from ref_cstar import T_scene


# ---------------------------------------------------------------- 純粋な関数（関門 2〜4）
def pi_rho(z: Mapping, Py: Mapping) -> tuple[dict, dict]:
    """π＝softmax(z)（温度 1）、ρ_d＝π_d P_d(y)／Σ π_e P_e(y)。"""
    mx = max(z.values())
    w = {d: math.exp(v - mx) for d, v in z.items()}
    s = math.fsum(w.values())
    pi = {d: w[d] / s for d in z}
    den = math.fsum(pi[d] * Py[d] for d in z)
    rho = {d: pi[d] * Py[d] / den for d in z}
    return pi, rho


def mixed_loss(z: Mapping, Py: Mapping) -> float:
    """L＝−ln Σ π_e P_e(y)（ナット）。"""
    pi, _ = pi_rho(z, Py)
    return -math.log(math.fsum(pi[d] * Py[d] for d in z))


def increments(z: Mapping, Py: Mapping, dz: Mapping, dl: Mapping) -> dict:
    """席ごとの価値の増分。dz・dl の鍵は (候補 d, 席 s)。
    返り値：{(d, s): {"sel": (π_d−ρ_d)Δz, "ans": ρ_d Δℓ, "nat": 和, "bits": 和/ln 2}}。"""
    pi, rho = pi_rho(z, Py)
    out = {}
    for key in set(dz) | set(dl):
        d = key[0]
        sel = (pi[d] - rho[d]) * dz.get(key, 0.0)
        ans = rho[d] * dl.get(key, 0.0)
        out[key] = {"sel": sel, "ans": ans, "nat": sel + ans, "bits": (sel + ans) / math.log(2)}
    return out


# ---------------------------------------------------------------- 模型の形の上で（ref_delta_r の評価を使う）
def _answer_prob(ev: dict, y: str, kn: Knowledge) -> tuple[float, str]:
    """P_d(y)：答える席が一つならその分布、複数なら等しい重みで混ぜる、無ければ全体の頻度表 p̂（指示 5 の B の文言どおり）。"""
    if ev["answer_dists"]:
        return _avg(ev["answer_dists"]).get(y, 0.0), ("one_seat" if len(ev["answer_dists"]) == 1 else "mixed_seats")
    return p_hat_dist(kn.p_hat_counts).get(y, 0.0), "p_hat"


def error_driven(memory: list, scene, question, kn: Knowledge, params: Params, *, disclosed: bool = True) -> dict:
    """一試行の誤り駆動の増分。開示が無い・門を通った候補が無いなら空（関門 6）。
    候補 d の F/H の席 s ごとに、d だけを薄くした席で評価し直し（ref_delta_r.eval_definition＝第二段の再照合と
    同じ関数）、Δz・Δℓ・増分を出す。選び直し・門の判定し直しはしない。

    Δℓ は二通り出す（spec_notes (E)-1、選んでいない）：
      dl_formula：式どおり −ln P_d^薄(y)＋ln P_d(y)（再照合で答える席が変われば答える席以外でも 0 でない）。
      dl_answer_only：s が今の d の答える席（又はその一つ）のときだけ式の値、ほかは 0。
    """
    if not disclosed:
        return {"rows": [], "skipped": "no_disclosure"}
    base = predict(memory, scene, question, kn, params)
    cands = [e for e in base["evals"] if e["gate"] and e["z"] != -math.inf]
    if not cands:
        return {"rows": [], "skipped": "abstain"}
    y = question.y
    z = {e["R"]: e["z"] for e in cands}
    Py, case = {}, {}
    for e in cands:
        Py[e["R"]], case[e["R"]] = _answer_prob(e, y, kn)
    T_x = T_scene(scene)
    by_name = {d.name: d for d in memory}
    dz, dl_f, dl_a, extra = {}, {}, {}, {}
    for e in cands:
        d = by_name[e["R"]]
        for s in d.seats:
            t = thin(s)
            if t is None:
                continue
            ev2 = eval_definition(d.replace_seat(t), scene, question, kn, params, T_x)
            P2, case2 = _answer_prob(ev2, y, kn)
            k = (d.name, s.key)
            dz[k] = ev2["z"] - e["z"] if ev2["z"] != -math.inf else -math.inf
            f = (-math.log(P2) + math.log(Py[d.name])) if P2 > 0 and Py[d.name] > 0 else math.nan
            dl_f[k] = f
            dl_a[k] = f if s.key in e["answer_seats"] else 0.0
            extra[k] = {"state": s.state, "thinned_to": t.state, "z_before": e["z"], "z_after": ev2["z"],
                        "P_before": Py[d.name], "P_after": P2, "case_after": case2, "gate_after": ev2["gate"],
                        "answer_seats_after": ev2["answer_seats"],
                        "nonfinite": not (math.isfinite(dz[k]) and math.isfinite(f))}
    inc_f = increments(z, Py, {k: v for k, v in dz.items()}, dl_f)
    inc_a = increments(z, Py, dz, dl_a)
    pi, rho = pi_rho(z, Py)
    rows = []
    for k in sorted(extra):
        rows.append({"R": k[0], "seat": k[1], **extra[k], "dz": dz[k], "dl_formula": dl_f[k],
                     "dl_answer_only": dl_a[k], "pi": pi[k[0]], "rho": rho[k[0]],
                     "sel": inc_f[k]["sel"], "ans_formula": inc_f[k]["ans"], "ans_answer_only": inc_a[k]["ans"],
                     "nat_formula": inc_f[k]["nat"], "nat_answer_only": inc_a[k]["nat"],
                     "bits_formula": inc_f[k]["bits"], "bits_answer_only": inc_a[k]["bits"],
                     "dl_differs": not (dl_f[k] == dl_a[k] or (math.isnan(dl_f[k]) and math.isnan(dl_a[k])))})
    return {"rows": rows, "pi": pi, "rho": rho, "z": z, "Py": Py, "case": case, "base": base}
