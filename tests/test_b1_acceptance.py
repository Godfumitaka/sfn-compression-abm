"""SPEC B1 §C.9 の中核受け入れ試験。"""

from __future__ import annotations

from collections import defaultdict
from random import Random

import pytest

from abm.abstraction import m1
from abm.accounting import participation, update_frequency
from abm.deletion import apply_theta
from abm.definition import EmbedState, MeritAccumulator
from abm.agent_runtime import predict
from abm.definition import Constituent, FrozenPrice, NamedDefinition
from abm.domains import (
    AgentConfig,
    AgentInput,
    AgentState,
    CorrectionMode,
    Abstain,
    EdgePrediction,
    Entity,
    Relation,
    RelationGraph,
)
from abm.ledger import ARM_DESCRIPTOR_FIELDS, LEDGER_FIELDS
from abm.sme import map_graphs
from abm.world import generate_world
from abm.loop import run_longitudinal


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


def _prediction_state(motif: str, m: int = 4) -> AgentState:
    graph = _graph(motif, definition=True)
    selected_ids = ("core1", "core2", "higher", "tower")[:m]
    live_rows = tuple(
        Constituent(
            slot_index=index,
            registered_at=0,
            relation=next(relation for relation in graph.relations if relation.relation_id == relation_id),
            frozen_price=FrozenPrice(4.0, 7, 11.0, m),
        )
        for index, relation_id in enumerate(selected_ids)
    )
    mediator_relation = next(relation for relation in graph.relations if relation.relation_id == "mediator")
    tombstone = Constituent(
        slot_index=m,
        registered_at=0,
        relation=mediator_relation,
        frozen_price=FrozenPrice(4.0, 4, 11.0, m + 1),
        alive=False,
    )
    rows = (*live_rows, tombstone)
    definition = NamedDefinition(f"R-{motif}", rows, m + 1, 0)
    p_hat = update_frequency(AgentState().p_hat, graph.relations)
    history = {(definition.name, row.slot_index): frozenset((row.relation.predicate,)) for row in live_rows}
    return AgentState(
        prototype=graph,
        definitions={definition.name: definition},
        p_hat=p_hat,
        slot_history=history,
    )


def _predict(state: AgentState, partial: RelationGraph):
    agent_input = AgentInput(
        base_graph=state.prototype,
        target_graph_partial=partial,
        observable_mask=tuple(relation.relation_id for relation in partial.relations),
    )
    output, _ = predict(
        agent_input,
        state,
        AgentConfig(threshold=0.0, correction_mode=CorrectionMode.NONE, tau_acc=0.67),
        Random(0),
    )
    return output


@pytest.fixture(scope="module")
def prediction_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, defaultdict[str, int]] = {
        motif: defaultdict(int) for motif in MOTIFS
    }
    for definition_motif in MOTIFS:
        state = _prediction_state(definition_motif)
        rng = Random(2)
        for trial in range(8_000):
            scene_motif = tuple(MOTIFS)[trial % 4]
            partial = _with_holdout(scene_motif, rng)
            output = _predict(state, partial)
            counts[definition_motif]["entity_map_bool"] += isinstance(
                output.trace.get("entity_map_covered"), bool
            )
            counts[definition_motif]["fallback"] += bool(output.trace.get("filling_fallback", False))
            if output.trace.get("R_used") is not None:
                counts[definition_motif]["applications"] += 1
            if not isinstance(output.prediction, EdgePrediction):
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
    assert state.definitions["R"].constituents
    assert all(participation(state.merit[("R", row.slot_index)]) >= 0.5 for row in state.definitions["R"].constituents)


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


def test_3_6_m2_does_not_always_end_in_no_projectable_relation() -> None:
    state = _prediction_state("M1", m=2)
    rng = Random(2)
    count = 0
    for _ in range(2_000):
        output = _predict(state, _with_holdout("M1", rng))
        count += isinstance(output.prediction, Abstain) and output.prediction.reason == "no_projectable_relation"
    assert count < 2_000


def test_3_13_entity_map_covered_is_filled_on_every_trial(
    prediction_counts: dict[str, dict[str, int]],
) -> None:
    assert all(values["entity_map_bool"] == 8_000 for values in prediction_counts.values())


def test_3_14_slot_history_is_nonempty_immediately_after_registration() -> None:
    base = _graph("M1", definition=True)
    target = _graph("M1", definition=False)
    state = AgentState(p_hat=update_frequency(AgentState().p_hat, target.relations))
    registered, event = m1(state, base, target, map_graphs(base, target).alignment, 1, name="R")
    assert event is not None
    assert registered.slot_history
    assert all(len(predicates) >= 1 for predicates in registered.slot_history.values())


def test_3_15_v0_never_uses_signature_fallback(
    prediction_counts: dict[str, dict[str, int]],
) -> None:
    assert sum(values["fallback"] for values in prediction_counts.values()) == 0


@pytest.mark.parametrize(
    ("motif", "expected_live"),
    (("M1", 4), ("M2", 2), ("M3", 2), ("M4", 4)),
)
def test_4_8_theta_02637_reaches_expected_live_size(motif: str, expected_live: int) -> None:
    state = _deletion_state(motif)
    deleted, _ = apply_theta(
        state,
        AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.2637),
        trial=10,
    )
    assert deleted.definitions["R"].m_live == expected_live


def test_4_11_longitudinal_m_alloc_is_bounded() -> None:
    class MemoryLedger:
        def append(self, record):
            pass

    result = run_longitudinal(
        generate_world(7, 120, ("agent",)),
        {"agent": AgentState()},
        {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=0.041)},
        MemoryLedger(),
    )
    state = result.states["agent"]
    total_alloc = sum(definition.m_alloc for definition in state.definitions.values())
    assert len(state.definitions) <= len(MOTIFS)
    assert total_alloc <= len(state.p_hat.alive_vocab)


def _deletion_state(motif: str) -> AgentState:
    graph = _graph(motif, definition=True)
    extra = Relation("peripheral", PERIPHERAL[motif], ("a", "e"))
    relations = (*graph.relations, extra)
    rows = tuple(
        Constituent(index, 0, relation, FrozenPrice(4.0, 7, 11.0, 6))
        for index, relation in enumerate(relations)
    )
    definition = NamedDefinition("R", rows, 6, 0)
    survivor_count = 4 if motif in ("M1", "M4") else 2
    merit = {}
    embed = {}
    for index, row in enumerate(rows):
        participation_level = 0.20 if index < survivor_count else 0.02
        merit[("R", index)] = MeritAccumulator(
            index, 0, (participation_level * 2,) * 16, 2.0, 0
        )
        embed[("R", index)] = EmbedState(index, 0.0, 0.0)
    return AgentState(definitions={"R": definition}, merit=merit, embed=embed)
