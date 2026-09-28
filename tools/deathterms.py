"""v3.7（2026-09-28、委任書「v3.7（② の罰をやめる）」の 3）：旗 --death-terms。死んだ行の V の項を side に書く。
記録だけ（模型の動きは変えない。台帳 ledgers/ には何も書かない）。

β＝0 では abm/deletion.py の deletion_event に V しか書かれない（V の項は β≠0 のときだけ）。そこで、loop.apply_theta の一番外側を包み、
返った deletion_event（kind＝deletion）ごとに、削除の直前の状態（apply_theta に渡された state）から、abm/deletion.py の apply_theta と
同じ入力で abm.accounting.constituent_value_terms をもう一度呼び、項を求める（純粋な関数なので、同じ入力なら同じ値）。
求めた V が event の V と一致しない数を STATS["v_mismatch"] に数える（0 のはず）。
V ＝ P·a ＋ w·(embed/ℓ)（β＝0）。P ＝ 参加率（abm.accounting.participation）、a ＝ (節約 − 適用あたりの例外費用)/ℓ。
side の行：{"kind": "death_terms", "trial": t, "rows": [{R, slot_index, registered_at, V, P, a, participation_term, embed_term, beta_term,
  saving, ell, exc_per_apply, lifetime}]}（その試行に削除があったときだけ）。"""
from __future__ import annotations

import json

STATS: dict = {"trials_with_deaths": 0, "deaths": 0, "v_mismatch": 0}


def install(fo) -> None:
    import abm.deletion as dl
    import abm.loop as loop
    from abm.accounting import constituent_value_terms, decay_ladder, participation
    from abm.definition import ExceptionAccumulator

    real = loop.apply_theta
    STATS.update(trials_with_deaths=0, deaths=0, v_mismatch=0)

    def wrapped(state, config, trial, *args, **kw):
        after, events = real(state, config, trial, *args, **kw)
        dels = [e for e in events if e.get("kind") == "deletion"]
        if dels:
            embed = dl._embed_immediately_before_deletion(state)
            horizon = kw.get("horizon")
            decay = decay_ladder(horizon) if config.beta else None
            rows = []
            for e in dels:
                R, slot, reg = e["R"], e["slot_index"], e["registered_at"]
                row = next(c for c in state.definitions[R].constituents
                           if c.slot_index == slot and c.registered_at == reg)
                acc = state.merit[(R, slot, reg)]
                exc = state.exceptions.get((R, slot), ExceptionAccumulator((0.0,) * 16, 0.0, 0))
                terms = constituent_value_terms(row.frozen_price, acc, exc, embed[(R, slot, reg)],
                                                w=config.w, kappa=config.kappa, beta=config.beta,
                                                decay=decay, elapsed=trial - reg)
                den = sum(acc.basis)
                per = sum(exc.basis) / den if den > 0.0 else 0.0
                price = row.frozen_price
                rows.append({"R": R, "slot_index": slot, "registered_at": reg, "V": e["V"],
                             "P": participation(acc), "a": (price.saving - per) / price.ell_frozen,
                             "participation_term": terms.participation_term, "embed_term": terms.embed_term,
                             "beta_term": terms.beta_term, "saving": price.saving, "ell": price.ell_frozen,
                             "exc_per_apply": per, "lifetime": trial - reg})
                if terms.total != e["V"]:
                    STATS["v_mismatch"] += 1
            STATS["trials_with_deaths"] += 1
            STATS["deaths"] += len(rows)
            fo.write(json.dumps({"kind": "death_terms", "trial": trial, "rows": rows}, ensure_ascii=False) + "\n")
        return after, events

    loop.apply_theta = wrapped
