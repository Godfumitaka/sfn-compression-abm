"""種1〜5の全場面を旧版の飾りと全バイト照合する。模型は走らせない。"""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT.parents[1] / "codex_shop_deco_2026-10-04/source"
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
from abm.seed import load_seed
from abm.world import generate_trial, opaque_id
import shopworld as current


def encode(out, info):
    return json.dumps({"trial": out.trial, "motif": out.motif, "full": out.G_star.to_dict(),
        "public": out.target_graph_partial.to_dict(), "held": out.held_out_edge.to_dict(),
        "u_coins": out.u_coins, "research_info": info},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def main():
    dest = Path(sys.argv[1]);dest.mkdir(parents=True, exist_ok=True)
    for name in ("abm/world.py", "abm/seed.py", "abm/domains.py", "tools/shop/U-011_seed_shop.json"):
        assert (ROOT / name).read_bytes() == (OLD / name).read_bytes(), name
    spec = importlib.util.spec_from_file_location("legacy_shop_deco", OLD / "tools/shopworld.py")
    legacy = importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    seed = load_seed(ROOT / "tools/shop/U-011_seed_shop.json")
    hashes = {level: {"legacy": sha256(), "sme": sha256()} for level in current.DECO_LEVELS}
    counts = Counter();public = {};examples = []
    start = time.monotonic()
    for run_seed in range(1, 6):
        for trial in range(1740):
            base = generate_trial(run_seed, trial, ("agent",), seed=seed)
            cue = "e" if current.cue_rng(run_seed, trial).random() < 0.2 else "n"
            for world in (1, 2):
                core = None
                for level in current.DECO_LEVELS:
                    legacy.CFG.clear();legacy.CFG["deco"] = level
                    current.CFG.clear();current.CFG["deco"] = level
                    before, bi = legacy.build(base, run_seed, trial, cue=cue, world=world)
                    after, ai = current.build(base, run_seed, trial, cue=cue, world=world)
                    a, b = encode(before, bi), encode(after, ai)
                    assert a == b, (run_seed, trial, world, level)
                    for side, data in (("legacy", a), ("sme", b)):
                        hashes[level][side].update(data + b"\n")
                    relations = {r.relation_id: r for r in after.G_star.relations}
                    keys = (opaque_id(run_seed, trial, "relation:tree:0.0.0"),
                            opaque_id(run_seed, trial, "relation:shop:sig"),
                            opaque_id(run_seed, trial, "relation:shop:link"))
                    signature = tuple(relations[k] for k in keys), tuple(ai[k] for k in (
                        "shop_type", "shop_cue", "door_pred", "held_out_is_door"))
                    if core is None:core = signature
                    assert signature == core
                    assert after.G_star.entities == base.G_star.entities and after.u_coins == base.u_coins
                    di = ai.get("deco")
                    if di:
                        assert after.held_out_edge.relation_id not in {r["id"] for r in di["added"] + di["removed"]}
                    public.setdefault(f"w{world}_{level}", Counter())[len(after.target_graph_partial.entities)] += 1
                    counts[level] += 1
                    if run_seed == 1 and trial in (4, 5) and world == 2:
                        examples.append({"seed": run_seed, "trial": trial, "world": world, "level": level,
                            "full_relations": len(after.G_star.relations), "full_entities": len(after.G_star.entities),
                            "public_entities": len(after.target_graph_partial.entities), "info": ai,
                            "held": after.held_out_edge.to_dict()})
                legacy.IDS.clear();current.IDS.clear()
        print(f"種{run_seed}: 全1740試行×世界2×水準4を旧版と照合済み", flush=True)
    result = {"passed": True, "seeds": list(range(1, 6)), "trial_count": 1740,
        "counts": counts, "total_compared_scenes": sum(counts.values()),
        "full_scene_public_scene_holdout_coins_metadata_raw_bytes_equal": True,
        "hashes": {level: {side: h.hexdigest() for side, h in by.items()} for level, by in hashes.items()},
        "public_entity_distributions": public, "examples": examples,
        "elapsed_sec": time.monotonic() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (dest / "world_gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("examples", "public_entity_distributions")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":main()
