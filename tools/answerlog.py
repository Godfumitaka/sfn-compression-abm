"""答えごとの記録（2026-09-30 朝の委任書「U を黙らせる比べ・答えごとの記録・世界 v4 の外れの中身」の 2・3）：旗 --dump-answers。
★ 記録だけ。模型は変えない（台帳・side は旗の有無で一字一句同じ）。--v39（v3.9 以降の予測）と一緒に使う。
実際に答えた（予測を出した）試行ごとに、side/<セル>/seed<種>.answers.csv へ一行ずつ書く。エージェントの側の量は、答えを出す前・開示の前の状態
（予測に渡された状態と、そのときの照合）で測る。当たり外れと開示の有無だけは、同じ試行の会計のときに足す。

列（エージェントの側）
  trial 試行・seed 種・R 答えた定義の名前・R_born 生まれた試行・def_id 名前＠生まれた試行
  source 答えの出どころ（F_proj＝F の投影／F_fill・H_fill・U_fill＝その状態の席の穴埋め）・slot 答えた席・pred 答えた述語・hit 当たり（1／0）・disclosed 開示を受けたか
  seat_state その席の状態（F・H・U）
  h_total・h_top・h_top_ratio・h_kinds・h_entropy_bits：H の席の履歴の回数の和・一番多い名の回数・その割合・名の種類の数（回数＞0）・エントロピー（ビット）。H でなければ空
  def_F・def_H・def_U 定義の席の数・def_registrations 定義の登録の回数（NamedDefinition.assimilation_count。誕生で 1、同化ごとに ＋1）・age 生まれてからの試行数
  support・m_live・support_ratio 発話の門での支持（写った F・H の席の数）・F＋H の席の数・その割合
  B_RF・B_RH・B_RU・B_n その席の B の点数（tools/v39.py rec_means：B＋E では書換ビットの重み付き平均。B_n は採点の重みの和）
  pred_freq 答えた述語の全体の頻度（p_hat の回数 ÷ 合計）
  cand_n 候補の定義の数（F・H の席があって照合したもの）・cand_other_max_ratio 選ばれなかった候補の支持の割合の最大・cand_other_ratios 同じく上位 5 つ
  cand_answers 候補ごとの JSON。R・R_born・def_id・selected・support・m_live・support_ratio・gate_pass・pred・arguments・source・seat_state・slot・abstain_reason・hit。
    門の下も含め、実際の選択時の対応と開示前の記憶で、門だけを適用せずに既存の投影・穴埋めを計算する。hit は計算後の会計で足す。
  cand_other_correct 選ばれた定義以外に正しい答えを出せた候補があったか（門の下を含む）。cand_other_correct_passed 同じく門を通った候補にあったか。
  cand_tie_disagree_pairs 選ばれた定義と支持の割合が同じで、どちらも答えを出し、述語または引数が違う候補対の数。cand_tie_disagree その対が一つ以上あったか。
列（研究者の側）
  born_motif 定義が生まれた試行の場面の型・base_motif 生まれたときの土台の場面の型・scene_motif 場面の型・same_motif 生まれた型の場面か（1／0）
  assim_motifs 定義が取り込んだ（同化した）場面の型と回数（例 M1:30;M2:2）・assim_total 同化の回数・assim_cross 型またぎの同化の回数（場面の型 ≠ born_motif）
  seat_pred_born その席の生まれたときの述語・role その席の役割（親の行の生まれたときの述語＃親の中の位置。親が二つ以上なら | で区切る。親が無ければ空）
  role_in_scene_motif その役割（親の述語と位置）が場面の型の骨組みにあるか・role_same_pred その役割に、場面の型でも同じ述語が入るか（構造の共有。親が無ければ空）
  世界 v4（型の変種、tools/worldvariant.py）のときだけ：scene_variant 場面の変種・held_out_switch 伏せ辺が切り替わる関係ならその部分木・
  born_variant 生まれた試行の場面の変種・base_variant 生まれたときの土台の場面の変種・def_switch_seats 定義に入っている切り替わる関係の席の数（生まれたときの土台の
  切り替わる関係の ID の行。0〜2）・other_switch_visible もう一方の切り替わる関係（伏せ辺でない方）が場面で見えていたか（伏せ辺が切り替わる関係のときだけ）
"""
from __future__ import annotations

