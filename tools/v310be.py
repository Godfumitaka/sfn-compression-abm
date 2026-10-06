"""v3.10 B＋E（書き直しの費用で結ぶ統合版、2026-09-29 午後の委任書）：旗 --v310-be。
仕様：control/sfn_v310_be_spec_2026-09-29_v2.md（ChatGPT、承認 アストラ）。基準 v3.10-main（cd8dc52）。tools/v39.py の上に載せる。
★ abm/ は変えない。旗を切れば何もしない。--v39 --v39-decay actr --v39-budget inf --v39-price λ と一緒に使う（α＝1）。
委任書で決まったこと：不在の確認は案 1（確かめられない限り取消は払わない。確かめられなかった件数を記録）・開示は今のまま（正解一件の通知）・
  取消の符号は案 1（D₁(k,m)＝I(m)＋m ceil(log₂ max(k,1))）。★ 本人には不在を確かめる情報が無い（仕様 2 節★）ので、取消の数 m は常に 0。

B（仕様 6 節）：席の記録は、三方式 F/H/U の局所書換ビット r_s（開示と名前・引数が一致なら 0、外れ／棄権なら正解の名前の ℓ）を
  16 本の減衰で持つ（v39 の SeatRec の列を「正解の数」から「書換ビット」に替える。4 本目は採点の回数で、式には使わない）。
  R_s＝Σ w(d) r_s（w は --v39-decay actr の重み。平均の除算・a の補正・Q は無い）。V＝(R_after − R_before)／(C_before − C_after)。
  V＜λ を低い点から一段ずつ（v3.10 の --v39-price の段。V＝λ は残す。λ＝0 でも負は手放す）。解放量 0 以下は比を作らず記録。
  採点は開示を受けた試行の、使った定義の、写しの決まった席のうち、写した位置が開示の引数と同じ席だけ（ほかは全列を更新しない）。
  誕生の初期値は、二材料の再現採点をビットにしたもの（旧い場面 φ^年齢、今の場面 1）。誕生後と分けて持つ。
E（仕様 7 節）：K_a＝A_a＋r(x|M_a)＋λ ΔC_a。x＝登録材料の共通構造（tools/v32.py commons_graph。2 行未満なら今までどおり何もしない）。
  M_a＝候補を仮に適用した記憶（abm.abstraction.m1 を、tools/v39.py の m1 と tools/v3_run.py の包みと同じ前処理で呼ぶ。状態は捨てる）。
  ΔC_a＝C(M_a)−C(M)（v3.9 仕様 6 節の総費用の差。符号表は選ぶ前の p_hat で固定）。A_k＝−log₂(n_k/(N＋α))、A_new＝−log₂(α/(N＋α))。
  r(x|M_a)：M_a の定義（のグラフ）を x に一度写し（今の照合）、
    写った席の答え（F＝固定名、H＝局所の最頻、決まらなければ棄権）が x の名と違えば書換（名前の ℓ）、
    写らなかった x の関係は追加、写らなかった定義の F・H の席は取消の対象（不在が確かめられないので払わない。数だけ記録）。
    書換 ＝ I(書換数) ＋ 書換数 × ceil(log₂ max(写った席数,1)) ＋ Σ ℓ
    追加 ＝ I(追加数) ＋ Σ [ℓ ＋ I(引数数) ＋ Σ 引数（型 1 ＋ ceil(log₂(x の物の数 又は x の関係の数)))]
    取消 ＝ D₁(k, 0)＝I(0)
  選び方は最小の K（argmin）。同点は、同化の回数の多い順・新しい順（新しい定義は回数 0・今の試行の誕生として並べる）。
  新しい定義が構造の条件で作れない（構造上必要な子を残すと 2 行未満）ときは候補から外し、数を記録する。
記録：side の kind＝"v310be"（試行ごと：候補ごとの A／書換／追加／取消の未確認／ΔC／K、採否、開示の有無、ΔC の予測と実測、
  同化の一致 0・履歴更新 0、B の書換ビット）。較正：--v39-dump-cands で、各試行の変換の前に列挙した正の V を書き出す。
使い方：tools/v3_run.py --v39 --v39-decay actr --v39-budget inf --v39-price λ --v310-be ...
"""
from __future__ import annotations

import json
import math
from dataclasses import replace

