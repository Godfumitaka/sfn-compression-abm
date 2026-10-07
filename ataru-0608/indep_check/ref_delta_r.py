"""(b) 第二段の Δr の参照の計算：席を一つ薄くした記憶で、照合から全部やり直して全候補を選び直し、
最終の答えの損の差 Δr_i＝r(M^{-i},x,y) − r(M,x,y) を出す。

仕様の出どころ（control/2026-10-06_渡す委任書_Claude.md の行）：
- 42 ■1（844–851 行）：開示のあった試行 t、記憶の各席 i（F か H）、一段薄くした記憶（F→H、H→U）。
  最終の答えは全候補の選びの点 z_d で選んだ定義の答え。0/ℓ の損：選ばれた定義の答えが y なら 0、違えば ℓ(y)。
- 42′ 1（930–934 行）：top1：今の選び方（門・同点・答える位置を含む）で選んだ d* の答える席の分布 P_{d*}(y)
  で r＝−log₂ P_{d*}(y)。門を通る定義が無い・答える席が無いなら b(y)。温度は使わない。mixture：p̃＝Σπ_k P_k(y)、
  候補が空なら b。0/ℓ は 42 の (α)（黙れば ℓ(y)）。
- 42′ 2（935 行）：Δr は負にもなる。0 に丸めない。
- 42′ 3（936 行）：薄くした席を含む定義だけ照合をやり直す方式が「今の貪欲な照合器に対して近似の無い計算」。
  この参照は、全定義を毎回総当たりでやり直す（遅いが近似が無い）。ただし照合は sme2017 の貪欲な探索ではなく
  max_M E[S0] の総当たり（ref_cstar.best_mappings）。spec_notes (b)-曖昧 1。
- 42′ 4（937 行）：反実仮想で本体の記憶・履歴・b・注意・使用回数・減衰の時刻・乱数を変えない
  （この関数は入力を変えない純粋な関数。新しい Definition を作るだけ）。
- 42″ 1（954 行）：確率 0 は L_of の退避符号の長さで払う（前後のどちらが 0 でも有限の差）。
- 42⁗（1081–1084 行）：--stage2-scope chosen は、実際に選ばれた定義の席だけを薄くする。
- 42⁵ 1〜3（1096–1100 行）：門を通る定義が無い・答える席が無い・問う席の形と階が分からない場合は p̂（形と階で
  絞らない）。形と階が分かる場合だけ絞った b。答える席の候補が複数なら等しい重みで混ぜる。どの場合かを記録。
- 受け箱 注意の係 指示 2 の 7（33 行）：反実仮想では a と b を固定し、薄くした席の P・C* の点・注意の m・選び・門・
  答えを全部計算し直す。
- 41′ 3（914 行）：門は C* の点とは別の仕組み。F は同じ名前、H は履歴にある名前で対になった席を支持に数え、
  U は分母に入れない。
- 門の必要支持数：古い版 abm/agent_runtime._need（ceil(0.67·n)）。選びの順：古い版 smeshared._definition_choice
  （N3→席数→新しさ、残りは同点）。ここでは N3 の代わりに z（a＝0 なら ln Q で順は N3 と同じ）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping

from refcommon import (Definition, Question, Scene, Seat, L_of, bits_of, code_lengths, normalize, p_hat_dist,
                       seat_dist, thin)
from ref_cstar import Q_P, T_def, T_scene, best_mappings, check_mapping, cstar_score, match_dists, q_from_dists
from ref_attn_m import EPS_M, m_vector, mixture_prob, softmax, z_value


@dataclass(frozen=True)
class Params:
    eps: float = 0.01                 # --logp-eps（41 ■4 (1)、41′ 1 で 0.01 が主の見込み）
    alpha: float = 1.0                # --h-dirichlet 1（41 ■3）
    match_eps: str = "0"              # --match-eps 0|shared（41 ■4 (1)）
    eps_m: float | None = None        # 注意の m の ε。None なら eps と同じ（42 ■1 848 行、指示 2 の 3 は 0.01）
    tau: float = 0.67                 # 門（abm/domains.AgentConfig.tau_acc の既定）
    loss: str = "top1"                # top1 | zero_ell | mixture（42′ 1）
    gate_order: str = "select_then_gate"   # 古い版：z（N3）で一つ選び、その定義が門を通らなければ黙る。
                                            # "gate_then_select" は門を通る定義の中で選ぶ読み（spec_notes (b)-曖昧 2）
    support_hidden: bool = True       # 伏せた位置に対した F/H の席を支持に数える（古い版のまま。(b)-曖昧 3）
    mixture_pool: str = "q_pos"       # mixture の候補：Q＞0 の全定義（"gate_pass" なら門を通るものだけ。(b)-曖昧 6）
    attention: bool = True            # 注意を外す構成なら False（z＝ln Q）
    use_cstar: bool = True            # C* を外す構成は今の照合（この参照では未実装。(b)-曖昧 9）


@dataclass(frozen=True)
class Knowledge:
    """予測前に固定する本人の知識（反実仮想でも変えない：42′ 4、指示 2 の 7）。"""
    b_of: Callable                     # (定義, 席) → その席に U が使う b（腕 L の絞った b）
    bbar_of: Callable                  # (場面, 位置の鍵) → 注意の基底 b̄_j
    p_hat_counts: Mapping              # 全体の名前の頻度表（回数）
    a: Mapping = field(default_factory=dict)   # 注意の重み（k2 の鍵 → a）
    key_of: Callable = staticmethod(lambda scene, j: scene.name_of(j))   # k2 の鍵（既定は関係の名前。(d)-曖昧 1）
    shape_b: Callable = staticmethod(lambda scene, q: None)   # 問う席の形と階が分かるときの絞った b、分からなければ None


# ---------------------------------------------------------------- 一つの定義の評価
def _mapped_args(seat: Seat, M: Mapping, ent: Mapping):
    """席の引数の写し：物は物の対応、席は関係の対応で写す。一つでも写せなければ None。"""
    out = []
    for a in seat.args:
        if a in ent:
            out.append(ent[a])
        elif a in M:
            out.append(M[a])
        else:
            return None
    return tuple(out)


def answer_seats(defn: Definition, scene: Scene, M: Mapping, ent: Mapping, question: Question) -> list:
    """答える席：問いの位置に対した席（問いの位置が伏せた節として場面にある場合）か、対の無い席で、
    引数の写しが問いの引数と同じもの（古い版 v39.score_answers の pos_ok と同じ位置の決め方）。
    spec_notes (b)-曖昧 4。"""
    out = []
    for s in sorted(defn.seats, key=lambda s: s.slot):
        if M.get(s.key) == question.key:
            out.append(s)
        elif s.key not in M and _mapped_args(s, M, ent) == tuple(question.args):
            out.append(s)
    return out


def support_count(defn: Definition, scene: Scene, M: Mapping, params: Params) -> int:
    """門の支持（41′ 3）：F は場面の名前が固定名と同じ関係に対した席、H は場面の名前が履歴（回数≥1）にある関係に
    対した席。U は数えない。伏せた位置に対した F/H は support_hidden なら数える。"""
    n = 0
    for s in defn.seats:
        if s.state == "U" or s.key not in M:
            continue
        x = scene.name_of(M[s.key])
        if x is None:
            n += params.support_hidden
        elif s.state == "F" and x == s.fixed:
            n += 1
        elif s.state == "H" and s.counts().get(x, 0) > 0:
            n += 1
    return n


def need(tau: float, n: int) -> int:
    """古い版 abm/agent_runtime._need の比読み：ceil(τ·n)（τ＜1）。"""
    if tau >= 1.0:
        return max(n - int(round(tau - 1.0)), 1)
    return math.ceil(tau * n)


def eval_definition(defn: Definition, scene: Scene, question: Question, kn: Knowledge, params: Params,
                    T_x: float, fixed_M: Mapping | None = None) -> dict:
    """一つの定義：C* の最良の対応・S_P・Q_P・門・m・z・答える席の分布。
    fixed_M を渡すと照合をやり直さず、その対応のまま点を計算し直す（42 ■3・42′ 3 の「対応を固定する近似」の
    比べ用。既定はやり直し）。"""
    Pm = match_dists(defn, kn.b_of, eps=params.eps, alpha=params.alpha, match_eps=params.match_eps)
    Ps = {s.key: seat_dist(s, kn.b_of(defn, s), eps=params.eps, alpha=params.alpha, purpose="score")
          for s in defn.seats}
    if fixed_M is not None:
        args = [dict(fixed_M)] if fixed_M else []
        S = cstar_score(defn, scene, fixed_M, q_from_dists(defn, scene, fixed_M, Pm)) if fixed_M else 0.0
    else:
        S, args = best_mappings(defn, scene, Pm)
    args = sorted(args, key=lambda M: sorted(M.items()))
    M = args[0] if args else {}
    ent = check_mapping(defn, scene, M) if M else {}
    Td = T_def(defn)
    Q = Q_P(S, Td, T_x) if args else 0.0
    sup = support_count(defn, scene, M, params)
    n = defn.n_FH()
    gate = sup >= need(params.tau, n)
    visible = {k: x for k, x, _a in scene.visible}
    mapped_dist = {M[s.key]: Ps[s.key] for s in defn.seats if M.get(s.key) in visible}
    bbar = {j: kn.bbar_of(scene, j) for j in visible}
    eps_m = params.eps_m if params.eps_m is not None else params.eps
    m = m_vector(visible, mapped_dist, bbar, eps_m)
    a = kn.a if params.attention else {}
    z = z_value(Q, a, m, lambda j: kn.key_of(scene, j))
    seats = answer_seats(defn, scene, M, ent, question)
    # 写しの同点で、別の対応が別の支持・答える席を与えるかを記録する（実装の乱数の同点は再現できない）
    tie_differs = False
    for M2 in args[1:]:
        e2 = check_mapping(defn, scene, M2)
        if (support_count(defn, scene, M2, params) != sup
                or [s.key for s in answer_seats(defn, scene, M2, e2, question)] != [s.key for s in seats]):
            tie_differs = True
    return {"R": defn.name, "registered_at": defn.registered_at, "n": n, "S_P": S, "T_d": Td, "T_x": T_x, "Q": Q,
            "M": M, "n_argmax_M": len(args), "mapping_tie_matters": tie_differs, "support": sup,
            "need": need(params.tau, n), "gate": gate, "m": m, "z": z,
            "answer_seats": [s.key for s in seats], "answer_dists": [Ps[s.key] for s in seats],
            "seat_dists": Ps}


# ---------------------------------------------------------------- 予測（選び・答え・損）
def _spoken(dists: list):
    """0/ℓ の発話：答える席の分布の最頻の名前（同点なら黙る＝None）。席が複数なら最初の席から順に、
    黙らない最初の答え（spec_notes (b)-曖昧 5）。"""
    for P in dists:
        if not P:
            continue
        mx = max(P.values())
        top = [x for x, p in P.items() if p == mx]
        if len(top) == 1:
            return top[0]
    return None


def fallback_dist(scene: Scene, question: Question, kn: Knowledge) -> tuple[dict, str]:
    """42⁵ 1：形と階が分かれば絞った b、分からなければ p̂。"""
    b = kn.shape_b(scene, question)
    if b is not None:
        return dict(b), "b_shape"
    return p_hat_dist(kn.p_hat_counts), "p_hat"


def predict(memory: list, scene: Scene, question: Question, kn: Knowledge, params: Params,
            fixed_maps: Mapping | None = None) -> dict:
    """全候補を評価して選び、問いの答えの分布・発話・損を返す。memory は Definition の並び（変えない）。
    fixed_maps（定義の名前→対応）を渡すと、その定義は照合をやり直さない（近似との比べ用）。"""
    T_x = T_scene(scene)
    fm = fixed_maps or {}
    evals = [eval_definition(d, scene, question, kn, params, T_x, fm.get(d.name)) for d in memory if d.n_FH() > 0]
    L = code_lengths(kn.p_hat_counts)
    y = question.y
    out = {"evals": evals, "y": y}
    # 選び：z（降順）→ 席数 n（降順）→ 新しさ（降順）。残った同点は記録する。
    pool = [e for e in evals if e["z"] != -math.inf]
    if params.gate_order == "gate_then_select":
        pool = [e for e in pool if e["gate"]]
    chosen = None
    tie = []
    if pool:
        keyf = lambda e: (e["z"], e["n"], e["registered_at"])
        best = max(map(keyf, pool))
        tie = sorted([e for e in pool if keyf(e) == best], key=lambda e: e["R"])
        chosen = tie[0]
    out["selected"] = chosen["R"] if chosen else None
    out["definition_tie"] = [e["R"] for e in tie] if len(tie) > 1 else []
    used = chosen if (chosen is not None and chosen["gate"]) else None
    out["used"] = used["R"] if used else None
    if used is not None and used["answer_dists"]:
        dists = used["answer_dists"]
        P = normalize({k: v for k, v in _avg(dists).items()})
        case = "one_seat" if len(dists) == 1 else "mixed_seats"
        spoken = _spoken(dists)
    else:
        P, case = fallback_dist(scene, question, kn)
        case = ("no_gate_pass" if used is None else "no_answer_seat") + ":" + case
        spoken = None
    out.update(answer_dist=P, case=case, spoken=spoken)
    # 損
    bits, escaped = bits_of(P, y, L)
    out["r_top1"], out["r_top1_escaped"] = bits, escaped
    out["r_zero_ell"] = 0.0 if spoken == y else float(L_of(y, L))
    # mixture（注意の代理の損と同じ形。ビットで返す）
    mpool = [e for e in evals if e["z"] != -math.inf and (params.mixture_pool == "q_pos" or e["gate"])]
    pi = softmax({e["R"]: e["z"] for e in mpool}) if mpool else None
    if pi is None:
        Pm, _c = fallback_dist(scene, question, kn)
        out["r_mixture"], out["r_mixture_escaped"] = bits_of(Pm, y, L)
        out["pi"] = None
    else:
        dists = {}
        for e in mpool:
            dists[e["R"]] = _avg(e["answer_dists"]) if e["answer_dists"] else fallback_dist(scene, question, kn)[0]
        p = mixture_prob(pi, dists, y)
        out["pi"] = pi
        out["r_mixture"], out["r_mixture_escaped"] = (-math.log2(p), False) if p > 0 else (float(L_of(y, L)), True)
    out["r"] = {"top1": out["r_top1"], "zero_ell": out["r_zero_ell"], "mixture": out["r_mixture"]}[params.loss]
    return out


def _avg(dists: list) -> dict:
    keys = set().union(*dists)
    return {x: math.fsum(P.get(x, 0.0) for P in dists) / len(dists) for x in keys}


# ---------------------------------------------------------------- Δr
def thinned_memory(memory: list, R: str, seat_key: str) -> list:
    """席 (R, seat_key) だけを一段薄くした記憶（新しい並び。元は変えない）。"""
    out = []
    for d in memory:
        if d.name == R:
            t = thin(d.seat(seat_key))
            if t is None:
                raise ValueError("U は薄くできない")
            d = d.replace_seat(t)
        out.append(d)
    return out


def delta_r(memory: list, scene: Scene, question: Question, kn: Knowledge, params: Params, *,
            scope: str = "all", rematch: str = "full") -> dict:
    """全ての F/H の席（scope="all"）、又は実際に選ばれて答えに使われた定義の席だけ（scope="chosen"、42⁗）について
    Δr_i＝r(M^{-i}) − r(M) を出す。負も 0 に丸めない（42′ 2）。
    rematch="full"（既定）：薄くした記憶で全定義の照合を総当たりでやり直す。"fixed"：予測の時点の各定義の
    対応を固定して点と答えだけ計算し直す（42 ■3 の軽い近似。差の表を作るための比べ用）。

    返り値：{"base": 元の予測, "rows": [{R, seat, state, thinned_to, r_before, r_after, delta, selected_before,
             selected_after, used_after, case_after, spoken_after, ...}]}
    """
    base = predict(memory, scene, question, kn, params)
    fixed = {e["R"]: e["M"] for e in base["evals"]} if rematch == "fixed" else None
    if rematch not in {"full", "fixed"}:
        raise ValueError(rematch)
    rows = []
    for d in memory:
        if scope == "chosen" and d.name != base["used"]:
            continue
        for s in d.seats:
            if s.state == "U":
                continue
            alt = predict(thinned_memory(memory, d.name, s.key), scene, question, kn, params, fixed)
            rows.append({"R": d.name, "seat": s.key, "state": s.state, "thinned_to": thin(s).state,
                         "r_before": base["r"], "r_after": alt["r"], "delta": alt["r"] - base["r"],
                         "delta_top1": alt["r_top1"] - base["r_top1"],
                         "delta_zero_ell": alt["r_zero_ell"] - base["r_zero_ell"],
                         "delta_mixture": alt["r_mixture"] - base["r_mixture"],
                         "selected_before": base["selected"], "selected_after": alt["selected"],
                         "used_before": base["used"], "used_after": alt["used"],
                         "case_before": base["case"], "case_after": alt["case"],
                         "spoken_before": base["spoken"], "spoken_after": alt["spoken"],
                         "definition_tie_after": alt["definition_tie"],
                         "mapping_tie_matters_after": any(e["mapping_tie_matters"] for e in alt["evals"])})
    return {"base": base, "rows": rows}
