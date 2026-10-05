"""反実仮想の保持価値の診断（2026-10-01 午前の返事の段 5）：旗 --cf-value。★ 記録だけ。学習・状態・乱数・台帳・ほかの side は変えない。
いつ：開示があった試行。開示を学びに使う前の、予測の直前の記憶と、本人に見えていた場面（提示）で測る。
  （loop.predict を包んで予測の直前の状態と提示を控え、会計の段（loop._update_accounting）の入口で、開示の有無を見て測る。）
どの席：選ばれた定義（台帳の R_used）の席のうち、次の種類（重なれば全部書く）。U の席は対象外。
  答えた席・答えた席の親（その席の関係を引数に持つ行）・根（一番上の関係）・T 階（部分木 T をまとめる関係）・
  お店の世界ではシール（sig_n／sig_e）と link（attach）の席。
  根と T 階は、席の関係 ID と同じ ID の世界の関係の述語（研究者の側。種ファイルの骨組みの語）で見分ける。シールと link は tools/shopworld.py の IDS。
どう測る（一席ずつ）：
  1 本物の記憶（凍った状態）はそのまま。写しとして、その席だけを今の規則（tools/v39.py _convert：F→H は行を墓石に、H→U は履歴を外す）で一段薄くした状態を作る。
  2 その状態で、予測（定義の選択・照合・発話の門・--answer-gap・最終回答。tools/v3_run.py の旗のとおり）をやり直す。乱数は、本物の予測と同じ種
    （abm/loop.py _rng_seed(agent, 試行)）から新しく作る。正解は渡さない。
  3 書き直し費用：答えが開示の関係と述語・引数とも同じなら 0、誤答・棄権なら開示の述語の符号長（予測の直前の p̂ の符号表。tools/v310be.py _ell）。
  4 利益 ＝ 薄くした場合の費用 − 薄くしない場合（実際の答え）の費用。
一緒に書く：席の種類と状態・一段薄くしたときに空くビット（tools/v310be.py candidates の解放量。候補にならない席は空欄）・
  同じ席の今の B の点数（同じ candidates の V の分子と分母と R̄F・R̄H・R̄U・重み）・薄くした場合に選ばれた定義と答え・一試行あたりの計算時間。
確かめ：測る前後で、本物の状態の指紋（状態の repr の sha256）が同じこと（違えば止める）。部品の STATS・CTX などは測る前の値に戻す（tools/probeworld.py と同じ）。
記録：side/<セル>/seed<種>.cfvalue.jsonl（席ごとに一行）。
"""
from __future__ import annotations

import json
import sys
import time
from hashlib import sha256
from random import Random

ST: dict = {}
ROOT_PREDS = {"govern", "sustainedby"}
T_PREDS = {"couple", "anchor", "steer", "shield"}


def _fp(state) -> str:
    return sha256(repr(state).encode("utf-8")).hexdigest()


def install(path, *, agent_id="agent") -> None:
    """tools/v3_run.py の worker で、試験の旗（probeworld）のあと、答えごとの記録（answerlog）より前に入れる。"""
    import abm.loop as loop
    import abm.world as w
    ST.clear()
    ST.update(f=open(path, "w", encoding="utf-8"), pred={}, pre=None, rows=0, trials=0, checks=0, agent=agent_id,
              inner_predict=loop.predict)
    real_gen = w.generate_trial

    def generate_trial(rs, i, aids, *, seed, holdout_include_second_order=False):
        tr = real_gen(rs, i, aids, seed=seed, holdout_include_second_order=holdout_include_second_order)
        for r in tr.G_star.relations:
            ST["pred"].setdefault(r.relation_id, r.predicate)
        return tr

    w.generate_trial = generate_trial
    inner = loop.predict

    def predict(agent_input, state, config, rng):
        ST["pre"] = (agent_input, state, config)
        return inner(agent_input, state, config, rng)

    loop.predict = predict
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        if coin.f_fired and ST.get("pre") is not None:
            _measure(output, coin.t, revealed_edge)
        ST["pre"] = None
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting


def _measure(output, t, revealed):
    import abm.loop as loop
    import probeworld as pw   # 部品の控えと戻し（tools/probeworld.py の _snapshot_modules を使う）
    import v39
    import v310be
    from abm.domains import EdgePrediction
    agent_input, state, config = ST["pre"]
    R = output.trace.get("R_used")
    if R is None or R not in state.definitions:
        return
    t0 = time.time()
    snap = pw._snapshot_modules()
    fp0 = _fp(state)
    L = v39.code_lengths(state.p_hat)
    ell = v310be._ell(revealed.predicate, L)

    def cost(pred):
        if isinstance(pred, EdgePrediction) and pred.edge.predicate == revealed.predicate and tuple(pred.edge.arguments) == tuple(revealed.arguments):
            return 0.0
        return ell

    c_actual = cost(output.prediction)
    d = state.definitions[R]
    by_id = {row.relation.relation_id: row for row in d.constituents}
    ans_slot = None
    if isinstance(output.prediction, EdgePrediction):
        rid = output.prediction.edge.relation_id
        if rid.startswith("filling__"):
            ans_slot = int(rid.rsplit("__", 2)[1])
        elif rid.startswith("sme_projection__"):
            row = by_id.get(rid[len("sme_projection__"):])
            ans_slot = row.slot_index if row is not None else None
    ans_rid = next((row.relation.relation_id for row in d.constituents if row.slot_index == ans_slot), None)
    ids = sys.modules["shopworld"].IDS if "shopworld" in sys.modules else {}
    kinds = {}
    for row in d.constituents:
        k = []
        rid = row.relation.relation_id
        if row.slot_index == ans_slot:
            k.append("答えた席")
        if ans_rid is not None and ans_rid in row.relation.arguments:
            k.append("答えた席の親")
        p = ST["pred"].get(rid)
        if p in ROOT_PREDS:
            k.append("根")
        if p in T_PREDS:
            k.append("T 階")
        if ids.get(rid) == "sig":
            k.append("シール")
        if ids.get(rid) == "link":
            k.append("link")
        if k:
            kinds[row.slot_index] = k
    cands = {c[3]: c for c in v310be.candidates(state, d, t, L, len(state.definitions))}
    rows_out = []
    for row in d.constituents:
        s = row.slot_index
        if s not in kinds:
            continue
        st = v39.seat_state(d, row, state.slot_history)
        if st == "U":
            continue
        kind = "FH" if st == "F" else "HU"
        st2, _ev = v39._convert(state, kind, R, s, t)
        rng = Random(loop._rng_seed(ST["agent"], t))
        out2, _pend = ST["inner_predict"](agent_input, st2, config, rng)
        c2 = cost(out2.prediction)
        cd = cands.get(s)
        e2 = out2.prediction
        rec = {"trial": t, "R": R, "slot": s, "kinds": kinds[s], "state": st, "step": kind, "world_pred": ST["pred"].get(row.relation.relation_id),
               "cost_actual": c_actual, "cost_thinned": c2, "benefit": c2 - c_actual,
               "answer_actual": (output.prediction.edge.predicate if isinstance(output.prediction, EdgePrediction) else None),
               "abstain_actual": getattr(output.prediction, "reason", None),
               "answer_thinned": (e2.edge.predicate if isinstance(e2, EdgePrediction) else None),
               "abstain_thinned": getattr(e2, "reason", None), "R_used_thinned": out2.trace.get("R_used"),
               "freed_bits": (cd[4] if cd else None), "V": (cd[0] if cd else None),
               "V_num": ((cd[5][1] - cd[5][0]) if (cd and cd[1] == "FH") else (cd[5][2] - cd[5][1]) if cd else None),
               "V_den": (cd[4] if cd else None), "RF": (cd[5][0] if cd else None), "RH": (cd[5][1] if cd else None),
               "RU": (cd[5][2] if cd else None), "n": (cd[5][3] if cd else None)}
        rows_out.append(rec)
        pw._restore_modules(snap)
    fp1 = _fp(state)
    pw._restore_modules(snap)
    if fp0 != fp1:
        raise RuntimeError(f"--cf-value：測る前後で本物の状態の指紋が違う（試行 {t}）")
    ST["checks"] += 1
    sec = time.time() - t0
    for rec in rows_out:
        rec["sec_trial"] = sec
        ST["f"].write(json.dumps(rec, ensure_ascii=False) + "\n")
        ST["rows"] += 1
    ST["trials"] += 1


def close() -> dict:
    f = ST.get("f")
    if f is not None:
        f.close()
    return {"rows": ST.get("rows", 0), "trials": ST.get("trials", 0), "fingerprint_checks": ST.get("checks", 0)}