import csv
import copy
import json
import math
import sys
from collections import Counter
from dataclasses import replace
from itertools import combinations

COLS = ["trial", "seed", "R", "R_born", "def_id", "source", "slot", "pred", "hit", "disclosed", "seat_state",
        "h_total", "h_top", "h_top_ratio", "h_kinds", "h_entropy_bits", "def_F", "def_H", "def_U", "def_registrations", "age",
        "support", "m_live", "support_ratio", "B_RF", "B_RH", "B_RU", "B_n", "pred_freq",
        "cand_n", "cand_other_max_ratio", "cand_other_ratios", "cand_answers", "cand_other_correct", "cand_other_correct_passed",
        "cand_tie_disagree", "cand_tie_disagree_pairs",
        "born_motif", "base_motif", "scene_motif", "same_motif", "assim_motifs", "assim_total", "assim_cross",
        "seat_pred_born", "role", "role_in_scene_motif", "role_same_pred"]
WCOLS = ["scene_variant", "held_out_switch", "born_variant", "base_variant", "def_switch_seats", "other_switch_visible"]
ST: dict = {}


def _describe_prediction(d, prediction, slot_history):
    """答えと出どころだけを返す。正解には触れない。"""
    import v39
    from abm.domains import EdgePrediction
    if not isinstance(prediction, EdgePrediction):
        return {"pred": None, "arguments": None, "source": None, "seat_state": None,
                "slot": None, "abstain_reason": prediction.reason}
    edge = prediction.edge
    rid = edge.relation_id
    slot = None
    if rid.startswith("sme_projection__"):
        base_id = rid[len("sme_projection__"):]
        slot = next((r.slot_index for r in d.constituents if r.relation.relation_id == base_id), None)
    elif rid.startswith("filling__"):
        slot = int(rid.rsplit("__", 2)[1])
    row = next((r for r in d.constituents if r.slot_index == slot), None)
    st = v39.seat_state(d, row, slot_history) if row is not None else None
    source = "F_proj" if rid.startswith("sme_projection__") else (f"{st}_fill" if rid.startswith("filling__") else "other")
    return {"pred": edge.predicate, "arguments": list(edge.arguments), "source": source,
            "seat_state": st, "slot": slot, "abstain_reason": None}


def _candidate_answer(d, graph, alignment, state, config, scene, rng):
    """v39.predict と同じ投影優先の答え。門だけ外す。照合し直さず、正解・更新・採点を呼ばない。"""
    import v39
    from abm.domains import Abstain, EdgePrediction
    from abm.sme import project
    # fill_v39 の記録用変数も元に戻す。乱数は各候補に独立の写しを渡す。
    saved_stats, saved_ctx = dict(v39.STATS), dict(v39.CTX)
    try:
        f_ids = {r.relation.relation_id for r in d.constituents if r.alive}
        alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in f_ids))
        prediction = project(alignment, graph, scene, prototype_prior_weight=0.0)
        filling = v39.fill_v39(d, scene, alignment.entity_mapping, alignment.relation_mapping,
                               state.slot_history, state.p_hat, config.fill_selection, copy.deepcopy(rng),
                               higher_order_predicates=config.higher_order_predicates, local_lambda=config.local_lambda)
        if filling.ambiguous and not isinstance(prediction, EdgePrediction):
            prediction = Abstain(reason="ambiguous_projection")
        elif isinstance(prediction, Abstain) and filling.relations:
            prediction = EdgePrediction(filling.relations[0])
        elif isinstance(prediction, Abstain):
            prediction = Abstain(reason="no_projectable_relation")
        return _describe_prediction(d, prediction, state.slot_history)
    finally:
        v39.STATS.clear()
        v39.STATS.update(saved_stats)
        v39.CTX.clear()
        v39.CTX.update(saved_ctx)


