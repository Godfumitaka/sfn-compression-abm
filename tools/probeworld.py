"""内的世界の試験（旗 --probe-world、記録だけ）。2026-09-30 夕方の委任書「個体の走行に『内的世界の試験』を、記録だけの旗で入れる」。
★ abm/ は変えない。記録だけ：記憶・履歴・成績・全体の頻度・逐語の記憶を一切変えず、採点も届けず、世界・学習の乱数を消費しない。
  台帳・side・答えの記録は旗の有無で一字一句同じ。試験の記録は side/<セル>/seed<種>.probe.jsonl に別に書く。

試験の場面：走行の初めに、世界とは別の流れ（run_seed の代わりに "probe‖run_seed"）で abm.world.generate_trial（その腕の世界の旗を含む）を呼んで作り、固定する。
  四つの型それぞれ一場面（その流れで試行の番号 0, 1, … を順に見て、型ごとに最初のもの）。
  その場面の骨組みの関係（一階・高階。型の展開の経路 tree:<経路> の関係）を一本ずつ伏せた問いにする。見えている部分と物は、今の世界の作り方と同じ。
試験の時点：試行 t−1 の終わり（削除の段のあと）の状態で、t＝100, 200, …, 1,700 と、走行の終わり（t＝試行数）に答えさせる。
  答え方は、その腕の旗のとおりの予測（照合・門・選び方・候補ごとの棄権・U の扱い）。予測の乱数は別の流れ（sha256("probe"‖種‖時点‖問い)）。
  試験の前後で、状態の指紋（状態の repr の sha256）が同じことを毎回確かめ、違えば止める。部品の STATS・CTX などの控えも、試験の前の値に戻す。
記録（問いごとに一行）：
  t・型・伏せた関係の経路（path）・階（level、一階＝1）・世界での述語（truth）・親の（述語, 位置）の並び（role、粗い読み）
  ★ 外挿の印の道具の「粗い・細かい状況の鍵」は、この版の道具にも control/ にも定義が見つからなかったので、鍵そのものは作らず、材料（型・経路・階・親の述語と位置）を書く。
  答え（述語・引数）か棄権（理由）・答えの出どころ（F_proj・F_fill・H_fill・U_fill）・選ばれた定義（名前＠生まれた試行）・支持の三分類（sel_vis・sel_hid・sel_none・sel_vis_match）
  オラクル：答えた関係（述語と引数の組）が試験の場面の関係にあれば真、無ければ偽。
  経験（研究者が世界の歴史から数える。その試行の前まで）：
    exp_path＝同じ型の場面の、同じ経路の関係の中身を見た回数（見えていた、又は伏せられて開示された）・名ごとの回数・最後に見た名。
    exp_role＝型を問わず、同じ親の（述語, 位置）の関係の中身を見た回数・名ごとの回数・最後に見た名（粗い読み）。
  逐語の記憶：その時点の逐語の記憶の場面（written_at＝世界の試行）のうち、同じ型で同じ経路の関係が見えている場面の数と、その中身。
  状態のまとめ：定義の数・記憶のビット C（tools/v39.py total_bits、その時点の p̂ の符号表）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from hashlib import sha256
from random import Random

ST: dict = {}
SNAP_MODULES = ("v39", "v310be", "fixorder2", "fix2", "v32", "projfirst", "fillnorestate", "fillunseen", "nocharge2", "v38", "v31",
                "histrole", "ustruct", "relearninit", "tiestruct", "answerlog", "worldvariant", "worldcue", "deathterms", "checks_v37",
                "routelog", "answergap", "shopworld")
SNAP_ATTRS = ("STATS", "CTX", "ST", "INFO", "TCTX")


def _snapshot_modules():
    snap = []
    for name in SNAP_MODULES:
        m = sys.modules.get(name)
        if m is None or m is sys.modules.get(__name__):
            continue
        for a in SNAP_ATTRS:
            d = getattr(m, a, None)
            if isinstance(d, dict):
                snap.append((d, {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in d.items()}))
    return snap


def _restore_modules(snap):
    for d, saved in snap:
        d.clear()
        d.update(saved)


def _fingerprint(state) -> str:
    return sha256(repr(state).encode("utf-8")).hexdigest()


def _partial(G, hidden_id):
    from abm.domains import RelationGraph
    visible = tuple(r for r in G.relations if r.relation_id != hidden_id)
    ids = frozenset(r.relation_id for r in visible)
    ents = {e.entity_id for e in G.entities}
    reach = frozenset(a for r in visible for a in r.arguments if a not in ids and a in ents)
    return RelationGraph(graph_id=G.graph_id, entities=tuple(e for e in G.entities if e.entity_id in reach), relations=visible)


def _paths(seed_data, run_seed, t, motif):
    """経路 → (関係 ID, 階, 述語, 親の経路と位置の並び)"""
    import abm.world as w
    sk = w._expand_motif(seed_data, motif)
    rid = {path: w.opaque_id(run_seed, t, f"relation:tree:{path}") for _, (_l, path, _p, _c) in sk}
    parents = {}
    for _, (_l, path, _p, ch) in sk:
        for k, c in enumerate(ch or ()):
            parents.setdefault(c, []).append((path, k))
    return {path: (rid[path], lvl, pred, parents.get(path, [])) for _, (lvl, path, pred, _c) in sk}, {path: pred for _, (_l, path, pred, _c) in sk}


def install(path, *, run_seed, agent_ids, seed_file, horizon, holdout_second) -> None:
    """tools/v3_run.py の worker で、ほかの差し替え（v39・v310be・世界の旗）のあと、答えごとの記録（answerlog）より前、世界を作る前に入れる。"""
    import abm.loop as loop
    import abm.world as w
    from abm.seed import load_seed
    sd = load_seed(seed_file)
    ST.clear()
    ST.update(f=open(path, "w", encoding="utf-8"), run_seed=run_seed, sd=sd, horizon=horizon, trials={}, disclosed={}, probes=[],
              checks=0, rows=0, predict=loop.predict)
    motifs = tuple(sd.data["motif_structure"])
    prs = f"probe\x1f{run_seed}"
    snap = _snapshot_modules()
    found = {}
    i = 0
    while len(found) < len(motifs) and i < 10000:
        m = w._motif_for_trial(prs, i, motifs)
        if m not in found:
            found[m] = w.generate_trial(prs, i, agent_ids, seed=sd, holdout_include_second_order=holdout_second)
        i += 1
    _restore_modules(snap)
    for m in motifs:
        tr = found[m]
        info, _ = _paths(sd.data, prs, tr.trial, m)
        by_id = {r.relation_id: r for r in tr.G_star.relations}
        for p, (hid, lvl, pred, par) in sorted(info.items()):
            if hid not in by_id:
                continue
            role = [(info[pp][2], k) for pp, k in par]
            ST["probes"].append({"motif": m, "path": p, "level": lvl, "truth": by_id[hid].predicate, "role": role, "hid": hid,
                                 "G": tr.G_star, "partial": _partial(tr.G_star, hid),
                                 "facts": {(r.predicate, tuple(r.arguments)) for r in tr.G_star.relations}})

    # 世界の歴史（研究者の側）：場面と開示を控える
    real_gen = w.generate_trial

    def generate_trial(rs, trial_index, aids, *, seed, holdout_include_second_order=False):
        tr = real_gen(rs, trial_index, aids, seed=seed, holdout_include_second_order=holdout_include_second_order)
        if rs == run_seed:
            ST["trials"][trial_index] = tr
        return tr

    w.generate_trial = generate_trial
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        ST["disclosed"][coin.t] = bool(coin.f_fired)
        ST["config"] = config
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting
    real_theta = loop.apply_theta

    def apply_theta(state, config, trial, *a, **k):
        after, events = real_theta(state, config, trial, *a, **k)
        nxt = trial + 1
        if nxt % 100 == 0 and nxt < horizon:
            _probe(after, config, nxt)
        if trial == horizon - 1:
            _probe(after, config, horizon)
        return after, events

    loop.apply_theta = apply_theta


def _seen(t_limit, key_fn):
    """試行 t_limit の前までに、key_fn(試行の場面) が返す関係の中身を見た回数（見えていた、又は伏せられて開示された）。"""
    names = Counter()
    last = None
    for tau in range(t_limit):
        tr = ST["trials"].get(tau)
        if tr is None:
            continue
        vis = {r.relation_id for r in tr.target_graph_partial.relations}
        for rid, pred in key_fn(tau, tr):
            if rid in vis or (rid == tr.held_out_edge.relation_id and ST["disclosed"].get(tau)):
                names[pred] += 1
                last = pred
    return names, last


def _paths_of(tau):
    """世界の試行 tau の骨組み：(型, {経路: (関係 ID, 階, 述語, 親)}, {役割（親の述語と位置の並び）: [(関係 ID, 述語)]})。一度だけ作って控える。"""
    import abm.world as w
    pc = ST.setdefault("pcache", {})
    if tau not in pc:
        rs = ST["run_seed"]
        m = w._motif_for_trial(rs, tau, tuple(ST["sd"].data["motif_structure"]))
        info, _ = _paths(ST["sd"].data, rs, tau, m)
        roles = {}
        for p, (rid, _lvl, pred_, par) in info.items():
            roles.setdefault(tuple((info[pp][2], k) for pp, k in par), []).append((rid, pred_))
        pc[tau] = (m, info, roles)
    return pc[tau]


def _probe(state, config, t):
    import v39
    from abm.domains import AgentInput, EdgePrediction
    snap = _snapshot_modules()
    fp0 = _fingerprint(state)
    L = v39.code_lengths(state.p_hat)
    summary = {"defs": len(state.definitions), "C": v39.total_bits(v39.ensure(state), L)}
    rs = ST["run_seed"]
    paths_of = _paths_of

    real_select = v39.select_definition
    for qi, q in enumerate(ST["probes"]):
        got = {}

        def select_definition(st, scene, cfg):
            res = real_select(st, scene, cfg)
            got["res"] = res
            return res

        v39.select_definition = select_definition
        try:
            rng = Random(int.from_bytes(sha256(f"probe\x1f{rs}\x1f{t}\x1f{qi}".encode()).digest()[:8], "big"))
            ai = AgentInput(q["partial"], q["partial"], tuple(r.relation_id for r in q["partial"].relations))
            out, pending = ST["predict"](ai, state, config, rng)
        finally:
            v39.select_definition = real_select
        pred = out.prediction
        rec = {"t": t, "motif": q["motif"], "path": q["path"], "level": q["level"], "truth": q["truth"], "role": q["role"]}
        rec.update(q.get("extra", {}))   # ★ お店の世界の試験の印（tools/shopworld.py add_probes）。ほかの試験には無い
        if isinstance(pred, EdgePrediction):
            e = pred.edge
            rid = e.relation_id
            if rid.startswith("sme_projection__"):
                src = "F_proj"
            else:
                sts = dict(zip(v39.CTX.get("fill_ids", ()), v39.CTX.get("fill_states", ())))
                src = f"{sts.get(rid, '?')}_fill"
            rec.update(answer=e.predicate, args=list(e.arguments), source=src,
                       oracle=int((e.predicate, tuple(e.arguments)) in q["facts"]) if q.get("score_truth", True) else None,
                       answer_is_truth=int(e.predicate == q["truth"]) if q.get("score_truth", True) else None)
        else:
            rec.update(answer=None, abstain=getattr(pred, "reason", None))
        res = got.get("res")
        if res is not None:
            _r, _s, d, _g, al, _n, _tie, _passed = res
            vis = {r.relation_id: r for r in q["partial"].relations}
            tri = [0, 0, 0, 0]
            for row in d.constituents:
                s_ = v39.seat_state(d, row, state.slot_history)
                if s_ == "U":
                    continue
                mm = al.relation_mapping.get(row.relation.relation_id)
                if mm in vis:
                    tri[0] += 1
                    pp = vis[mm].predicate
                    tri[3] += (pp == row.relation.predicate) if s_ == "F" else (v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).get(pp, 0) >= 1)
                elif mm is not None:
                    tri[1] += 1
                else:
                    tri[2] += 1
            rec.update(R=f"{d.name}@{d.registered_at}", R_used=out.trace.get("R_used") is not None,
                       sel_vis=tri[0], sel_hid=tri[1], sel_none=tri[2], sel_vis_match=tri[3])
        # 経験：同じ型・同じ経路
        if "verb_name" in q:
            import verbworld
            names, last = verbworld.seen(ST, t, q["verb_name"])
        else:
            names, last = _seen(t, lambda tau, tr: [(paths_of(tau)[1][q["path"]][0], paths_of(tau)[1][q["path"]][2])]
                                if paths_of(tau)[0] == q["motif"] and q["path"] in paths_of(tau)[1] else [])
        rec.update(exp_path_n=sum(names.values()), exp_path_names=dict(names), exp_path_last=last)
        rkey = tuple(tuple(x) for x in q["role"])
        if "verb_name" in q:
            names, last = verbworld.seen(ST, t, None)
        else:
            names, last = _seen(t, lambda tau, tr: paths_of(tau)[2].get(rkey, []))
        rec.update(exp_role_n=sum(names.values()), exp_role_names=dict(names), exp_role_last=last)
        # 逐語の記憶
        vb = Counter()
        for tr_ in state.prototype.traces:
            tau = tr_.written_at
            if "verb_name" in q and verbworld.INFO.get(tr_.scene.graph_id, {}).get("verb_name") != q["verb_name"]:
                continue
            m, info, _roles = paths_of(tau)
            if m != q["motif"] or q["path"] not in info:
                continue
            rid = info[q["path"]][0]
            hit = next((r.predicate for r in tr_.scene.relations if r.relation_id == rid), None)
            if hit is not None:
                vb[hit] += 1
        rec.update(verbatim_n=sum(vb.values()), verbatim_names=dict(vb), **summary)
        ST["f"].write(json.dumps(rec, ensure_ascii=False) + "\n")
        ST["rows"] += 1
    fp1 = _fingerprint(state)
    _restore_modules(snap)
    if fp0 != fp1:
        raise RuntimeError(f"--probe-world：試験の前後で状態の指紋が違う（時点 {t}）")
    ST["checks"] += 1


def close() -> dict:
    f = ST.get("f")
    if f is not None:
        f.close()
    return {"rows": ST.get("rows", 0), "fingerprint_checks": ST.get("checks", 0), "probes": len(ST.get("probes", []))}