STATS: dict = {}
CFG: dict = {}
CTX: dict = {}


# ---------------------------------------------------------------- B：書換ビットで採点する
def _ell(p, L) -> float:
    import v39
    return float(v39.L_of(p, L))


def score_answers(seats, ans, received, t):
    """控えた三答え（開示前）を、受け取った開示で採点する。r＝0（名前・引数が一致）又は 正解の名前の ℓ（外れ・棄権）。
    写した位置が開示の引数と違う席・U の席・世代や状態が変わった席は、全列を更新しない。"""
    import v39
    L = CTX["L_score"]
    seats = dict(seats)
    scored = []
    for it in ans["items"]:
        if "ans" not in it:
            continue
        key = (ans["R"], it["slot"])
        rec = seats.get(key)
        if rec is None or rec.gen != it["gen"] or rec.state != it["st"]:
            v39.STATS["score_skipped_changed"] = v39.STATS.get("score_skipped_changed", 0) + 1
            continue
        if tuple(it["pos"]) != tuple(received.arguments):
            STATS["score_other_position"] += 1
            continue
        lp = _ell(received.predicate, L)
        pos_ok = not CFG.get("score_arg_order") or tuple(it["pos"]) == tuple(received.arguments)
        r = {x: (0.0 if pos_ok and it["ans"].get(x) == received.predicate else lp) for x in ("F", "H", "U")}
        inc = (r["F"] if it["st"] == "F" else 0.0, r["H"], r["U"], 1.0)
        seats[key] = v39.rec_add(rec, t, inc)
        scored.append([it["slot"], it["st"], r["F"] if it["st"] == "F" else None, r["H"], r["U"]])
        CTX["R_B_trial"] += r[it["st"]]
    return seats, scored


# ---------------------------------------------------------------- 採点の対応先（旗 --score-role、2026-09-30 の追加・置換の指示 3）
# score_answers は「写した位置（物の組）が開示の引数と同じ席」をすべて採点する。一つの物の組に一階の関係が何本も乗る世界では、
# 一本の開示で同じ物の組の別の席まで採点してしまう（採点先の混線）。旗を立てると、次のようにする。
#   開示前の定義と場面の対応（予測に使った definition_alignment）で、席を引数に持つ親の行が対応した場面の関係の「同じ位置の子」
#   （関係の ID）を、その席の対応先として控える（three_answers の控えに cid を足す）。
#   開示された関係の ID が対応先と一致する席だけを採点する。答えは開示前に控えた三答え（F・H・U）。正解の名前で対応を選び直さない。
#   親が無い・親が場面の関係に対応しない・対応先が一意でない席には、採点の証拠を足さない（理由ごとの件数を STATS に）。物の組だけの判定には戻さない。
def role_target(d, row, alignment, scene):
    """席の対応先：(関係 ID, None) 又は (None, 理由)。親の行ごとに、対応した場面の関係の同じ位置の子を集める。"""
    sid = row.relation.relation_id
    parents = [(p, k) for p in d.constituents for k, a in enumerate(p.relation.arguments) if a == sid]
    if not parents:
        return None, "親が無い"
    s_by_id = {r.relation_id: r for r in scene.relations}
    got = []
    for p, k in parents:
        Q = s_by_id.get(alignment.relation_mapping.get(p.relation.relation_id))
        if Q is None or k >= len(Q.arguments):
            continue
        if Q.arguments[k] not in got:
            got.append(Q.arguments[k])
    if not got:
        return None, "親が対応しない"
    if len(got) > 1:
        return None, "対応先が一意でない"
    return got[0], None


def three_answers_role(inner):
    def three_answers(d, alignment, state, config, scene):
        from abm.filling import _is_higher
        items = inner(d, alignment, state, config, scene)
        rows = {row.slot_index: row for row in d.constituents}
        rel_ids = {row.relation.relation_id for row in d.constituents}
        for it in items:
            row = rows[it["slot"]]
            cid, why = role_target(d, row, alignment, scene)
            it["cid"] = cid
            it["cid_why"] = why
            it["higher"] = _is_higher(row.relation, rel_ids)
        return items
    return three_answers


