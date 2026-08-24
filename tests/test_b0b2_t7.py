"""SPEC B0+B2 §B.10 T7 の独立検算。"""

from __future__ import annotations

from collections import defaultdict

import pytest

from abm.domains import Entity, Relation, RelationGraph
from abm.sme import map_graphs


MOTIFS = {
    "M1": (("hold", ("a", "b")), ("push", ("b", "a")), ("require", ("core1", "core2"))),
    "M2": (("carry", ("a", "b")), ("lift", ("a", "b")), ("cause", ("core2", "core1"))),
    "M3": (("break", ("a", "b")), ("cut", ("a", "b")), ("cause", ("core2", "core1"))),
    "M4": (("push", ("a", "b")), ("turn", ("b", "c")), ("cause", ("core1", "core2"))),
}
LIVE_IDS = frozenset(("core1", "core2", "higher", "tower"))


def _graph(motif: str, *, definition: bool) -> RelationGraph:
    core1, core2, higher = MOTIFS[motif]
    entity_ids = ("a", "b", "c", "e") if motif == "M4" else ("a", "b", "e")
    mediator_predicate = "tombstone" if definition else "stone"
    relations = (
        Relation("core1", core1[0], core1[1]),
        Relation("core2", core2[0], core2[1]),
        Relation("higher", higher[0], higher[1]),
        # 墓石は relation ノードのまま残し、m_live からのみ除外する。
        Relation("mediator", mediator_predicate, ("a", "e")),
        Relation("tower", "allow", ("mediator", "core1")),
    )
    return RelationGraph(
        graph_id=f"{'definition' if definition else 'scene'}-{motif}",
        entities=tuple(Entity(entity_id) for entity_id in entity_ids),
        relations=relations,
    )


def _is_satisfied(
    relation_id: str,
    definition: RelationGraph,
    scene: RelationGraph,
    relation_mapping: dict[str, str],
) -> bool:
    mapped_id = relation_mapping.get(relation_id)
    if mapped_id is None:
        return False
    definition_predicates = {relation.relation_id: relation.predicate for relation in definition.relations}
    scene_predicates = {relation.relation_id: relation.predicate for relation in scene.relations}
    return definition_predicates[relation_id] == scene_predicates.get(mapped_id)


@pytest.mark.parametrize(
    ("motif", "expected_acceptance", "expected_oa", "expected_core"),
    (
        ("M1", 0.250, 0.000, 1.000),
        ("M2", 0.500, 0.500, 0.500),
        ("M3", 0.500, 0.500, 0.500),
        ("M4", 0.250, 0.000, 1.000),
    ),
)
def test_t7_reproduces_fixed_definition_alignment_table(
    motif: str,
    expected_acceptance: float,
    expected_oa: float,
    expected_core: float,
) -> None:
    definition = _graph(motif, definition=True)
    counts: defaultdict[str, int] = defaultdict(int)

    # 8,000 場面を4モチーフ均等に与える。この反復に世界生成の乱数は介入しない。
    for trial_index in range(8_000):
        scene_motif = tuple(MOTIFS)[trial_index % len(MOTIFS)]
        scene = _graph(scene_motif, definition=False)
        mapping = dict(map_graphs(definition, scene).alignment.relation_mapping)
        matched_live = len(LIVE_IDS.intersection(mapping))
        if matched_live / len(LIVE_IDS) < 0.67:
            continue

        counts["accepted"] += 1
        counts["overapplied"] += scene_motif != motif
        for relation_id in LIVE_IDS:
            counts[f"satisfied:{relation_id}"] += _is_satisfied(relation_id, definition, scene, mapping)

    acceptance = counts["accepted"] / 8_000
    assert acceptance == pytest.approx(expected_acceptance)
    assert counts["overapplied"] / counts["accepted"] == pytest.approx(expected_oa)
    assert counts["satisfied:core1"] / counts["accepted"] == pytest.approx(expected_core)
    assert counts["satisfied:core2"] / counts["accepted"] == pytest.approx(expected_core)
    assert counts["satisfied:higher"] / counts["accepted"] == pytest.approx(1.000)
    assert counts["satisfied:tower"] / counts["accepted"] == pytest.approx(1.000)
