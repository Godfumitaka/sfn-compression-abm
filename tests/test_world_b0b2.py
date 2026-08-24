from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, pstdev

import pytest

from abm.seed import load_seed
from abm.world import MOTIF_ROWS, generate_world, one_minus_h, opaque_id


def test_one_minus_h_matches_all_seed_values() -> None:
    seed = load_seed()

    for motif in MOTIF_ROWS:
        assert abs(one_minus_h(float(seed.data["pi_A"][motif])) - float(seed.data["one_minus_h"][motif])) <= 1e-6


def test_world_is_deterministic_and_sweep_independent() -> None:
    first = generate_world("run-7", 64, ("agent-b", "agent-a"))
    second = generate_world("run-7", 64, ("agent-a", "agent-b"))

    assert first.world_hash == second.world_hash
    assert first.trials == second.trials


def test_motifs_are_randomized_within_balanced_blocks() -> None:
    world = generate_world("motif-blocks", 8_000, ("agent",))
    motifs = [trial.motif for trial in world.trials]

    assert Counter(motifs) == {motif: 2_000 for motif in MOTIF_ROWS}
    for start in range(0, len(motifs), len(MOTIF_ROWS)):
        assert set(motifs[start : start + len(MOTIF_ROWS)]) == set(MOTIF_ROWS)

    positions: defaultdict[str, list[int]] = defaultdict(list)
    for index, motif in enumerate(motifs):
        positions[motif].append(index)
    intervals = [
        right - left
        for motif_positions in positions.values()
        for left, right in zip(motif_positions, motif_positions[1:])
    ]
    assert min(intervals) >= 1
    assert max(intervals) <= 7
    assert mean(intervals) == pytest.approx(4.0, abs=0.05)
    assert pstdev(intervals) > 0.0


def test_world_hash_depends_on_run_seed_and_repeats_for_same_seed() -> None:
    first = generate_world("hash-seed-a", 128, ("agent",))
    repeated = generate_world("hash-seed-a", 128, ("agent",))
    different = generate_world("hash-seed-b", 128, ("agent",))

    assert first.world_hash == repeated.world_hash
    assert first.world_hash != different.world_hash


def test_scene_contract_holdout_and_opaque_ids() -> None:
    world = generate_world("run-8", 80, ("agent",))
    glue_counts = set()

    for trial in world.trials:
        full_ids = {relation.relation_id for relation in trial.G_star.relations}
        visible_ids = {relation.relation_id for relation in trial.target_graph_partial.relations}
        assert full_ids - visible_ids == {trial.held_out_edge.relation_id}
        assert trial.held_out_edge.predicate not in {"allow", str(load_seed().data["role_unary"][trial.motif])}
        assert all(len(entity.entity_id) == 16 for entity in trial.G_star.entities)
        glue_counts.add(sum(relation.predicate in load_seed().data["glue"] for relation in trial.G_star.relations))

    assert glue_counts == {1, 2, 3}


def test_id_relabeling_preserves_scene_structure() -> None:
    trial = generate_world("run-9", 1, ("agent",)).trials[0]
    all_ids = [entity.entity_id for entity in trial.G_star.entities] + [
        relation.relation_id for relation in trial.G_star.relations
    ]
    relabel = {value: opaque_id("replacement", 0, str(index)) for index, value in enumerate(all_ids)}

    original = [
        (relation.predicate, tuple("R" if arg in {r.relation_id for r in trial.G_star.relations} else "E" for arg in relation.arguments))
        for relation in trial.G_star.relations
    ]
    replaced = [
        (relation.predicate, tuple("R" if relabel[arg] in {relabel[r.relation_id] for r in trial.G_star.relations} else "E" for arg in relation.arguments))
        for relation in trial.G_star.relations
    ]
    assert replaced == original