def _score_candidates(cands, held):
    """控えた答えの採点だけ。候補の答えを作り直さない。"""
    scored = [{**c, "hit": int(c["pred"] is not None and c["pred"] == held.predicate
                              and tuple(c["arguments"]) == tuple(held.arguments))} for c in cands]
    others = [c for c in scored if not c["selected"]]
    selected = next(c for c in scored if c["selected"])
    tied = [c for c in scored if c["support_ratio"] == selected["support_ratio"] and c["pred"] is not None]
    pairs = sum((a["pred"], a["arguments"]) != (b["pred"], b["arguments"]) for a, b in combinations(tied, 2))
    return {"cand_answers": json.dumps(scored, ensure_ascii=False, separators=(",", ":")),
            "cand_other_correct": int(any(c["hit"] for c in others)),
            "cand_other_correct_passed": int(any(c["hit"] and c["gate_pass"] for c in others)),
            "cand_tie_disagree": int(pairs > 0), "cand_tie_disagree_pairs": pairs}


def _role_triples(seed):
    import abm.world as w
    out = {}
    for m in seed.data["motif_structure"]:
        sk = w._expand_motif(seed.data, m)
        pred = {path: p for _, (_lvl, path, p, _ch) in sk}
        tri = set()
        for _, (_lvl, path, p, ch) in sk:
            for k, c in enumerate(ch or ()):
                if c in pred:
                    tri.add((p, k, pred[c]))
        out[m] = tri
    return out


