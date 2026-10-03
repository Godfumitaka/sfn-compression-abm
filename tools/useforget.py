"""使用で強める腕 D（D-最小）：旗 --use-forget τ。2026-10-01 昼の予約の委任書「使用で強める腕 D の実装と走行（改訂 2：D-最小）」。
★ abm/ は変えない。旗を切れば何もしない。今の B（席の点数が λ を下回れば一段薄くする）の判断の代わりに、名前の使用の強さで薄くする。
  E（まとめる判断）は今のまま（--e-price）。

1 名前の使用（試行ごと、同じ試行では一回だけ）：本物の予測（試験 --probe-world・反実仮想のやり直しは数えない）で、
  (a) 選ばれた定義（tools/v39.py select_definition の一位。発話の門を判定する前）の採用された照合で、その席の名前が照合の成立に実際に使われた。
      F：席の固定の名が、写った場面の関係（見えている関係）の名と一致。H：写った場面の関係の名が、その席の履歴（回数 1 以上）にある。
      門を通らず黙った試行でも数える。高階の席・シール・link も含む（席の種類を問わない）。
  (b) 話した答えの名前を、その席から取り出した（F の投影・F の穴埋め・H の穴埋め）。
  別に記録するが数えないもの：伏せた位置（見えていない ID）に写っただけ（構造だけ）・選ばれなかった候補の定義の照合で写った・U の席の照合。
2 誕生（覚え直しを含む）の試行に一回の使用を付ける。D の判断は誕生の次の試行から。
3 強さ S ＝ Σ_使った時点 w(今 − その時点)。w は今の B の点数の古さの重み（tools/v39.py の 16 本の減衰 _pow と mean16、--v39-decay actr）。
  席ごとに 16 本の記録（t0, 16 本）を持ち、使用のたびに今へ減衰させてから 1 を足す（tools/v39.py rec_add と同じ形）。
4 薄くする決まり：今の B が判断する時点（tools/v39.py run_conversions、削除の段）で、全部の定義の U でない席について、S ＜ τ なら、
  その席の名前をまとめて失う（F は H を経て U まで、同じ判断の中で進める。H は U）。今の B の λ による判断はしない。
  やり方：変換の候補（tools/v39.py _candidates、B＋E では tools/v310be.py candidates）を包み、S ＜ τ の席の候補だけを残して、点を −1e9 にする
    （変換の段は点が λ 未満の候補を尽きるまで変換し、一つ変換するたびにその定義の候補を作り直すので、F→H→U が同じ判断の中で進む）。
    費用の勘定・出来事の記録・退役（全席 U）は今の仕組みのまま。
★ 仮の決定（関門に関わらない細部。既存のコードを最も変えない選び方）：
  - 同じ判断の中の変換の順は、今の変換の段の同点の選び方（点がすべて −1e9 で同点）に任せる。
  - 解放量が 0 以下で候補が作られない席（tools/v310be.py candidates の zero_release）は、S ＜ τ でも変換されない。その数を記録する。
  - 席の同一性は（定義の名前, 席の番号, 定義が生まれた試行）。覚え直し（U→H）で記録を作り直す。退役した定義の記録は捨てる。
記録：side/<セル>/seed<種>.useforget.jsonl（試行ごとに一行：名前の使用・構造だけ・候補の照合・薄くした席とその S など）。
  薄くした席：[定義, 席, 生まれた試行, S, 判断のあとの状態, 誕生の試行, 判断の前の状態, 誕生のほかの名前の使用の回数, 種類]。
  10 試行ごと（と最後の試行）に、生きている全部の席の [定義, 席, 生まれた試行, 状態, S, 種類] を "snap" に書く（定義の中の S のばらつき・種類ごとの時間変化）。
  種類（記録だけ。研究者の側）：根・T 階は tools/cfvalue.py と同じ見分け（席の関係 ID の世界の述語）、シール・link は tools/shopworld.py の IDS。
  較正用（--use-forget-dump-s）：試行 100 以降の各試行の終わりに、生きている（U でない）全部の席の S を side/<セル>/seed<種>.useforget_S.f64 に書く。
"""
from __future__ import annotations

import json
from array import array

ST: dict = {}
SENTINEL = -1e9


def _key(d, row):
    return (d.name, row.slot_index, d.registered_at)


def _decayed(rec, t):
    import v39
    t0, vec = rec
    w = v39._pow(max(t - t0, 0))
    return [x * k for x, k in zip(vec, w)]


def strength(rec, t) -> float:
    import v39
    return v39.mean16(_decayed(rec, t)) if rec is not None else 0.0


