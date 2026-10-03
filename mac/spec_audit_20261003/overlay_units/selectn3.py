"""選び方 N3（旗 --select-n3）と、選びの記録（記録だけの旗 --select-log）。2026-10-02 夜の委任書「選び方 N3 の実装・関門・走行」。
★ abm/ は変えない。旗を切れば何もしない（今の規則 tools/v39.py select_definition のまま）。方式の定義は ChatGPT（N3）、
  数え方はマックの tools/selcands.py（ブランチ spc-analysis-2026-10-01）と同じ。

N3(d, x) ＝ 2 S(d,x) ÷ (S(d,d) ＋ S(x,x))。S は非負の三項の和（合わなかった数の減点は入れない。係数はどれも 1）。
  S(d,x)（定義 d を場面 x に写した照合 al＝tools/v39.py map_v39 の結果で）：
    名前：見えている関係（提示の関係）に写った F・H の席の数。U の席は 0 点。
    引数：見えている関係に写った席すべて（U も構造として数える）の引数のうち、写り先の関係の同じ位置の引数に写った数（物・関係）。
    つながり：見えている関係に写った席どうしの親子の組（親の引数が子の関係 ID）で、子の写り先が親の写り先の同じ位置の引数である数。
  S(d,d)：恒等の対応で。名前＝F・H の席の数（U は 0）、引数＝全部の席の引数の位置の数、つながり＝引数が定義の行である位置の数（U を含む）。
  S(x,x)：提示の関係（照合器に渡している見えている関係）だけで、恒等の対応で。名前＝関係の数、引数＝引数の位置の数、
    つながり＝引数が提示の関係である位置の数。伏せた関係の名前はどこにも使わない。
  分母 0 の候補は選ばない（STATS["n3_den0"] に数える）。
選び方（--select-n3）：N3 が最大の定義。N3 の比べは分数で正確に行う。完全な同点だけ、今の規則の残りの順（F＋H の席の数の多い順 → 新しい順 → 名前）。
  支持の割合は順位に使わない。門は今のまま（選んだ定義の支持が ceil(0.67×(F＋H)) 以上。tools/v39.py predict）。通らなければ黙る（次点は探さない）。
  返り値は tools/v39.py select_definition と同じ形（割合・支持・定義・グラフ・照合（F の行の投影候補だけに絞る）・F＋H・同点か・門を通る定義の一覧）。
  C の答え直し（--cf-learn・--cf-value）・試験（--probe-world）の予測も tools/v39.py predict を通るので、同じく N3 で選ぶ。
  薄くした写しの定義の S(d,d) もその写しの状態で数えるので、自己の点は計算し直される。
--select-log：選びを変えずに（--select-n3 のときは N3 の選びのまま）、本物の予測ごとに候補ごとの量を side/<セル>/seed<種>.select.jsonl.gz に書く。
  候補：選ぶ段が照合した定義（F・H の席があり、照合が None でないもの）。欄：名前・生まれた試行・支持の分子と分母・N3 の三項・S(d,d)・S(x,x)・N3・
  今の規則での順位・N3 での順位・選ばれたか・今の門を通るか。照合は選ぶ段がその場で作ったものを控えて使う（照合を二度は作らない）。
"""
from __future__ import annotations

import gzip
import json
from dataclasses import replace
from fractions import Fraction

STATS: dict = {}
LOG: dict = {}


def n3_terms(d, sh, al, scene):
    """(名前, 引数, つながり, S(d,d), S(x,x))。tools/selcands.py の N3 の数え方と同じ。"""
    import v39
    vis = {r.relation_id: r for r in scene.relations}
    rm, em = al.relation_mapping, al.entity_mapping
    stt = {r.relation.relation_id: v39.seat_state(d, r, sh) for r in d.constituents}
    mapped_vis = [r for r in d.constituents if rm.get(r.relation.relation_id) in vis]
    n_name = sum(1 for r in mapped_vis if stt[r.relation.relation_id] != "U")
    n_arg = 0
    for r in mapped_vis:
        tgt = vis[rm[r.relation.relation_id]]
        for k, a in enumerate(r.relation.arguments):
            if k < len(tgt.arguments) and (em.get(a) == tgt.arguments[k] or rm.get(a) == tgt.arguments[k]):
                n_arg += 1
    mv_ids = {r.relation.relation_id for r in mapped_vis}
    n_link = 0
    for r in mapped_vis:
        tgt = vis[rm[r.relation.relation_id]]
        for k, a in enumerate(r.relation.arguments):
            if a in mv_ids and k < len(tgt.arguments) and rm.get(a) == tgt.arguments[k]:
                n_link += 1
    row_ids = {r.relation.relation_id for r in d.constituents}
    s_dd = (sum(1 for r in d.constituents if stt[r.relation.relation_id] != "U")
            + sum(len(r.relation.arguments) for r in d.constituents)
            + sum(1 for r in d.constituents for a in r.relation.arguments if a in row_ids))
    s_xx = (len(vis) + sum(len(r.arguments) for r in vis.values())
            + sum(1 for r in vis.values() for a in r.arguments if a in vis))
    return n_name, n_arg, n_link, s_dd, s_xx


