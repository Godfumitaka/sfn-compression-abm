"""定義の選びと門の記録（2026-10-01 夕方の委任書「D-最小の外れの中身」の段 2）：旗 --dump-door。
★ 記録だけ。模型は変えない（台帳・side の今のファイルは旗の有無で一字一句同じ）。--v39 と一緒に使う。
本物の予測ごと（試験 --probe-world・--cf-value のやり直しは数えない）に、予測の直前の状態とそのときの照合から、
side/<セル>/seed<種>.door.jsonl へ一行ずつ書く（答えた試行も黙った試行も）。

本人に見える量
  sel：選ばれた定義（tools/v39.py select_definition の一位）[名前, 生まれた試行, 支持, F＋H の席の数, 門の必要数, 門を通ったか,
       三分類 vis（見えている関係に対応）・hid（見えていない ID＝親から伏せた位置に対応）・none（対応先なし）, vis_match（vis のうち名が合った数）]
       名が合う：F は固定の名＝場面の関係の名、H は場面の関係の名が履歴（回数 1 以上）にある（tools/useforget.py と同じ）。
       門の必要数＝abm/agent_runtime.py _need(tau_acc, F＋H)。門を通った＝支持 ≥ 必要数（tools/v39.py predict と同じ比べ）。
  seal：選ばれた定義のシールの席ごとに [席, 状態 F/H/U, 照合]。照合＝合った／名が違う／伏せた位置／対応先なし（U の席は U:… と書く）。
        シールの席が無ければ空の一覧。シールの席の見分けは tools/shopworld.py の IDS（研究者の側の登録。記録の印にだけ使う）。
  rank：照合できた全部の候補の定義を、選ぶ段と同じ並びで [名前, 生まれた試行, 支持の割合, 支持, F＋H, vis, hid, none, vis_match]。一つ目が選ばれた定義、二つ目が次点。
  live：その時点の全部の定義 [名前, 生まれた試行, F＋H の席の数]。
  out：予測の種類（Edge／Abstain）と棄権の理由、答えの出どころ（F_proj・<状態>_fill）と席。
研究者の側の量（正解か・場面の型・シール・定義の材料の場面）は、台帳と side の誕生・同化の記録から後づけで足す（記録には入れない）。
"""
from __future__ import annotations

import json

ST: dict = {}


def _tri(d, al, scene, state):
    import v39
    vis_ids = {r.relation_id: r for r in scene.relations}
    vis = hid = none = match = 0
    for row in d.constituents:
        st = v39.seat_state(d, row, state.slot_history)
        if st == "U":
            continue
        m = al.relation_mapping.get(row.relation.relation_id) if al is not None else None
        if m is None:
            none += 1
        elif m in vis_ids:
            vis += 1
            C = vis_ids[m]
            ok = (C.predicate == row.relation.predicate) if st == "F" else \
                (v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).get(C.predicate, 0) >= 1)
            match += ok
        else:
            hid += 1
    return vis, hid, none, match


def _seal(d, al, scene, state):
    import sys
    import v39
    ids = sys.modules["shopworld"].IDS if "shopworld" in sys.modules else {}
    vis_ids = {r.relation_id: r for r in scene.relations}
    out = []
    for row in d.constituents:
        if ids.get(row.relation.relation_id) != "sig":
            continue
        st = v39.seat_state(d, row, state.slot_history)
        m = al.relation_mapping.get(row.relation.relation_id) if al is not None else None
        if m is None:
            res = "対応先なし"
        elif m not in vis_ids:
            res = "伏せた位置"
        elif st == "U":
            res = "写った"
        else:
            C = vis_ids[m]
            ok = (C.predicate == row.relation.predicate) if st == "F" else \
                (v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).get(C.predicate, 0) >= 1)
            res = "合った" if ok else "名が違う"
        out.append([row.slot_index, st, (f"U:{res}" if st == "U" else res)])
    return out


def install(path) -> None:
    """tools/v3_run.py の worker で、ほかの差し替えのすべてのあと（一番外）に入れる。"""
    import abm.agent_runtime as ar
    import abm.loop as loop
    import v39
    ST.clear()
    ST.update(f=open(path, "w", encoding="utf-8"), real=False, t=None, rec=None, rows=0)
    real_ai = loop._agent_input

    def _agent_input(trial, state):
        ST["t"] = trial.trial
        return real_ai(trial, state)

    loop._agent_input = _agent_input
    real_select = v39.select_definition

    def select_definition(state, scene, config):
        if not ST["real"]:
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
        rank = []
        for d, al in got:
            if al is None:
                continue
            n = v39.n_FH(d, state.slot_history)
            sup = sum(1 for row in d.constituents if v39.seat_state(d, row, state.slot_history) != "U"
                      and row.relation.relation_id in al.relation_mapping)
            rank.append((sup / n, sup, d, al, n))
        rank.sort(key=lambda it: (-it[0], -it[4], -it[2].registered_at, it[2].name))
        rec = ST["rec"]
        rec["rank"] = [[d.name, d.registered_at, r, s, n, *_tri(d, al, scene, state)] for r, s, d, al, n in rank]
        if res is not None:
            _r, s, d, _g, _al, n, _tie, _passed = res
            al = next((a for dd, a in got if dd.name == d.name), None)     # 選ぶ段が使った照合（候補だけに絞る前）
            need = ar._need(config.tau_acc, n)
            rec["sel"] = [d.name, d.registered_at, s, n, need, s >= need, *_tri(d, al, scene, state)]
            rec["seal"] = _seal(d, al, scene, state)
            rec["sel_is_rank0"] = bool(rank) and rank[0][2].name == d.name
        return res

    v39.select_definition = select_definition
    real_predict = loop.predict

    def predict(agent_input, state, config, rng):
        ST["real"] = True
        ST["rec"] = {"t": ST["t"], "sel": None, "seal": None, "rank": [],
                     "live": [[d.name, d.registered_at, v39.n_FH(d, state.slot_history)] for d in state.definitions.values()]}
        try:
            out, pending = real_predict(agent_input, state, config, rng)
        finally:
            ST["real"] = False
        rec = ST.pop("rec")
        _out(rec, state, out)
        ST["f"].write(json.dumps(rec, ensure_ascii=False) + "\n")
        ST["rows"] += 1
        return out, pending

    loop.predict = predict


def _out(rec, state, out):
    import v39
    from abm.domains import EdgePrediction
    pred = out.prediction
    if not isinstance(pred, EdgePrediction):
        rec["out"] = ["Abstain", getattr(pred, "reason", None), None, None]
        return
    R = out.trace.get("R_used")
    rid = pred.edge.relation_id
    d = state.definitions.get(R)
    slot = None
    if d is not None and rid.startswith("sme_projection__"):
        base = rid[len("sme_projection__"):]
        slot = next((r.slot_index for r in d.constituents if r.relation.relation_id == base), None)
    elif rid.startswith("filling__"):
        slot = int(rid.rsplit("__", 2)[1])
    row = next((r for r in d.constituents if r.slot_index == slot), None) if d is not None else None
    st = v39.seat_state(d, row, state.slot_history) if row is not None else ""
    src = "F_proj" if rid.startswith("sme_projection__") else (f"{st}_fill" if rid.startswith("filling__") else "other")
    rec["out"] = ["Edge", None, src, slot]


def close() -> dict:
    if ST.get("f") is not None:
        ST["f"].close()
    return {"rows": ST.get("rows", 0)}
