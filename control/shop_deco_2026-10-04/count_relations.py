"""段1の関係数を再現する読み取り用の道具。模型の走行・採点・学習は呼ばない。"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import ceil, fsum, log2
from pathlib import Path
import json
import resource
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BASE = "3380344add7f85ce2c3608656de5805995dcf971"
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from abm.seed import load_seed
from abm.world import _expand_motif, generate_trial, opaque_id
from shopworld import NEW_PREDICATES, build, cue_rng, door_pred


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main() -> None:
    files = ("abm/world.py", "abm/seed.py", "tools/shopworld.py", "tools/shop/U-011_seed_shop.json")
    provenance = {}
    for name in files:
        expected = git("rev-parse", f"{BASE}:{name}")
        actual = git("hash-object", name)
        if actual != expected:
            raise ValueError(f"指定点とファイルが不一致: {name}")
        provenance[name] = {"git_blob": actual, "sha256": sha256((ROOT / name).read_bytes()).hexdigest()}
    seed = load_seed(ROOT / "tools/shop/U-011_seed_shop.json")
    skeleton = {}
    for motif in seed.data["motif_structure"]:
        nodes = _expand_motif(seed.data, motif)
        skeleton[motif] = {
            "by_level": dict(sorted(Counter(node[0] for _, node in nodes).items())),
            "paths": [{"path": node[1], "predicate": node[2]} for _, node in nodes],
        }
    roles_order = ("tree_other", "door", "role_unary", "sig", "link", "mediator", "peripheral", "glue")
    examples = {}
    for trial in range(512):
        base = generate_trial(1, trial, ("agent",), seed=seed)
        nodes = _expand_motif(seed.data, base.motif)
        roles = {opaque_id(1, trial, f"relation:tree:{node[1]}"):
                 ("door" if node[1] == "0.0.0" else "tree_other") for _, node in nodes}
        for name in ("mediator", "role_unary", "peripheral"):
            roles[opaque_id(1, trial, f"relation:{name}")] = name
        for index in range(3):
            roles[opaque_id(1, trial, f"relation:glue:{index}")] = "glue"
        roles[opaque_id(1, trial, "relation:shop:sig")] = "sig"
        roles[opaque_id(1, trial, "relation:shop:link")] = "link"
        cue = "e" if cue_rng(1, trial).random() < 0.2 else "n"
        tr, info = build(base, 1, trial, cue=cue, world=2)
        counts = Counter(roles[relation.relation_id] for relation in tr.G_star.relations)
        if len(tr.G_star.relations) != 18 + 1 + counts["peripheral"] + counts["glue"]:
            raise ValueError("関係数の内訳が不一致")
        if len(tr.target_graph_partial.relations) != len(tr.G_star.relations) - 1:
            raise ValueError("可視関係数が不一致")
        key = (counts["peripheral"], counts["glue"])
        if key not in examples:
            examples[key] = {
                "seed": 1, "trial_index_zero_based": trial, "shop_type": info["shop_type"],
                "cue": cue, "world": 2, "counts": {role: counts[role] for role in roles_order},
                "total": len(tr.G_star.relations), "visible": len(tr.target_graph_partial.relations),
                "visible_entities": len(tr.target_graph_partial.entities),
                "held_role": roles[tr.held_out_edge.relation_id],
                "additional_relations": [{"role": roles[r.relation_id], "predicate": r.predicate}
                                         for r in tr.G_star.relations
                                         if roles[r.relation_id] in ("mediator", "peripheral", "glue")],
            }
        if len(examples) == 6:
            break
    if len(examples) != 6:
        raise ValueError("周縁の有無×つなぎ本数の6通りを確認できない")
    probability = float(seed.data["pi_A"]["M1"])
    dictionary = dict.fromkeys(seed.data["marginal"])
    for predicate in NEW_PREDICATES:
        dictionary.setdefault(predicate)
    result = {
        "scope": "段1の生成だけ。走行・予測・採点・学習・分類は未実施。",
        "base_commit": BASE, "source_files": provenance,
        "run_seeds_used": [1], "generated_trial_count": trial + 1,
        "run_seed_21_to_40_accessed": False, "skeleton": skeleton,
        "examples": [examples[key] for key in sorted(examples)],
        "mediator_bags": {motif: [p for p, motifs in seed.data["bags"].items() if motif in motifs]
                          for motif in seed.data["motif_structure"]},
        "peripheral_predicates": {motif: row["peripheral"] for motif, row in seed.data["motif_structure"].items()},
        "role_unary": dict(seed.data["role_unary"]),
        "door_table": [{"world": world, "type": typ, "cue": cue, "predicate": door_pred(world, typ, cue)}
                       for world in (1, 2) for typ in ("甲", "乙") for cue in ("n", "e")],
        "design_expectations_not_run_results": {
            "additional_relation_count_mean": 1 + probability + 2,
            "current_door_holdout_rate": fsum((1 - probability) / (9 + glue) + probability / (10 + glue)
                                             for glue in (1, 2, 3)) / 3,
            "naive_skeleton_door_holdout_rate": 1 / 8,
        },
        "dictionary": {"current_size": len(dictionary), "proposed_plus_size": len(dictionary) + 12,
                       "current_bits_per_word": ceil(log2(len(dictionary))),
                       "proposed_plus_bits_per_word": ceil(log2(len(dictionary) + 12))},
        "peak_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