def _use(key, t):
    if key in ST["used_t"]:
        return False
    ST["used_t"].add(key)
    rec = ST["S"].get(key)
    vec = _decayed(rec, t) if rec is not None else [0.0] * 16
    ST["S"][key] = (t, [x + 1.0 for x in vec])
    return True


def install(fo_path, *, tau: float, dump_s_path=None, horizon=None) -> None:
    """tools/v3_run.py の worker で、ほかの差し替えのすべてのあと（一番外）に入れる。
    試験（--probe-world）・腕 C（--cf-learn）・--cf-value は、入れた時点の予測を控えて使うので、この包みの外で予測する（数えない）。"""
    import abm.loop as loop
    import v39
    ST.clear()
    ST.update(t=None, horizon=horizon, tau=float(tau), f=open(fo_path, "w", encoding="utf-8"), S={}, born={}, n_use={}, used_t=set(), real=False, trial=None,
              rec=None, rows=0, dumps=open(dump_s_path, "wb") if dump_s_path else None, stats={"forget_seats": 0, "uses": 0,
              "no_candidate_below_tau": 0, "trial_mismatch": 0})

    # (a) 選ばれた定義の照合（本物の予測のときだけ）
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
        if res is not None:
            _record_matching(state, scene, res)
            best = res[2].name
            ST["rec"]["other"] = sum(1 for d, al in got if al is not None and d.name != best for row in d.constituents
                                     if v39.seat_state(d, row, state.slot_history) != "U" and row.relation.relation_id in al.relation_mapping)
        return res

    v39.select_definition = select_definition
    # 試行の番号：本物の予測の直前に呼ばれる abm/loop.py _agent_input(trial, state) から取る
    real_ai = loop._agent_input

    def _agent_input(trial, state):
        ST["t"] = trial.trial
        return real_ai(trial, state)

    loop._agent_input = _agent_input
    real_predict = loop.predict

    def predict(agent_input, state, config, rng):
        ST["real"] = True
        ST["rec"] = {"uses": [], "struct": [], "other": 0, "answer": None}
        try:
            out, pending = real_predict(agent_input, state, config, rng)
        finally:
            ST["real"] = False
        _record_answer(state, out)
        return out, pending

    loop.predict = predict

    # 誕生（m1）と覚え直し（reconcile）
    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        out, reg = real_m1(state, base, target, alignment, trial, **kw)
        if reg is not None and not reg["was_extension"]:
            d = out.definitions[reg["R"]]
            for row in d.constituents:
                _birth(_key(d, row), trial)
        return out, reg

    loop.m1 = m1
    real_rec = v39.reconcile

    def reconcile(state, trial, why):
        n0 = len(v39.CTX.get("relearn") or [])
        out = real_rec(state, trial, why)
        for ev in (v39.CTX.get("relearn") or [])[n0:]:
            d = out.definitions[ev["R"]]
            row = next(r for r in d.constituents if r.slot_index == ev["slot"])
            ST["S"].pop(_key(d, row), None)
            _birth(_key(d, row), trial)
        return out

    v39.reconcile = reconcile

    # 薄くする判断：変換の候補を包む
    real_cands = v39._candidates

    def _candidates(state, d, t, L, n_defs):
        out = []
        for c in real_cands(state, d, t, L, n_defs):
            row = next(r for r in d.constituents if r.slot_index == c[3])
            k = _key(d, row)
            if ST["born"].get(k) == t:
                continue
            if strength(ST["S"].get(k), t) < ST["tau"]:
                out.append((SENTINEL,) + tuple(c[1:]))
        return out

    v39._candidates = _candidates
    real_rc = v39.run_conversions

    def run_conversions(state, trial):
        if ST.get("t") != trial:
            ST["stats"]["trial_mismatch"] += 1
        below = {}
        for d in state.definitions.values():
            for row in d.constituents:
                if v39.seat_state(d, row, state.slot_history) == "U":
                    continue
                k = _key(d, row)
                s = strength(ST["S"].get(k), trial)
                if ST["born"].get(k) != trial and s < ST["tau"]:
                    below[k] = (s, v39.seat_state(d, row, state.slot_history), _kinds(row.relation.relation_id))
        res = real_rc(state, trial)
        after = res[0]
        forgot = []
        for k, (s, st0, kd) in below.items():
            d = after.definitions.get(k[0])
            row = next((r for r in d.constituents if r.slot_index == k[1]), None) if d is not None and d.registered_at == k[2] else None
            st = v39.seat_state(d, row, after.slot_history) if row is not None else "退役"
            if st in ("U", "退役"):
                forgot.append([k[0], k[1], k[2], round(s, 9), st, ST["born"].get(k), st0, ST["n_use"].get(k, 0), kd])
            else:
                ST["stats"]["no_candidate_below_tau"] += 1
        ST["stats"]["forget_seats"] += len(forgot)
        for k in [k for k in ST["S"] if k[0] not in after.definitions or after.definitions[k[0]].registered_at != k[2]]:
            ST["S"].pop(k, None)
            ST["n_use"].pop(k, None)
        rec = ST.pop("rec", None) or {}
        line = {"trial": trial, "uses": rec.get("uses", []), "struct_only": rec.get("struct", []), "other_cand_mapped": rec.get("other", 0),
                "answer_seat": rec.get("answer"), "forgot": forgot, "births": [list(k) for k, b in ST["born"].items() if b == trial]}
        if trial % 10 == 0 or trial == (ST.get("horizon") or 0) - 1:
            line["snap"] = [[d.name, row.slot_index, d.registered_at, st, round(strength(ST["S"].get(_key(d, row)), trial), 6),
                             _kinds(row.relation.relation_id)]
                            for d in after.definitions.values() for row in d.constituents
                            for st in [v39.seat_state(d, row, after.slot_history)] if st != "U"]
        ST["f"].write(json.dumps(line, ensure_ascii=False) + "\n")
        ST["rows"] += 1
        if ST["dumps"] is not None and trial >= 100:
            vals = []
            for d in after.definitions.values():
                for row in d.constituents:
                    if v39.seat_state(d, row, after.slot_history) != "U":
                        vals.append(strength(ST["S"].get(_key(d, row)), trial))
            array("d", vals).tofile(ST["dumps"])
        ST["used_t"] = set()
        return res

    v39.run_conversions = run_conversions