def score_answers_role(seats, ans, received, t):
    """score_answers と同じ採点（r＝0 又は 正解の名前の ℓ、世代・状態の確かめ）を、対応先の ID が開示の ID と一致する席だけに行う。"""
    import v39
    L = CTX["L_score"]
    seats = dict(seats)
    scored = []
    for it in ans["items"]:
        if "ans" not in it:
            continue
        key = (ans["R"], it["slot"])
        rec = seats.get(key)
        if rec is None or rec.gen != it["gen"] or rec.state != it["st"]:
            v39.STATS["score_skipped_changed"] = v39.STATS.get("score_skipped_changed", 0) + 1
            continue
        old = tuple(it["pos"]) == tuple(received.arguments)    # 記録だけ：今の決め方（物の組）なら採点したか
        order = "高階" if it.get("higher") else "一階"
        if it.get("cid") is None:
            STATS[f"score_role_no_target_{order}_{it.get('cid_why')}"] = STATS.get(f"score_role_no_target_{order}_{it.get('cid_why')}", 0) + 1
            STATS["score_role_old_would_score_no_target"] += old
            continue
        if it["cid"] != received.relation_id:
            STATS["score_role_other_target"] += 1
            STATS["score_role_old_would_score_other"] += old
            continue
        STATS["score_role_scored"] += 1
        STATS["score_role_scored_pos_differs"] += not old
        lp = _ell(received.predicate, L)
        pos_ok = not CFG.get("score_arg_order") or old
        r = {x: (0.0 if pos_ok and it["ans"].get(x) == received.predicate else lp) for x in ("F", "H", "U")}
        inc = (r["F"] if it["st"] == "F" else 0.0, r["H"], r["U"], 1.0)
        seats[key] = v39.rec_add(rec, t, inc)
        scored.append([it["slot"], it["st"], r["F"] if it["st"] == "F" else None, r["H"], r["U"]])
        CTX["R_B_trial"] += r[it["st"]]
    return seats, scored


def init_rec(d, row, state, base, target, trial, base_age, config):
    """誕生の初期値：二材料の再現採点をビットに（F の答えは固定名なので 0。H・U は外れなら ℓ）。旧い場面は φ^年齢。"""
    import v39
    if v39.CFG["init"] == "zero":
        return v39.SeatRec(0, "F", trial, trial, v39.ZERO4, v39.ZERO4)
    L = v39.code_lengths(state.p_hat)
    p = row.relation.predicate
    lp = _ell(p, L)
    h, h_why = v39.h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)
    u_cur, u_why = v39.u_answer(d, row, target, state.p_hat, config.higher_order_predicates)
    u_old, u_why_old = v39.u_answer(d, row, base, state.p_hat, config.higher_order_predicates)
    r_old = (0.0, 0.0 if h == p else lp, 0.0 if u_old == p else lp, 1.0)
    r_cur = (0.0, 0.0 if h == p else lp, 0.0 if u_cur == p else lp, 1.0)
    ordered = None
    if CFG.get("score_arg_order"):
        import argorder
        (obs_old, pos_old), (obs_cur, pos_cur) = argorder.birth_observations(row, base, target)

        def costs(observed, position, ua):
            length = _ell(observed.predicate, L)
            return tuple(0.0 if argorder.correct(a, position, observed) else length for a in (p, h, ua)) + (1.0,)

        r_old = costs(obs_old, pos_old, u_old)
        r_cur = costs(obs_cur, pos_cur, u_cur)
        ordered = {"position_old": list(pos_old) if pos_old is not None else None,
                   "position_current": list(pos_cur) if pos_cur is not None else None,
                   "observed_old": obs_old.to_dict(), "observed_current": obs_cur.to_dict(),
                   "r_old": list(r_old), "r_current": list(r_cur)}
    w = tuple(f ** max(base_age, 0) for f in v39.CFG["decay"])
    init = tuple(tuple(k * so + sc for k in w) for so, sc in zip(r_old, r_cur))
    v39.CTX["births_rec"].append({"slot": row.slot_index, "rF": 0.0, "rH": r_cur[1], "rU旧": r_old[2], "rU今": r_cur[2],
                                  "H答え": h, "U答え": [u_old, u_cur], "理由": [h_why, u_why_old, u_why],
                                  "履歴": v39.hist_counts(state.slot_history.get((d.name, row.slot_index)))})
    if ordered is not None:
        v39.CTX["births_rec"][-1].update(rF=r_cur[0], ordered_arguments=ordered)
    return v39.SeatRec(0, "F", trial, trial, init, v39.ZERO4)


