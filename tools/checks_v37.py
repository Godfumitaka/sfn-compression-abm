"""v3.7 の決まりごとの検査（旗 --checks、2026-09-28、委任書「v3.7（② の罰をやめる）」の 2-3）。記録だけ。
模型の動きは変えない。台帳にも書かない（結果は走行の記録 manifest の "checks_v37" に出す）。

決まり 1：罰を受けた行の写し先が、伏せ辺そのもの（述語と引数の組が同じ）ではない。
決まり 2：当たりの試行に罰が付かない。
罰 ＝ その試行の charge_source の「①」「②」「①_穴埋め」「棄権」（と「①_その他」）。
写し先の求め方は、2026-09-28 朝の数える包み（diag2.py）と同じ：
  行の述語と、loop._mapped_arguments(行の関係, 写しの物, 写しの関係) の組（写しは output.trace の definition_alignment）。
  「①_穴埋め」は席の履歴を減らす罰で、罰の中身はその試行の発話（穴埋めの予測）そのものなので、発話の述語と引数の組を写し先とする。
install は、ほかのすべての差し替え（tools/v31.py の d32 を含む）のあとに呼び、loop._update_accounting の一番外側を包む。"""
from __future__ import annotations

STATS: dict = {}
_KEEP = 5


def install() -> None:
    import abm.loop as loop
    from abm.domains import EdgePrediction

    real = loop._update_accounting
    STATS.clear()
    STATS.update(trials=0, hit_trials=0, penalized_trials=0, penalized_rows=0, unresolved_rows=0,
                 rule1_violations=0, rule2_violations=0, by_kind={}, examples_rule1=[], examples_rule2=[])

    def wrapped(state, output, scene, config, horizon, score, coin, revealed_edge):
        next_state, acc = real(state, output, scene, config, horizon, score, coin, revealed_edge)
        STATS["trials"] += 1
        hit = bool(score.hit)
        STATS["hit_trials"] += hit
        sources = acc.get("charge_source") or {}
        hid = (revealed_edge.predicate, tuple(revealed_edge.arguments))
        al = output.trace.get("definition_alignment")
        pen = []
        for kind in ("①", "②"):
            for R, slot in sources.get(kind) or []:
                pen.append((kind, R, slot))
        for kind in ("①_穴埋め", "棄権"):
            for e in sources.get(kind) or []:
                pen.append((kind, e["R"], e["slot_index"]))
        other = list(sources.get("①_その他") or [])
        if pen or other:
            STATS["penalized_trials"] += 1
            if hit:
                STATS["rule2_violations"] += 1
                if len(STATS["examples_rule2"]) < _KEEP:
                    STATS["examples_rule2"].append({"R_used": output.trace.get("R_used"),
                                                    "penalties": [list(p) for p in pen], "other": other})
        for kind, R, slot in pen:
            STATS["penalized_rows"] += 1
            STATS["by_kind"][kind] = STATS["by_kind"].get(kind, 0) + 1
            target = None
            if kind == "①_穴埋め":
                p = output.prediction
                if isinstance(p, EdgePrediction):
                    target = (p.edge.predicate, tuple(p.edge.arguments))
            else:
                d = state.definitions.get(R)
                row = next((c for c in d.constituents if c.slot_index == slot and c.alive), None) if d is not None else None
                if row is not None and al is not None:
                    pos = loop._mapped_arguments(row.relation, al.entity_mapping, al.relation_mapping)
                    if pos is not None:
                        target = (row.relation.predicate, tuple(pos))
            if target is None:
                STATS["unresolved_rows"] += 1
            elif target == hid:
                STATS["rule1_violations"] += 1
                if len(STATS["examples_rule1"]) < _KEEP:
                    STATS["examples_rule1"].append({"kind": kind, "R": R, "slot_index": slot, "hit": hit})
        return next_state, acc

    loop._update_accounting = wrapped
