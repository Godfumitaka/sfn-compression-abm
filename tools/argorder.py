"""--score-arg-order：A の書換採点に、対応後の引数の順を含める。

採点する席の選び方は --score-role のまま。誕生は登録に渡された対応、
覚え直しは観察を届けた対応を使う。採点のための照合は呼ばない。
"""
from __future__ import annotations

CTX: dict = {}


def correct(name, position, observed):
    return (observed is not None and position is not None and name == observed.predicate
            and tuple(position) == tuple(observed.arguments))


def birth_observations(row, base, target):
    from abm.filling import _mapped_arguments
    b = next((r for r in base.relations if r.relation_id == row.relation.relation_id), None)
    al = CTX.get("birth_alignment")
    if b is None or al is None:
        raise RuntimeError("順つきの誕生採点：登録材料の対応が無い")
    cid = al.relation_mapping.get(b.relation_id)
    o = next((r for r in target.relations if r.relation_id == cid), None)
    if o is None:
        raise RuntimeError("順つきの誕生採点：観察した材料の行が無い")
    current_pos = _mapped_arguments(row.relation, al.entity_mapping, al.relation_mapping)
    return (b, row.relation.arguments), (o, current_pos)


def relearn_observation(R, slot, why):
    if why == "会計":
        import v39
        ans = v39.CTX.get("answers") or {}
        if ans.get("R") == R:
            it = next((x for x in ans.get("items", ()) if x["slot"] == slot), None)
            if it is not None:
                return CTX.get("received"), it.get("pos")
        raise RuntimeError("順つきの覚え直し採点：予測時の席の対応が無い")
    import histrole
    items = histrole.CTX.get("observations", {}).get((R, slot), ())
    if len(items) != 1:
        raise RuntimeError("順つきの覚え直し採点：一回の観察とその対応を控えられない")
    return items[0]


def install():
    import abm.loop as loop
    import v310be
    import histrole
    import probeworld
    v310be.CFG["score_arg_order"] = True
    v310be.STATS["cfg"]["score_arg_order"] = True
    histrole.CFG["ordered_observations"] = True
    CTX.clear()
    histrole.CTX.clear()
    if "argorder" not in probeworld.SNAP_MODULES:
        probeworld.SNAP_MODULES += ("argorder",)
    inner_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        CTX["birth_alignment"] = alignment
        return inner_m1(state, base, target, alignment, trial, **kw)

    loop.m1 = m1
    inner_acc = loop._update_accounting

    def accounting(state, output, scene, config, horizon, score, coin, revealed_edge):
        CTX["received"] = revealed_edge if coin.f_fired else None
        return inner_acc(state, output, scene, config, horizon, score, coin, revealed_edge)

    loop._update_accounting = accounting
