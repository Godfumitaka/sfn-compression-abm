"""既存SME候補再生のあとで記憶の内訳を観測する。模型の部品は変更しない。"""
from collections import Counter
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import selcands_sme
import smereplay

REAL_INSTALL = smereplay.install


def memory_parts(state):
    # 旧版のsealmem.mem_partsと同じ式。型を復元し直さず本物の更新後の状態を読む。
    import v39
    lengths = v39.code_lengths(state.p_hat)
    parts = {"G": v39.global_table_bits(state.p_hat), "Idef": v39.I(len(state.definitions)),
             "S": 0, "seat2": 0, "Hc": 0, "Fc": 0, "defs": len(state.definitions)}
    counts = Counter()
    for d in state.definitions.values():
        parts["S"] += v39.structure_bits(d)
        for row in sorted(d.constituents, key=lambda x: x.slot_index):
            kind = v39.seat_state(d, row, state.slot_history)
            counts[kind] += 1
            parts["seat2"] += 2
            bits = v39.seat_content_bits(d, row, kind, state.slot_history, lengths)
            if kind in ("H", "F"):
                parts[kind + "c"] += bits
    parts["total"] = sum(parts[k] for k in ("G", "Idef", "S", "seat2", "Hc", "Fc"))
    parts.update({"n" + k: counts[k] for k in "FHU"})
    return parts


def install(path, *, replay=None):
    REAL_INSTALL(path, replay=replay)
    import abm.loop as loop
    import probeworld
    import smeshared
    stream = smeshared._text_gzip(Path(path).with_name(Path(path).name.replace(".sme.states.", ".sme.memory.")))
    record = loop._ledger_record

    def observe(agent_id, trial, config, output, score, coin, state, *a, **k):
        result = record(agent_id, trial, config, output, score, coin, state, *a, **k)
        before = smereplay.encode(state)
        snap = probeworld._snapshot_modules()
        extras = []
        for name in ("v39", "ustruct", "strictpc", "useforget"):
            mod = sys.modules.get(name)
            for attr in ("REG", "UREG", "RELPOS", "KINDS", "_POW", "STATS", "CTX"):
                val = getattr(mod, attr, None)
                if isinstance(val, dict):
                    extras.append((val, dict(val)))
        try:
            parts = memory_parts(state)
        finally:
            probeworld._restore_modules(snap)
            for current, saved in extras:
                current.clear();current.update(saved)
        assert smereplay.encode(state) == before, f"試行{trial.trial}：記憶量の観測で状態が変わった"
        stream.write(json.dumps({"trial": trial.trial, **parts, "graph_id": trial.G_star.graph_id,
            "full_entity_count": len(trial.G_star.entities),
            "public_entity_count": len(trial.target_graph_partial.entities)}, ensure_ascii=False) + "\n")
        return result

    loop._ledger_record = observe
    close = smereplay.close

    def finish():
        stream.close()
        return close()

    smereplay.close = finish


# spawnの子にも同じ観測を登録する。
smereplay.install = install

if __name__ == "__main__":
    selcands_sme.main()