def candidates(state, d, t, L, n_defs):
    """定義 d の席ごとの、可能な次の一段と V＝(R_after − R_before)／(C_before − C_after)。解放量 0 以下は比を作らない。"""
    import v39
    out = []
    sts = {row.slot_index: v39.seat_state(d, row, state.slot_history) for row in d.constituents}
    n_nonU = sum(1 for s in sts.values() if s != "U")
    for row in d.constituents:
        st = sts[row.slot_index]
        if st == "U":
            continue
        rec = state.v39_seats[(d.name, row.slot_index)]
        RF, RH, RU, n = v39.rec_means(rec, t)
        h = state.slot_history.get((d.name, row.slot_index))
        if st == "F":
            dc = v39.fixed_spec_bits(row.relation.predicate, h, L)
            kind, num = "FH", RH - RF
        else:
            dc = v39.hcost(h, L)
            if n_nonU == 1:   # ★ 最後の変換：定義が退役する。構造を含む実際の総解放量（仕様 6 節の近似として記録）
                dc = v39.definition_bits(d, state.slot_history, L) + v39.I(n_defs) - v39.I(n_defs - 1)
                STATS["retire_candidate_evals"] += 1
            kind, num = "HU", RU - RH
        if dc <= 0:
            STATS["zero_release"] += 1
            CTX.setdefault("zero_release", []).append([d.name, row.slot_index, kind, dc])
            continue
        out.append((num / dc, kind, d.name, row.slot_index, dc, (RF, RH, RU, n)))
    return out


# ---------------------------------------------------------------- 取消の符号 D₁（仕様 3 節、案 1）
def gamma(n: int) -> str:
    """I(n) の符号語（n＋1 の Elias γ）：長さ 2 floor(log₂(n＋1))＋1。"""
    b = bin(n + 1)[2:]
    return "0" * (len(b) - 1) + b


def ungamma(bits: str, i: int = 0):
    z = 0
    while bits[i + z] == "0":
        z += 1
    return int(bits[i + z:i + 2 * z + 1], 2) - 1, i + 2 * z + 1


def d1_bits(k: int, m: int) -> int:
    """D₁(k,m)＝I(m)＋m ceil(log₂ max(k,1))。k＝0 では m＝0 だけ。"""
    import v39
    if k == 0 and m != 0:
        raise ValueError("k＝0 では m＝0 だけ")
    if not 0 <= m <= max(k, 0):
        raise ValueError((k, m))
    return v39.I(m) + m * v39.clog2(max(k, 1))


def d1_encode(k: int, seats) -> str:
    """取り消す席（固定順の 0〜k−1）を、個数と昇順の席番号で書く。"""
    import v39
    seats = sorted(seats)
    b = v39.clog2(max(k, 1))
    if k == 0 and seats:
        raise ValueError("k＝0 では m＝0 だけ")
    return gamma(len(seats)) + "".join(format(x, f"0{b}b") if b else "" for x in seats)


def d1_decode(k: int, bits: str):
    import v39
    m, i = ungamma(bits)
    b = v39.clog2(max(k, 1))
    return [int(bits[i + j * b:i + (j + 1) * b], 2) if b else 0 for j in range(m)]


# ---------------------------------------------------------------- E：候補を仮に適用する
def _restrict(alignment, keep):
    return replace(alignment, relation_mapping={k: v for k, v in alignment.relation_mapping.items() if k in keep})