def install(path, *, seed: int, seed_file: str) -> None:
    """tools/v3_run.py の worker で、ほかの差し替え（v39・v310be・世界 v4）のあと、世界を作る前に呼ぶ。"""
    import abm.loop as loop
    import abm.world as w
    import v39
    from abm.domains import EdgePrediction
    from abm.seed import load_seed
    sd = load_seed(seed_file)
    ST.clear()
    ST.update(f=open(path, "w", encoding="utf-8", newline=""), seed=seed, motif={}, run_seed=None, birth={}, assim={},
              pending=None, cands=None, tri=_role_triples(sd), sd=sd, rows=0)
    wv = sys.modules.get("worldvariant")
    ST["cols"] = COLS + (WCOLS if wv is not None else [])
    ST["w"] = csv.writer(ST["f"])
    ST["w"].writerow(ST["cols"])

    real_gen = w.generate_trial

    def generate_trial(run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
        tr = real_gen(run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)
        ST["run_seed"] = run_seed
        ST["motif"][trial_index] = tr.motif
        return tr

    w.generate_trial = generate_trial

    # 候補の定義の支持（選び方の照合をそのまま控える。計算し直さない）
    real_select = v39.select_definition

    def select_definition(state, scene, config):
        got = {}
        real_map = v39.map_v39

        def map_v39(d, slot_history, sc):
            g, al = real_map(d, slot_history, sc)
            got[d.name] = (d, g, al)
            return g, al

        v39.map_v39 = map_v39
        try:
            res = real_select(state, scene, config)
        finally:
            v39.map_v39 = real_map
        cands = []
        for name, (d, g, al) in got.items():
            if al is None:
                continue
            n = v39.n_FH(d, state.slot_history)
            sup = sum(1 for row in d.constituents if v39.seat_state(d, row, state.slot_history) != "U"
                      and row.relation.relation_id in al.relation_mapping)
            cands.append((d, g, al, sup, n))
        ST["cands"] = cands
        return res

    v39.select_definition = select_definition

    # 誕生と同化（実際の鎖の一番外）
    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        out, reg = real_m1(state, base, target, alignment, trial, **kw)
        if reg is not None:
            d = out.definitions[reg["R"]]
            key = (d.name, d.registered_at)
            if not reg["was_extension"]:
                rid = {row.relation.relation_id: row.slot_index for row in d.constituents}
                ST["birth"][key] = {
                    "motif": ST["motif"].get(trial), "base_t": kw.get("base_written_at"),
                    "base_motif": ST["motif"].get(kw.get("base_written_at")),
                    "pred": {row.slot_index: row.relation.predicate for row in d.constituents},
                    "rid": {row.slot_index: row.relation.relation_id for row in d.constituents},
                    "parents": {row.slot_index: [(rid[p.relation.relation_id], k) for p in d.constituents
                                                 for k, a in enumerate(p.relation.arguments) if a == row.relation.relation_id]
                                for row in d.constituents}}
                ST["assim"][key] = Counter()
            else:
                ST["assim"].setdefault(key, Counter())[ST["motif"].get(trial)] += 1
        return out, reg

    loop.m1 = m1

    real_predict = loop.predict

    def predict(agent_input, state, config, rng):
        ST["cands"] = None
        rng_before = copy.deepcopy(rng)
        output, pending = real_predict(agent_input, state, config, rng)
        ST["pending"] = None
        if isinstance(output.prediction, EdgePrediction) and output.trace.get("R_used"):
            import abm.agent_runtime as ar
            scene = agent_input.target_graph_partial
            cands = []
            for d, g, al, sup, n in ST["cands"] or []:
                answer = _candidate_answer(d, g, al, state, config, scene, rng_before)
                selected = d.name == output.trace["R_used"]
                if selected and answer != _describe_prediction(d, output.prediction, state.slot_history):
                    raise RuntimeError("記録用の候補の答えが実際の答えと一致しない。停止")
                cands.append({"R": d.name, "R_born": d.registered_at, "def_id": f"{d.name}@{d.registered_at}",
                              "selected": int(selected), "support": sup, "m_live": n,
                              "support_ratio": sup / n if n else 0.0, "gate_pass": int(sup >= ar._need(config.tau_acc, n)),
                              **answer})
            ST["pending"] = (state, output, getattr(pending, "prediction_path", None), scene, cands)
        return output, pending

    loop.predict = predict

    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        p = ST.pop("pending", None)
        ST["pending"] = None
        if p is not None and p[1] is output:
            _write(p, coin, revealed_edge)
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting


def _variant(t):
    import worldvariant as V
    return "A" if V.variant_rng(ST["run_seed"], t).random() < V.CFG["p_a"] else "B"


def _switch_ids(t):
    import abm.world as w
    m = ST["motif"].get(t)
    if m is None:
        return set()
    n = len(ST["sd"].data["motif_structure"][m]["subtrees"])
    return {w.opaque_id(ST["run_seed"], t, f"relation:tree:{i}.0.0") for i in range(n)}


def _write(p, coin, held):
    import v39
    state, output, path, scene, cands = p
    t = coin.t
    tr = output.trace
    R = tr["R_used"]
    d = state.definitions[R]
    edge = output.prediction.edge
    rid = edge.relation_id
    slot = None
    if rid.startswith("sme_projection__"):
        base_id = rid[len("sme_projection__"):]
        slot = next((row.slot_index for row in d.constituents if row.relation.relation_id == base_id), None)
    elif rid.startswith("filling__"):
        slot = int(rid.rsplit("__", 2)[1])
    row = next((r for r in d.constituents if r.slot_index == slot), None)
    st = v39.seat_state(d, row, state.slot_history) if row is not None else ""
    source = "F_proj" if rid.startswith("sme_projection__") else (f"{st}_fill" if rid.startswith("filling__") else "other")
    hit = int(edge.predicate == held.predicate and tuple(edge.arguments) == tuple(held.arguments))
    r = {"trial": t, "seed": ST["seed"], "R": R, "R_born": d.registered_at, "def_id": f"{R}@{d.registered_at}", "source": source,
         "slot": slot, "pred": edge.predicate, "hit": hit, "disclosed": int(bool(coin.f_fired)), "seat_state": st}
    if st == "H":
        h = {k: v for k, v in v39.hist_counts(state.slot_history.get((R, slot))).items() if v > 0}
        tot = sum(h.values())
        top = max(h.values()) if h else 0
        r.update(h_total=tot, h_top=top, h_top_ratio=(top / tot if tot else ""), h_kinds=len(h),
                 h_entropy_bits=(abs(-sum(v / tot * math.log2(v / tot) for v in h.values())) if tot else ""))
    sts = Counter(v39.seat_state(d, x, state.slot_history) for x in d.constituents)
    n = tr.get("m_live") or 0
    r.update(def_F=sts["F"], def_H=sts["H"], def_U=sts["U"], def_registrations=d.assimilation_count, age=t - d.registered_at,
             support=tr.get("support_at_adoption"), m_live=n, support_ratio=(tr.get("support_at_adoption", 0) / n if n else ""))
    rec = getattr(state, "v39_seats", {}).get((R, slot))
    if rec is not None:
        rf, rh, ru, bn = v39.rec_means(rec, t)
        r.update(B_RF=rf, B_RH=rh, B_RU=ru, B_n=bn)
    ph = state.p_hat
    r["pred_freq"] = (ph.counts.get(edge.predicate, 0) / ph.total) if ph.total else ""
    if cands is not None:
        others = sorted((c["support_ratio"] for c in cands if not c["selected"]), reverse=True)
        r.update(cand_n=len(cands), cand_other_max_ratio=(others[0] if others else ""), cand_other_ratios=";".join(f"{x:.4f}" for x in others[:5]))
        r.update(_score_candidates(cands, held))
    b = ST["birth"].get((R, d.registered_at))
    sm = ST["motif"].get(t)
    r["scene_motif"] = sm
    if b is not None:
        a = ST["assim"].get((R, d.registered_at), Counter())
        r.update(born_motif=b["motif"], base_motif=b["base_motif"], same_motif=int(b["motif"] == sm),
                 assim_motifs=";".join(f"{k}:{v}" for k, v in sorted(a.items(), key=lambda kv: str(kv[0]))),
                 assim_total=sum(a.values()), assim_cross=sum(v for k, v in a.items() if k != b["motif"]))
        if slot is not None:
            p0 = b["pred"].get(slot)
            roles = sorted({(b["pred"][ps], k) for ps, k in b["parents"].get(slot, [])})
            r["seat_pred_born"] = p0
            if roles:
                tri = ST["tri"].get(sm, set())
                r.update(role="|".join(f"{pp}#{k}" for pp, k in roles),
                         role_in_scene_motif=int(any(pp == x[0] and k == x[1] for pp, k in roles for x in tri)),
                         role_same_pred=int(any((pp, k, p0) in tri for pp, k in roles)))
        if "worldvariant" in sys.modules:
            sw = _switch_ids(b["base_t"]) if b["base_t"] is not None else set()
            r.update(born_variant=_variant(d.registered_at), base_variant=(_variant(b["base_t"]) if b["base_t"] is not None else ""),
                     def_switch_seats=sum(1 for x in b["rid"].values() if x in sw))
    if "worldvariant" in sys.modules:
        import worldvariant as V
        info = V.INFO.get(scene.graph_id) or {}
        r.update(scene_variant=info.get("variant"), held_out_switch=info.get("held_out_switch") or "")
        if info.get("held_out_switch"):
            vis = {x.relation_id for x in scene.relations}
            other = [x for x in info.get("switch", {}).values() if x != held.relation_id]
            r["other_switch_visible"] = int(all(x in vis for x in other)) if other else ""
    ST["w"].writerow([r.get(c, "") for c in ST["cols"]])
    ST["rows"] += 1


def close() -> dict:
    f = ST.get("f")
    if f is not None:
        f.close()
    return {"rows": ST.get("rows", 0), "births": len(ST.get("birth", {}))}
