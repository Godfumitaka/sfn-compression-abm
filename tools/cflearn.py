"""反実仮想で学ぶ腕 C（2026-10-01 午前・改訂の段 3）：旗 --cf-learn。
今の B との違いは一点だけ：席の点数のもとになる「その席が F・H・U ならどうだったか」の書き直し費用を、その席自身の答えではなく、
エージェントが実際に言う最終的な答えで測る。忘れる判断（tools/v39.py run_conversions）は今の B と同じ。
いつ・どの席：開示のあった試行で、選ばれた定義（R_used）の U でない席全部（高階の席・シール・link を含む）。
測り方：--cf-value（tools/cfvalue.py）と同じ仕組み。予測の直前の状態（凍った状態）から、その席だけを今の規則（tools/v39.py _convert）で
  一段・二段薄くした写しを作り（F の席：H と U、H の席：U）、定義の選択から最終的な答えまでやり直す（tools/v3_run.py の旗のとおり）。
  今の状態（その席の今の状態）の答えは、実際の答え。正解はやり直しに渡さない。乱数は本物の予測と同じ種から新しく作る。
  書き直し費用：正解（述語と引数が開示の関係と同じ）なら 0、誤答・棄権なら開示の述語の符号長
  （採点の段の符号表 tools/v310be.py CTX["L_score"] と _ell。今の R と同じ定め方）。
点数の使い方：今の B の採点（tools/v39.py update_accounting が呼ぶ v39.score_answers）を包み、R̄F・R̄H・R̄U に上の費用を、同じ古さの重み
  （tools/v39.py rec_add、重み 1）で積む。F の列は F の席だけ（H の席は 0。今の採点と同じ）。席の世代・状態が予測のときと変わっていれば積まない（今と同じ）。
  席自身の答えでの採点（今の score_answers）は、この旗では積まない（二重に数えないため）。値は記録に残す。
記録：side/<セル>/seed<種>.cflearn.jsonl（席ごとに一行）：今の採点の値（その席が採点されたなら rF・rH・rU）と --cf-learn の値を並べる。一試行あたりの計算時間。
確かめ：測る前後で本物の状態の指紋が同じこと（違えば止める）。部品の STATS・CTX は測る前の値に戻す（tools/probeworld.py と同じ）。
"""
from __future__ import annotations

import json
import time
from hashlib import sha256
from random import Random

ST: dict = {}


def _fp(state) -> str:
    return sha256(repr(state).encode("utf-8")).hexdigest()


def _correct(pred, revealed) -> bool:
    from abm.domains import EdgePrediction
    return isinstance(pred, EdgePrediction) and pred.edge.predicate == revealed.predicate and \
        tuple(pred.edge.arguments) == tuple(revealed.arguments)


def variants_correct(state, agent_input, config, R, t, revealed, actual_pred, predict_fn, rng_seed):
    """席ごとに {状態: 正解か}。今の状態は実際の答え。返り値 {席: (今の状態, {状態: 正解か})}。本物の状態は変えない。"""
    import v39
    d = state.definitions[R]
    out = {}
    ok_actual = _correct(actual_pred, revealed)
    for row in d.constituents:
        s = row.slot_index
        st = v39.seat_state(d, row, state.slot_history)
        if st == "U":
            continue
        res = {st: ok_actual}
        if st == "F":
            sH, _ = v39._convert(state, "FH", R, s, t)
            sU, _ = v39._convert(sH, "HU", R, s, t)
            todo = (("H", sH), ("U", sU))
        else:
            sU, _ = v39._convert(state, "HU", R, s, t)
            todo = (("U", sU),)
        for k, s2 in todo:
            out2, _p = predict_fn(agent_input, s2, config, Random(rng_seed))
            res[k] = _correct(out2.prediction, revealed)
        out[s] = (st, res)
    return out


def install(path, *, agent_id="agent") -> None:
    """tools/v3_run.py の worker で、v310be（score_answers_role）のあと、--cf-value のあと、答えごとの記録・届け先の記録より前に入れる。"""
    import abm.loop as loop
    import v39
    import v310be
    ST.clear()
    ST.update(f=open(path, "w", encoding="utf-8"), pre=None, cf=None, rows=0, trials=0, checks=0, agent=agent_id,
              inner_predict=loop.predict)
    inner = loop.predict

    def predict(agent_input, state, config, rng):
        ST["pre"] = (agent_input, state, config)
        return inner(agent_input, state, config, rng)

    loop.predict = predict
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        ST["cf"] = None
        if coin.f_fired and ST.get("pre") is not None:
            R = output.trace.get("R_used")
            agent_input, pre, cfg = ST["pre"]
            if R is not None and R in pre.definitions:
                import probeworld as pw
                t0 = time.time()
                snap = pw._snapshot_modules()
                fp0 = _fp(pre)
                res = variants_correct(pre, agent_input, cfg, R, coin.t, revealed_edge, output.prediction, ST["inner_predict"],
                                       loop._rng_seed(ST["agent"], coin.t))
                pw._restore_modules(snap)
                if _fp(pre) != fp0:
                    raise RuntimeError(f"--cf-learn：測る前後で本物の状態の指紋が違う（試行 {coin.t}）")
                ST["checks"] += 1
                ST["cf"] = {"R": R, "t": coin.t, "res": res, "sec": time.time() - t0}
        ST["pre"] = None
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting
    real_score = v39.score_answers

    def score_answers(seats_in, ans, received, t):
        own_seats, own_scored = real_score(seats_in, ans, received, t)   # 今の採点（記録だけ。この旗では積まない）
        cf = ST.get("cf")
        if cf is None or cf["R"] != ans["R"] or cf["t"] != t:
            return seats_in, []
        L = v310be.CTX["L_score"]
        lp = v310be._ell(received.predicate, L)
        own = {x[0]: x for x in own_scored}
        items = {it["slot"]: it for it in ans["items"]}
        seats = dict(seats_in)
        scored = []
        for s, (st, ok) in sorted(cf["res"].items()):
            key = (ans["R"], s)
            rec = seats.get(key)
            it = items.get(s)
            applied = rec is not None and it is not None and rec.gen == it.get("gen") and rec.state == it.get("st") == st
            r = {k: (0.0 if v else lp) for k, v in ok.items()}
            inc = (r.get("F", 0.0) if st == "F" else 0.0, r.get("H", 0.0), r["U"], 1.0)
            if applied:
                seats[key] = v39.rec_add(rec, t, inc)
                scored.append([s, st, r.get("F") if st == "F" else None, r.get("H"), r["U"]])
            o = own.get(s)
            ST["f"].write(json.dumps({"trial": t, "R": ans["R"], "slot": s, "state": st, "applied": applied,
                                      "cf": {"F": r.get("F"), "H": r.get("H"), "U": r["U"]},
                                      "own": ({"F": o[2], "H": o[3], "U": o[4]} if o else None), "sec_trial": cf["sec"]},
                                     ensure_ascii=False) + "\n")
            ST["rows"] += 1
        ST["trials"] += 1
        return seats, scored

    v39.score_answers = score_answers


def close() -> dict:
    f = ST.get("f")
    if f is not None:
        f.close()
    return {"rows": ST.get("rows", 0), "trials": ST.get("trials", 0), "fingerprint_checks": ST.get("checks", 0)}
