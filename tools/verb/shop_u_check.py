"""お店のUの小例。既存u_answerをそのまま呼ぶ。学習・予測走行はしない。"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "tools"), str(REPO)]


def main():
    import abm.world as w
    import probeworld as pw
    import shopworld as sw
    import v39
    from abm.abstraction import _structural_relation_ids
    from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition
    from abm.domains import RelationGraph
    from abm.filling import _predicate_has_signature, slot_signature
    from abm.seed import higher_order_predicates, load_seed
    seed = load_seed(REPO / "tools/shop/U-011_seed_shop.json")
    hop = higher_order_predicates(seed) | {"attach"}
    examples = {}
    t = 0
    while len(examples) < 2:
        trial = w.generate_trial(1, t, ("agent",), seed=seed, holdout_include_second_order=False)
        examples.setdefault(trial.motif, (t, trial))
        t += 1
        if t > 100:
            raise RuntimeError("二つの型の小例を作れない")
    result = {"seed": 1, "world_generation_trials_examined": t,
              "description": "固定した甲/乙の小例、完全入力で作る検査用頻度表。甲:乙=1:1、通常:例外=4:1。学習台帳のp_hatではない。", "cases": []}
    old = dict(v39.CFG)
    try:
        v39.CFG["u_abstain"] = False
        for world in (1, 2):
            scenes = []
            for motif in ("M1", "M2"):
                tau, base = examples[motif]
                for cue, weight in (("n", 4), ("e", 1)):
                    tr, info = sw.build(base, 1, tau, cue=cue, world=world)
                    scenes.append({"trial": tr, "info": info, "weight": weight, "t": tau})
            for corpus, included in (("甲と乙", scenes), ("甲のみ", scenes[:2]), ("乙のみ", scenes[2:])):
                counts = Counter()
                for sample in included:
                    for rel in sample["trial"].G_star.relations:
                        counts[rel.predicate] += sample["weight"]
                table = FrequencyTable(dict(counts), sum(counts.values()), .1, frozenset(counts))
                for sample in included:
                    tr, info = sample["trial"], sample["info"]
                    ids = _structural_relation_ids(tr.G_star)
                    rels = [r for r in tr.G_star.relations if r.relation_id in ids]
                    price = FrozenPrice(1.0, 0, 0.0, 3)
                    rows = tuple(Constituent(i, 0, replace(r, predicate=v39.ERASED) if r.relation_id == info["door_id"] else r,
                                             price, r.relation_id != info["door_id"]) for i, r in enumerate(rels))
                    d = NamedDefinition("R_shop_inspection", rows, len(rows)-1, 0)
                    row = next(r for r in rows if r.relation.relation_id == info["door_id"])
                    if v39.seat_state(d, row, {}) != "U":
                        raise RuntimeError("ドアの席がUでない")
                    scene = pw._partial(tr.G_star, info["door_id"])
                    dg = RelationGraph("definition", relations=tuple(c.relation for c in rows))
                    sig = slot_signature(row.relation, dg)
                    pool = v39._order_pool(frozenset(p for p in table.alive_vocab if _predicate_has_signature(p, sig, scene, dg)), d, row, hop)
                    answer, reason = v39.u_answer(d, row, scene, table, hop)
                    maximum = max(table.prob(p) for p in pool)
                    top = sorted(p for p in pool if table.prob(p) == maximum)
                    result["cases"].append({"world": world, "corpus": corpus, "shop_type": info["shop_type"], "cue": info["shop_cue"],
                                            "door_truth": sw.door_pred(world, info["shop_type"], info["shop_cue"]), "door_path": "0.0.0",
                                            "signature": sig, "state": "U", "answer": answer, "reason": reason,
                                            "max_names": top, "max_count": counts[top[0]],
                                            "skeleton_counts": {p: counts[p] for p in ("push", "carry", "lift", "steer", "reach")},
                                            "hold_count": counts["hold"], "hold_b_count": counts["hold_b"],
                                            "pool": [{"predicate": p, "count": counts[p], "prob": table.prob(p)} for p in sorted(pool)]})
    finally:
        v39.CFG.clear()
        v39.CFG.update(old)
    path = Path(sys.argv[1])
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    for case in result["cases"]:
        print(json.dumps({k: case[k] for k in ("world", "corpus", "shop_type", "cue", "door_truth", "answer", "reason", "max_names", "max_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
