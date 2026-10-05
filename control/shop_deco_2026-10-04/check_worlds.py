"""段3：種1〜20の生成だけを照合する。予測・採点・学習は呼ばない。"""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import gzip
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from abm.seed import load_seed
from abm.world import generate_trial, opaque_id
import shopworld as sw


def main():
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    seed = load_seed(ROOT / "tools/shop/U-011_seed_shop.json")
    levels = sw.DECO_LEVELS
    hashes = {level: sha256() for level in levels}
    counts = Counter()
    examples = {}
    distributions = {str(world): {level: Counter() for level in levels} for world in (1, 2)}
    first_five = {str(world): {level: Counter() for level in levels} for world in (1, 2)}
    entity_log = gzip.open(dest / "world_entities.jsonl.gz", "wt", encoding="utf-8")
    start = time.monotonic()
    for run_seed in range(1, 21):
        for trial in range(1740):
            base = generate_trial(run_seed, trial, ("agent",), seed=seed)
            cue = "e" if sw.cue_rng(run_seed, trial).random() < 0.2 else "n"
            door = opaque_id(run_seed, trial, "relation:tree:0.0.0")
            sig = opaque_id(run_seed, trial, "relation:shop:sig")
            link = opaque_id(run_seed, trial, "relation:shop:link")
            glue = {opaque_id(run_seed, trial, f"relation:glue:{i}") for i in range(3)}
            for world in (1, 2):
                sw.CFG.clear()
                current, ci = sw.build(base, run_seed, trial, cue=cue, world=world)
                before = {r.relation_id: r for r in current.G_star.relations}
                for level in levels:
                    sw.CFG["deco"] = level
                    out, info = sw.build(base, run_seed, trial, cue=cue, world=world)
                    after = {r.relation_id: r for r in out.G_star.relations}
                    assert all(before[rid] == after[rid] for rid in (door, sig, link))
                    assert out.G_star.entities == current.G_star.entities
                    assert out.u_coins == current.u_coins
                    assert (out.held_out_edge.relation_id == door) == (current.held_out_edge.relation_id == door)
                    assert all(info[key] == ci[key] for key in ("shop_type", "shop_cue", "door_pred", "held_out_is_door"))
                    if level == "current":
                        assert out == current and info == ci
                        added, removed = [], []
                    else:
                        di = info["deco"]
                        added, removed = di["added"], di["removed"]
                        assert out.held_out_edge.relation_id not in {r["id"] for r in added + removed}
                        assert di["original_held_out"] == sw._relation_record(current.held_out_edge)
                        assert di["held_out"] == sw._relation_record(out.held_out_edge)
                        if level == "skeleton":
                            assert not added
                            assert {r["id"] for r in removed} == (set(before) & glue)
                            assert out.G_star.relations == tuple(r for r in current.G_star.relations if r.relation_id not in glue)
                            if current.held_out_edge.relation_id in glue:
                                entities = {e.entity_id for e in out.G_star.entities}
                                excluded = {door, sig, opaque_id(run_seed, trial, "relation:role_unary")}
                                candidates = [r for r in out.G_star.relations if r.relation_id not in excluded
                                              and all(a in entities for a in r.arguments)]
                                assert out.held_out_edge in candidates and len(candidates) in (8, 9)
                                counts["rerouted"] += 1
                            else:
                                assert out.held_out_edge == current.held_out_edge
                        else:
                            n = 4 if level == "plus4" else 8
                            assert not removed and len(added) == n
                            assert out.held_out_edge == current.held_out_edge
                            assert out.G_star.relations[:-n] == current.G_star.relations
                            assert len({r["predicate"] for r in added}) == n
                            assert all(r["predicate"] in sw.DECO_PREDICATES and len(r["arguments"]) == 1 for r in added)
                    row = {"seed": run_seed, "trial": trial, "world": world, "cue": cue,
                           "door": sw._relation_record(after[door]), "sig": sw._relation_record(after[sig]),
                           "link": sw._relation_record(after[link]), "door_day": out.held_out_edge.relation_id == door}
                    hashes[level].update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
                    counts[level] += 1
                    public_n = len(out.target_graph_partial.entities)
                    entity_log.write(json.dumps({"seed": run_seed, "trial": trial, "world": world, "level": level,
                        "full_entity_count": len(out.G_star.entities), "public_entity_count": public_n}) + "\n")
                    distributions[str(world)][level][public_n] += 1
                    if run_seed <= 5:
                        first_five[str(world)][level][public_n] += 1
                    if level == "skeleton" and out.target_graph_partial.entities != current.target_graph_partial.entities:
                        counts["partial_entity_sets_differ"] += 1
                    # 小例は元のつなぎ伏せ・仲立ち伏せ・ドア伏せを含めて各1つ。
                    held = current.held_out_edge.relation_id
                    kind = "door" if held == door else ("glue" if held in glue else
                            ("mediator" if held == opaque_id(run_seed, trial, "relation:mediator") else "other"))
                    key = (world, kind, level)
                    if run_seed == 1 and key not in examples:
                        examples[key] = {"seed": run_seed, "trial": trial, "world": world, "level": level,
                                         "original_held_out": sw._relation_record(current.held_out_edge),
                                         "held_out": sw._relation_record(out.held_out_edge),
                                         "added": added, "removed": removed,
                                         "relations": [sw._relation_record(r) for r in out.G_star.relations],
                                         "entities": [e.entity_id for e in out.G_star.entities],
                                         "visible_entities": [e.entity_id for e in out.target_graph_partial.entities]}
                sw.IDS.clear()
        print(f"種{run_seed}: 1,740試行×世界2×水準4を照合済み", flush=True)
    entity_log.close()
    signatures = {level: h.hexdigest() for level, h in hashes.items()}
    assert len(set(signatures.values())) == 1
    result = {"passed": True, "seeds": list(range(1, 21)), "trial_count": 1740,
              "counts": dict(counts), "invariant_sha256": signatures,
              "elapsed_sec": time.monotonic() - start,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "public_entity_distribution_seeds_1_20": distributions,
              "public_entity_distribution_seeds_1_5": first_five,
              "examples": [examples[k] for k in sorted(examples)]}
    (dest / "world_gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "examples"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
