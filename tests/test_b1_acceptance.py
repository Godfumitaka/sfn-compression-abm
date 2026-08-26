"""SPEC B1 §C.9 の中核受け入れ試験。"""

from __future__ import annotations

from collections import defaultdict
from random import Random

import pytest

from abm.abstraction import m1
from abm.accounting import participation, update_frequency
from abm.domains import AgentState, EdgePrediction, Entity, Relation, RelationGraph
from abm.ledger import ARM_DESCRIPTOR_FIELDS, LEDGER_FIELDS
from abm.sme import map_graphs, project


MOTIFS = {
    "M1": (("hold", ("a", "b")), ("push", ("b", "a")), ("require", ("core1", "core2"))),
    "M2": (("carry", ("a", "b")), ("lift", ("a", "b")), ("cause", ("core2", "core1"))),
    "M3": (("break", ("a", "b")), ("cut", ("a", "b")), ("cause", ("core2", "core1"))),
    "M4": (("push", ("a", "b")), ("turn", ("b", "c")), ("cause", ("core1", "core2"))),
}
LIVE_IDS = frozenset(("core1", "core2", "higher", "tower"))
PI_A = {"M1": 0.060701, "M2": 0.081710, "M3": 0.130073, "M4": 0.265404}
PERIPHERAL = {"M1": "carry", "M2": "cold", "M3": "carry", "M4": "hard"}
GLUE = ("near", "above", "below", "beside", "behind", "inside")


def _graph(motif: str, *, definition: bool) -> RelationGraph:
    core1, core2, higher = MOTIFS[motif]
    entity_ids = ("a", "b", "c", "e") if motif == "M4" else ("a", "b", "e")
    return RelationGraph(
        graph_id=f"{'definition' if definition else 'scene'}-{motif}",
        entities=tuple(Entity(entity_id) for entity_id in entity_ids),
        relations=(
            Relation("core1", core1[0], core1[1]),
            Relation("core2", core2[0], core2[1]),
            Relation("higher", higher[0], higher[1]),
            Relation("mediator", "tombstone" if definition else "stone", ("a", "e")),
            Relation("tower", "allow", ("mediator", "core1")),
        ),
    )


def _with_holdout(motif: str, rng: Random) -> RelationGraph:
    scene = _graph(motif, definition=False)
    entities = list(scene.entities)
    relations = list(scene.relations)
    candidates = ["core1", "core2", "mediator"]
    if rng.random() < PI_A[motif]:
        entities.append(Entity("peripheral_entity"))
        relations.append(Relation("peripheral", PERIPHERAL[motif], ("a", "peripheral_entity")))
        candidates.append("peripheral")
    for index in range(rng.randint(1, 3)):
        left, right = rng.sample([entity.entity_id for entity in entities], 2)
        relations.append(Relation(f"glue{index}", GLUE[index], (left, right)))
        candidates.append(f"glue{index}")
    held_out = rng.choice(candidates)
    return RelationGraph(
        graph_id=scene.graph_id,
        entities=tuple(entities),
        relations=tuple(relation for relation in relations if relation.relation_id != held_out),
    )


@pytest.fixture(scope="module")
def prediction_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, defaultdict[str, int]] = {
        motif: defaultdict(int) for motif in MOTIFS
    }
    for definition_motif in MOTIFS:
        definition = _graph(definition_motif, definition=True)
        rng = Random(2)
        for trial in range(8_000):
            scene_motif = tuple(MOTIFS)[trial % 4]
            partial = _with_holdout(scene_motif, rng)
            mapping = map_graphs(definition, partial).alignment
            support = len(LIVE_IDS.intersection(mapping.relation_mapping))
            if support / 4 < 0.67:
                continue
            counts[definition_motif]["applications"] += 1
            prediction = project(mapping, definition, partial)
            if not isinstance(prediction, EdgePrediction):
                continue
            counts[definition_motif][f"prediction:{scene_motif}"] += 1
    return {motif: dict(values) for motif, values in counts.items()}


def test_1_11_ledger_has_85_unique_fields() -> None:
    assert len(LEDGER_FIELDS) == len(set(LEDGER_FIELDS)) == 85


def test_1_12_run_header_has_12_arm_descriptors() -> None:
    assert len(ARM_DESCRIPTOR_FIELDS) == len(set(ARM_DESCRIPTOR_FIELDS)) == 12


def test_2_7_mediator_initial_participation_is_at_least_half() -> None:
    base = _graph("M2", definition=True)
    target = _graph("M2", definition=False)
    p_hat = update_frequency(AgentState().p_hat, target.relations)
    state, event = m1(
        AgentState(p_hat=p_hat),
        base,
        target,
        map_graphs(base, target).alignment,
        trial=1,
        name="R",
    )
    assert event is not None
    mediator = next(row for row in state.definitions["R"].constituents if row.relation.relation_id == "mediator")
    assert participation(state.merit[("R", mediator.slot_index)]) >= 0.5


@pytest.mark.parametrize(
    ("motif", "expected"),
    (("M1", 0.406), ("M2", 0.414), ("M3", 0.384), ("M4", 0.184)),
)
def test_3_8_m4_live_holdout_prediction_rate(
    prediction_counts: dict[str, dict[str, int]], motif: str, expected: float
) -> None:
    actual = prediction_counts[motif].get(f"prediction:{motif}", 0) / 2_000
    assert actual == pytest.approx(expected, abs=0.02)


@pytest.mark.parametrize(
    ("definition_motif", "target_motif", "expected"),
    (("M2", "M3", 0.384), ("M3", "M2", 0.414)),
)
def test_3_9_overapplication_prediction_rate(
    prediction_counts: dict[str, dict[str, int]],
    definition_motif: str,
    target_motif: str,
    expected: float,
) -> None:
    actual = prediction_counts[definition_motif].get(f"prediction:{target_motif}", 0) / 2_000
    assert actual == pytest.approx(expected, abs=0.02)


@pytest.mark.parametrize(
    ("motif", "expected"),
    (("M1", 0.000), ("M2", 0.210), ("M3", 0.216), ("M4", 0.000)),
)
def test_4_2_type1_rate_at_full_feedback(
    prediction_counts: dict[str, dict[str, int]], motif: str, expected: float
) -> None:
    overapplication_target = {"M2": "M3", "M3": "M2"}.get(motif)
    failures = prediction_counts[motif].get(f"prediction:{overapplication_target}", 0)
    actual = failures / prediction_counts[motif]["applications"]
    assert actual == pytest.approx(expected, abs=0.02)