def _kinds(rid):
    import sys
    k = []
    cv = sys.modules.get("cfvalue")
    if cv is not None and cv.ST.get("pred") is not None:
        p = cv.ST["pred"].get(rid)
        if p in cv.ROOT_PREDS:
            k.append("根")
        if p in cv.T_PREDS:
            k.append("T 階")
    sw = sys.modules.get("shopworld")
    if sw is not None:
        x = sw.IDS.get(rid)
        if x == "sig":
            k.append("シール")
        elif x == "link":
            k.append("link")
    return k


def _birth(k, t):
    ST["n_use"][k] = 0
    ST["born"][k] = t
    ST["used_t"].discard(k)
    _use(k, t)
    ST["stats"]["uses"] += 1


def _record_matching(state, scene, res):
    import v39
    _r, _s, d, _g, al, _n, _tie, _passed = res
    vis = {r.relation_id: r for r in scene.relations}
    t = ST["t"]
    rec = ST["rec"]
    for row in d.constituents:
        st = v39.seat_state(d, row, state.slot_history)
        m = al.relation_mapping.get(row.relation.relation_id)
        if m is None:
            continue
        if st == "U":
            rec["struct"].append([row.slot_index, "U"])
            continue
        C = vis.get(m)
        if C is None:
            rec["struct"].append([row.slot_index, st])
            continue
        ok = (C.predicate == row.relation.predicate) if st == "F" else \
            (v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).get(C.predicate, 0) >= 1)
        if ok and _use(_key(d, row), t):
            ST["n_use"][_key(d, row)] = ST["n_use"].get(_key(d, row), 0) + 1
            rec["uses"].append([d.name, row.slot_index, "照合", st])
            ST["stats"]["uses"] += 1


def _record_answer(state, out):
    import v39
    from abm.domains import EdgePrediction
    pred = out.prediction
    R = out.trace.get("R_used")
    if not isinstance(pred, EdgePrediction) or R is None or R not in state.definitions:
        return
    d = state.definitions[R]
    rid = pred.edge.relation_id
    slot = None
    if rid.startswith("sme_projection__"):
        base = rid[len("sme_projection__"):]
        slot = next((r.slot_index for r in d.constituents if r.relation.relation_id == base), None)
    elif rid.startswith("filling__"):
        slot = int(rid.rsplit("__", 2)[1])
    row = next((r for r in d.constituents if r.slot_index == slot), None)
    if row is None:
        return
    st = v39.seat_state(d, row, state.slot_history)
    if st == "U":
        ST["rec"]["answer"] = [R, slot, "U（数えない）"]
        return
    t = ST["t"]
    if _use(_key(d, row), t):
        ST["n_use"][_key(d, row)] = ST["n_use"].get(_key(d, row), 0) + 1
        ST["rec"]["uses"].append([R, slot, "答え", st])
        ST["stats"]["uses"] += 1
    ST["rec"]["answer"] = [R, slot, st]


def close() -> dict:
    for k in ("f", "dumps"):
        if ST.get(k) is not None:
            ST[k].close()
    return {"rows": ST.get("rows", 0), **ST.get("stats", {})}