def hypo_m1(state, base, target, alignment, trial, name, kw):
    """候補を仮に適用した記憶 M_a。実際の鎖（tools/v39.py m1 → tools/v3_run.py wrapped → abm.abstraction.m1）と同じ前処理で、
    abm.abstraction.m1 を直接呼ぶ（side・STATS・CTX には何も書かない）。返り値：(状態, 登録した名前) 又は None。"""
    import sys
    import abm.abstraction as ab
    import v39
    if name is None:
        pairs = v39._pool_pairs(base, target, alignment)
        S, _ = v39._drop_childless([l for l, _ in pairs], {r.relation_id for r in base.relations})
        if len(S) < 2:
            return None
        alignment = _restrict(alignment, {r.relation_id for r in S})
        # tools/v3_run.py の --nohash：ハッシュ名が既にあれば「名前_t試行」で新しく生む
        base_by_id = {r.relation_id: r for r in base.relations}
        target_by_id = {r.relation_id: r for r in target.relations}
        raw = [(base_by_id[l], target_by_id[r]) for l, r in sorted(alignment.relation_mapping.items())
               if l in base_by_id and r in target_by_id]
        sids = ab._structural_relation_ids(base)
        pp = [p for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]
        hn = ab._definition_name(pp) if len(pp) >= 2 else None
        use = f"{hn}_t{trial}" if (CFG["nohash"] and hn is not None and hn in state.definitions) else None
    else:
        use = name
    pre_hist = state.slot_history
    made = []
    orig_dg = ab._definition_graph

    def dg(definition, *, mode="all"):
        g = v39.v39_graph(definition, pre_hist)
        made.append(g)
        return g

    if "v31" in sys.modules:
        sys.modules["v31"].CFG["target"] = target
    ab._definition_graph = dg
    try:
        out, reg = ab.m1(state, base, target, alignment, trial, name=use, **kw)
    finally:
        ab._definition_graph = orig_dg
        for g in made:
            v39.unregister(g)
    if reg is None:
        return None
    if v39.CFG.get("u_position"):
        import uposition
        out = uposition.decorate(out, state, base, reg)
    return out, reg["R"]


def _arg_bits(rel, x_rel_ids, e, m):
    import v39
    return v39.I(len(rel.arguments)) + sum(1 + (v39.clog2(m) if a in x_rel_ids else v39.clog2(e)) for a in rel.arguments)


def rewrite(state_a, R, x, L, config, scene_rel_ids):
    """r(x|M_a)：M_a の定義 R を x に一度写し、書換・追加・取消を数える。返り値：(ビット, 内訳)。"""
    import abm.sme as sme
    import v39
    d = state_a.definitions[R]
    hist = state_a.slot_history
    g = v39.v39_graph(d, hist)
    try:
        alignment = sme.map_graphs(g, x).alignment
        rm = alignment.relation_mapping
    finally:
        v39.unregister(g)
    x_by_id = {r.relation_id: r for r in x.relations}
    mapped_x = {}
    n_map = 0
    ren = []
    unmapped_seats = 0
    for row in d.constituents:
        st = v39.seat_state(d, row, hist)
        if st == "U":
            continue
        cid = rm.get(row.relation.relation_id)
        if cid in x_by_id:
            n_map += 1
            mapped_x[cid] = row.slot_index
            want = x_by_id[cid].predicate
            if st == "F":
                got = row.relation.predicate
            else:
                got, _ = v39.h_answer(d, row, hist, state_a.p_hat, config.local_lambda, config.higher_order_predicates)
            pos_ok = True
            if CFG.get("score_arg_order"):
                from abm.filling import _mapped_arguments
                pos = _mapped_arguments(row.relation, alignment.entity_mapping, rm)
                pos_ok = pos is not None and tuple(pos) == tuple(x_by_id[cid].arguments)
            if got != want or not pos_ok:
                ren.append(want)
        else:
            unmapped_seats += 1
    adds = [r for r in x.relations if r.relation_id not in mapped_x]
    e = len({a for r in x.relations for a in r.arguments if a not in scene_rel_ids})
    m = len(x.relations)
    x_rel_ids = set(x_by_id)
    b_ren = v39.I(len(ren)) + len(ren) * v39.clog2(max(n_map, 1)) + sum(_ell(p, L) for p in ren)
    b_add = v39.I(len(adds)) + sum(_ell(r.predicate, L) + _arg_bits(r, x_rel_ids, e, m) for r in adds)
    n_FH = sum(1 for row in d.constituents if v39.seat_state(d, row, hist) != "U")
    b_can = d1_bits(n_FH, 0)              # ★ D₁(k, 0)：不在が確かめられないので取消は 0 本（案 1）。k＝固定順の F・H の席数
    parts = {"書換": b_ren, "追加": b_add, "取消": b_can, "書換数": len(ren), "追加数": len(adds),
             "写った席": n_map, "一致": n_map - len(ren), "取消の未確認": unmapped_seats}
    return b_ren + b_add + b_can, parts


