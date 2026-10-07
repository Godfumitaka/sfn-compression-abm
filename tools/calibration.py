"""忘却停止の較正の記録。Vは本番の候補関数から取り、参照Hだけを仮に作る。"""
from __future__ import annotations

from collections import Counter
import json
import math

ST = {}


def value_row(candidate, *, reference=False):
    value, kind, name, slot, released, scores = candidate
    numerator = scores[1] - scores[0] if kind == "FH" else scores[2] - scores[1]
    if released <= 0 or not all(math.isfinite(x) for x in (value, released, numerator)):
        raise RuntimeError("較正候補の分母か値が未定義")
    if value != numerator / released:
        raise RuntimeError("較正候補の分子と分母が本番のVと違う")
    return dict(R=name, slot=slot, kind=kind, reference=reference,
                numerator=numerator, denominator=released, V=value,
                sign="positive" if value > 0 else "negative" if value < 0 else "zero")


def collect(state, trial, by_def, lengths):
    import probeworld
    import v39
    import v310be
    rows = [value_row(c) for pool in by_def.values() for c in pool]
    # 本番の候補関数が除いた席も、分母と理由を残す。
    excluded = [dict(R=r, slot=s, kind=k, denominator=dc, reason="nonpositive_release", reference=False)
                for r, s, k, dc in v310be.CTX.get("zero_release", ())]
    snap = probeworld._snapshot_modules()
    try:
        for name, definition in state.definitions.items():
            for row in definition.constituents:
                if v39.seat_state(definition, row, state.slot_history) != "F":
                    continue
                probeworld._restore_modules(snap)
                shadow, _ = v39._convert(state, "FH", name, row.slot_index, trial)
                # 仮のHの履歴は実際の履歴のまま。失われたF名を研究者が補わない。
                start = len(v310be.CTX.get("zero_release", ()))
                pool = v39._candidates(shadow, shadow.definitions[name], trial, lengths, len(shadow.definitions))
                match = next((c for c in pool if c[1] == "HU" and c[3] == row.slot_index), None)
                if match is not None:
                    rows.append(value_row(match, reference=True))
                else:
                    reason = next((dict(R=r, slot=s, kind=k, denominator=dc,
                                        reason="nonpositive_release", reference=True)
                                   for r, s, k, dc in v310be.CTX.get("zero_release", ())[start:]
                                   if s == row.slot_index and k == "HU"), None)
                    if reason is None:
                        raise RuntimeError("Fの参照H→Uの必要な分母が記録されていない")
                    excluded.append(reason)
    finally:
        probeworld._restore_modules(snap)
    record = dict(trial=trial, world=ST["world"], seed=ST["seed"], candidates=rows,
                  excluded=excluded, excluded_counts=dict(Counter(x["reason"] for x in excluded)))
    ST["f"].write(json.dumps(record, ensure_ascii=False) + "\n")
    ST["trials"] += 1


def install(path, *, world, seed):
    import smeshared
    import v39
    ST.clear()
    ST.update(f=smeshared._text_gzip(path), world=world, seed=seed, trials=0)
    v39.CFG["no_forget_exec"] = True


def close():
    ST["f"].close()
    return {"trials": ST["trials"]}
