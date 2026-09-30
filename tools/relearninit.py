"""覚え直しの初期の評価（旗 --relearn-init）。2026-09-30 の委任書「U の照合の直し・覚え直しの初期の評価・支持の三分類」の 2。
★ abm/ は変えない。旗を切れば何もしない。

2 --relearn-init（--u-struct と --v310-be と一緒に使う）
  U の席が観察を受けて覚え直す（U→H、tools/v39.py reconcile）とき、その観察一回だけの新しい H（名前 1 回）の記録の初期値に、
  同じ観察を H で答えた場合（h_answer）と U で答えた場合（u_answer）の書換ビット（一致なら 0、違えば観察した名の ℓ）を入れる（誕生の初期の成績と同じ形）。
  ℓ・H・U の答えは、同じ時点の p̂ と同じ場面で出す。古い履歴や点数は復活させない（世代は reconcile のとおり新しい）。
  未来の予測の成功とは数えない：B の採点の累計（R_B）には足さず、side の kind＝"relearn_init" に別に書く。
  観察が一つでない（鍵の回数の和が 1 でない）覚え直しには初期値を入れず、数だけ記録する。
"""
from __future__ import annotations

import json

CFG: dict = {}
STATS: dict = {}
CTX: dict = {}


def install(fo) -> None:
    """tools/ustruct.py の install のあとに入れる。"""
    import abm.loop as loop
    import v39
    CFG.clear()
    STATS.clear()
    CTX.clear()
    STATS.update(relearn_init=0, relearn_init_multi_obs=0, relearn_init_rU_gt_rH=0)

    # 2 覚え直しの初期の評価：場面を控え、reconcile の覚え直しに初期値を入れる
    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        CTX["scene"] = target
        return real_m1(state, base, target, alignment, trial, **kw)

    loop.m1 = m1
    real_acc = loop._update_accounting

    def update_accounting(state, output, scene, config, horizon_, score, coin, revealed_edge):
        CTX["scene"] = scene
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = update_accounting
    real_rec = v39.reconcile

    def reconcile(state, trial, why):
        n0 = len(v39.CTX.get("relearn") or [])
        out = real_rec(state, trial, why)
        new = (v39.CTX.get("relearn") or [])[n0:]
        if new:
            out = _apply_init(out, trial, why, new, fo)
        return out

    v39.reconcile = reconcile


def _apply_init(state, t, why, events, fo):
    from dataclasses import replace
    import v39
    import v310be
    config = v39.CTX["config"]
    L = v39.code_lengths(state.p_hat)
    seats = dict(state.v39_seats)
    scene = CTX.get("scene")
    for ev in events:
        d = state.definitions[ev["R"]]
        row = next(r for r in d.constituents if r.slot_index == ev["slot"])
        h = {k: v for k, v in v39.hist_counts(state.slot_history.get((d.name, row.slot_index))).items() if v > 0}
        rec = {"kind": "relearn_init", "trial": t, "R": d.name, "slot": row.slot_index, "gen": ev["gen"], "by": why,
               "obs": sorted(h.items())}
        if sum(h.values()) != 1:
            STATS["relearn_init_multi_obs"] += 1
            rec["skipped"] = "観察が一つでない"
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            continue
        o = next(iter(h))
        ha = v39.h_answer(d, row, state.slot_history, state.p_hat, config.local_lambda, config.higher_order_predicates)[0]
        ua = v39.u_answer(d, row, scene, state.p_hat, config.higher_order_predicates)[0] if scene is not None else None
        lo = v310be._ell(o, L)
        rH = 0.0 if ha == o else lo
        rU = 0.0 if ua == o else lo
        col = lambda v: (float(v),) * 16  # noqa: E731
        key = (d.name, row.slot_index)
        seats[key] = replace(seats[key], init=(col(0.0), col(rH), col(rU), col(1.0)))
        STATS["relearn_init"] += 1
        STATS["relearn_init_rU_gt_rH"] += rU > rH
        rec.update(H=ha, U=ua, r_H=rH, r_U=rU)
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return replace(state, v39_seats=seats)