def choose_and_register(state, base, target, alignment, trial, kw, inner_m1):
    """E：候補ごとに K＝A＋r＋λΔC を計り、最小のものを実際の鎖（inner_m1）で登録する。"""
    import v32
    import v39
    output = v39.CTX["output"]
    x = v32.commons_graph(target, output)
    rec = {"kind": "v310be", "trial": trial, "disclosed": CTX.get("disclosed")}
    if x is None:
        STATS["commons_lt2"] += 1
        rec["x"] = None
        CTX["side"] = rec
        return inner_m1(state, base, target, alignment, trial, **kw)
    config = v39.CTX["config"]
    lam = CFG["lam"]
    alpha = CFG["alpha"]
    L = v39.code_lengths(state.p_hat)
    scene_rel_ids = {r.relation_id for r in target.relations}
    n_defs = len(state.definitions)
    N = sum(d.assimilation_count for d in state.definitions.values())
    cands = []
    for d in sorted(state.definitions.values(), key=lambda d: (-d.assimilation_count, -d.registered_at, d.name)):
        h = hypo_m1(state, base, target, alignment, trial, d.name, kw)
        if h is None:
            STATS["assim_impossible"] += 1
            continue
        sa, R = h
        dC = (v39.definition_bits(sa.definitions[R], sa.slot_history, L) - v39.definition_bits(d, state.slot_history, L))
        r, parts = rewrite(sa, R, x, L, config, scene_rel_ids)
        A = -math.log2(d.assimilation_count / (N + alpha))
        cands.append({"R": d.name, "A": A, "r": r, "dC": dC, "K": A + r + lam * dC, "parts": parts,
                      "key": (-d.assimilation_count, -d.registered_at, d.name)})
    h = hypo_m1(state, base, target, alignment, trial, None, kw)
    if h is None:
        STATS["new_excluded_structure"] += 1
        rec["new_excluded"] = "構造の条件（構造上必要な子を残すと 2 行未満）"
    else:
        sa, R = h
        dC = v39.definition_bits(sa.definitions[R], sa.slot_history, L) + v39.I(n_defs + 1) - v39.I(n_defs)
        r, parts = rewrite(sa, R, x, L, config, scene_rel_ids)
        A = -math.log2(alpha / (N + alpha))
        cands.append({"R": None, "A": A, "r": r, "dC": dC, "K": A + r + lam * dC, "parts": parts, "key": (0, -trial, "")})
    if not cands:
        STATS["no_candidate"] += 1
        CTX["side"] = rec
        return state, None
    lo = min(c["K"] for c in cands)
    tied = sorted((c for c in cands if c["K"] == lo), key=lambda c: c["key"])
    pick = tied[0]
    STATS["ties"] += len(tied) > 1
    STATS["chose_new" if pick["R"] is None else "chose_existing"] += 1
    C0 = v39.total_bits(state, L)
    kw2 = dict(kw, name=pick["R"])
    out, reg = inner_m1(state, base, target, alignment, trial, **kw2)
    C1 = v39.total_bits(v39.ensure(out), L)
    if reg is not None and abs((C1 - C0) - pick["dC"]) > 1e-9:
        STATS["dC_mismatch"] += 1
    if pick["R"] is not None and reg is not None:
        R = reg["R"]
        STATS["assim_match0"] += pick["parts"]["一致"] == 0
        inc = sum(sum(v39.hist_counts(out.slot_history.get(k)).values()) for k in out.slot_history if k[0] == R) \
            - sum(sum(v39.hist_counts(state.slot_history.get(k)).values()) for k in state.slot_history if k[0] == R)
        STATS["assim_hist0"] += inc == 0
        rec["hist_inc"] = inc
    rec.update({"x_rows": len(x.relations), "N": N, "lam": lam, "chosen": pick["R"], "reg": reg["R"] if reg else None,
                "K": pick["K"], "r": pick["r"], "dC_pred": pick["dC"], "dC_real": (C1 - C0) if reg is not None else None,
                "C_after_E": C1, "ties": len(tied),
                "cands": [[c["R"], round(c["A"], 6), round(c["r"], 6), c["dC"], round(c["K"], 6),
                           {k: v for k, v in c["parts"].items()}] for c in sorted(cands, key=lambda c: c["K"])][:12]})
    CTX["side"] = rec
    CTX["R_E_trial"] = pick["r"]
    return out, reg