def n3_value(terms):
    n_name, n_arg, n_link, s_dd, s_xx = terms
    den = s_dd + s_xx
    return None if den == 0 else Fraction(2 * (n_name + n_arg + n_link), den)


def select_definition_n3(state, scene, config):
    """tools/v39.py select_definition の写し。★ の所（並べ方）だけ違う。"""
    import abm.agent_runtime as ar
    import v39
    v39.STATS["select_calls"] = v39.STATS.get("select_calls", 0) + 1
    ranked = []
    for d in state.definitions.values():
        n = v39.n_FH(d, state.slot_history)
        if n == 0:
            continue
        graph, alignment = v39.map_v39(d, state.slot_history, scene)
        if alignment is None:
            continue
        support = sum(1 for row in d.constituents
                      if v39.seat_state(d, row, state.slot_history) != "U"
                      and row.relation.relation_id in alignment.relation_mapping)
        q = n3_value(n3_terms(d, state.slot_history, alignment, scene))          # ★ N3
        if q is None:
            STATS["n3_den0"] = STATS.get("n3_den0", 0) + 1
            continue
        ranked.append((support / n, support, d, graph, alignment, n, q))
    if not ranked:
        return None
    ranked.sort(key=lambda it: (-it[6], -it[5], -it[2].registered_at, it[2].name))   # ★ N3 → 席の数 → 新しさ → 名前
    best = ranked[0]
    tie_event = sum(it[6] == best[6] and it[5] == best[5] and it[2].registered_at == best[2].registered_at for it in ranked) > 1
    passed = [{"R": d.name, "support": s, "m_live": n, "ratio": r, "selected": d.name == best[2].name}
              for r, s, d, _g, _a, n, _q in ranked if s >= ar._need(config.tau_acc, n)]
    ratio, support, d, graph, alignment, n, _q = best
    f_ids = {row.relation.relation_id for row in d.constituents if row.alive}
    alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in f_ids))
    STATS["n3_selects"] = STATS.get("n3_selects", 0) + 1
    return ratio, support, d, graph, alignment, n, tie_event, passed


def install_n3() -> None:
    """tools/v3_run.py の worker で、v39・v310be のあと、select_definition を包む記録（answerlog・probeworld・useforget・--select-log）より前に入れる。"""
    import v39
    STATS.clear()
    STATS.update(n3_den0=0, n3_selects=0)
    v39.select_definition = select_definition_n3


def install_log(path) -> None:
    """tools/v3_run.py の worker で、ほかの差し替えのすべてのあと（一番外）に入れる。"""
    import abm.agent_runtime as ar
    import abm.loop as loop
    import v39
    LOG.clear()
    LOG.update(f=gzip.open(path, "wt", encoding="utf-8"), real=False, t=None, rows=0)
    real_ai = loop._agent_input

    def _agent_input(trial, st):
        LOG["t"] = trial.trial
        return real_ai(trial, st)

    loop._agent_input = _agent_input
    real_select = v39.select_definition

    def select_definition(state, scene, config):
        if not LOG["real"]:
            return real_select(state, scene, config)
        got = []
        real_map = v39.map_v39

        def map_v39(d, slot_history, sc):
            g, al = real_map(d, slot_history, sc)
            got.append((d, al))
            return g, al

        v39.map_v39 = map_v39
        try:
            res = real_select(state, scene, config)
        finally:
            v39.map_v39 = real_map
        sh = state.slot_history
        cands = []
        for d, al in got:
            if al is None:
                continue
            n = v39.n_FH(d, sh)
            sup = sum(1 for row in d.constituents if v39.seat_state(d, row, sh) != "U" and row.relation.relation_id in al.relation_mapping)
            terms = n3_terms(d, sh, al, scene)
            q = n3_value(terms)
            cands.append({"R": d.name, "reg": d.registered_at, "sup": sup, "n": n, "name": terms[0], "arg": terms[1], "link": terms[2],
                          "S_dd": terms[3], "S_xx": terms[4], "N3": (None if q is None else float(q)), "_q": q,
                          "gate": sup >= ar._need(config.tau_acc, n)})
        cur = sorted(cands, key=lambda c: (-(c["sup"] / c["n"]), -c["n"], -c["reg"], c["R"]))
        for k, c in enumerate(cur):
            c["rank_now"] = k + 1
        n3o = sorted((c for c in cands if c["_q"] is not None), key=lambda c: (-c["_q"], -c["n"], -c["reg"], c["R"]))
        for k, c in enumerate(n3o):
            c["rank_n3"] = k + 1
        sel = None if res is None else (res[2].name, res[2].registered_at)
        for c in cands:
            c["selected"] = (c["R"], c["reg"]) == sel
            c.pop("_q")
        LOG["f"].write(json.dumps({"t": LOG["t"], "cands": cur}, ensure_ascii=False) + "\n")
        LOG["rows"] += 1
        return res

    v39.select_definition = select_definition
    real_predict = loop.predict

    def predict(agent_input, state, config, rng):
        LOG["real"] = True
        try:
            return real_predict(agent_input, state, config, rng)
        finally:
            LOG["real"] = False

    loop.predict = predict


def close() -> dict:
    if LOG.get("f") is not None:
        LOG["f"].close()
    return {"n3": dict(STATS), "select_log_rows": LOG.get("rows", 0)}