# ---------------------------------------------------------------- 入れる所
def install(fo, *, seed: int, nohash: bool, score_role: bool = False) -> None:
    import abm.loop as loop
    import v39
    if v39.CFG.get("mean_weights") is None:
        raise ValueError("--v310-be は --v39-decay actr と一緒に使う（仕様 6 節の w）")
    if v39.CFG.get("budget") is not None or v39.CFG.get("price") is None:
        raise ValueError("--v310-be は予算無限と --v39-price λ（λ＝0 を含む）で使う")
    STATS.clear()
    CFG.clear()
    CTX.clear()
    CFG.update(seed=seed, alpha=1.0, lam=float(v39.CFG["price"]), nohash=bool(nohash))
    STATS.update(commons_lt2=0, chose_new=0, chose_existing=0, ties=0, new_excluded_structure=0, assim_impossible=0,
                 no_candidate=0, dC_mismatch=0, assim_match0=0, assim_hist0=0, zero_release=0, retire_candidate_evals=0,
                 score_other_position=0, cfg={"alpha": 1.0, "lam": CFG["lam"], "cancel_code": "D1", "absence": "案1"})
    CTX.update(R_B_trial=0.0, R_E_trial=0.0, disclosed=None, L_score={})

    # B：採点・初期値・V を書換ビットの形に（tools/v39.py の同じ名前の関数を置き換える。呼ぶ側はモジュールの名前で引く）
    v39.score_answers = score_answers
    if score_role:
        # ★ 旗 --score-role：採点の対応先を、親の行の対応の同じ位置の子にする（上の role_target）
        STATS.update(score_role_scored=0, score_role_scored_pos_differs=0, score_role_other_target=0,
                     score_role_old_would_score_other=0, score_role_old_would_score_no_target=0)
        STATS["cfg"]["score_role"] = True
        v39.three_answers = three_answers_role(v39.three_answers)
        v39.score_answers = score_answers_role
    v39._init_rec = init_rec
    v39._candidates = candidates

    # 会計：採点の符号表（その試行の p_hat）と、開示の有無を控える。伏せ辺は読まない（開示が無ければ v39 が採点しない）
    inner_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        CTX["L_score"] = v39.code_lengths(state.p_hat)
        CTX["disclosed"] = bool(coin.f_fired)
        CTX["R_B_trial"] = 0.0
        return inner_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting

    # 同定：NSIM は使わない（選ぶのは m1 の中の E）
    def identify(state, scene, threshold, self_score_cache=None, *, identification_graph="all", self_score_cache_mode="legacy"):
        return None

    loop._identify_definition = identify

    # m1：E で選んで、実際の鎖で登録する
    inner_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        state = v39.ensure(state)
        CTX["R_E_trial"] = 0.0
        kw = {k: v for k, v in kw.items() if k != "name"}
        out, reg = choose_and_register(state, base, target, alignment, trial, kw, inner_m1)
        return out, reg

    loop.m1 = m1

    # 変換の段：較正用に「変換の前」の正の V を書き出す（v39 の apply が last_cands を書く）。試行ごとの記録を side に
    inner_rc = v39.run_conversions

    def run_conversions(state, trial):
        pre = None
        if v39.CFG.get("dump_cands"):
            L = v39.code_lengths(state.p_hat)
            pre = [c[0] for d in state.definitions.values() for c in candidates(state, d, trial, L, len(state.definitions))]
        res = inner_rc(state, trial)
        for e in res[1]:
            # ★ 新方式の値は別の名で残す（仕様 ⑫）：v39 の「S（正解の数）」の欄に入っているのは、ここでは書換ビット R
            if e.get("v39") in ("FH", "HU") and "S" in e:
                e["R_bits"] = e.pop("S")
                e["R_bits_init_post"] = e.pop("S_init_post", None)
        if pre is not None:
            v39.CTX["last_cands"] = pre
        side = CTX.pop("side", None) or {"kind": "v310be", "trial": trial, "x": "no_m1"}
        side.update(R_B=CTX.get("R_B_trial", 0.0), R_E=CTX.get("R_E_trial", 0.0), C_end=res[3],
                    zero_release=CTX.pop("zero_release", []))
        fo.write(json.dumps(side, ensure_ascii=False) + "\n")
        CTX["R_E_trial"] = 0.0
        CTX["R_B_trial"] = 0.0
        return res

    v39.run_conversions = run_conversions
