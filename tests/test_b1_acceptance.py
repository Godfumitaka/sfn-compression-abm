"""SPEC B1 §C.9 の中核受け入れ試験。"""

from __future__ import annotations

from collections import defaultdict
from random import Random

import pytest

from abm.abstraction import _identify_definition, m1
from abm.accounting import (
    constituent_value, decay_ladder, exception_cost, initial_merit, participation,
    update_frequency,
)
from abm.deletion import apply_theta
from abm.definition import EmbedState, ExceptionAccumulator, MeritAccumulator
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
    Prototype,
    RepairScope,
    VerbatimTrace,
)
from abm.ledger import ARM_DESCRIPTOR_FIELDS, LEDGER_FIELDS
from abm.sme import map_graphs
from abm.world import generate_world
from abm.loop import _repair_targets, run_longitudinal


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
    history = {
        (definition.name, row.slot_index, row.registered_at): frozenset((row.relation.predicate,))
        for row in live_rows
    }
    return AgentState(
        prototype=Prototype((VerbatimTrace(0, graph),)),
        definitions={definition.name: definition},
        p_hat=p_hat,
        slot_history=history,
    )


def _predict(state: AgentState, partial: RelationGraph):
    agent_input = AgentInput(
        base_graph=state.prototype.traces[0].scene,
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


def test_1_11_ledger_has_89_unique_fields() -> None:
    assert len(LEDGER_FIELDS) == len(set(LEDGER_FIELDS)) == 93


def test_1_12_run_header_has_13_arm_descriptors() -> None:
    assert len(ARM_DESCRIPTOR_FIELDS) == len(set(ARM_DESCRIPTOR_FIELDS)) == 13


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
        base_written_at=0,
        horizon=400,
    )
    assert event is not None
    assert state.definitions["R"].constituents
    assert all(
        participation(state.merit[("R", row.slot_index, row.registered_at)]) >= 0.5
        for row in state.definitions["R"].constituents
    )


def test_2_2_exception_cost_is_9_024_bits() -> None:
    assert exception_cost(4, 5.024) == pytest.approx(9.024)


def test_2_4_to_2_6_exception_cost_lowers_value_without_a_floor() -> None:
    merit = MeritAccumulator(0, 0, (2.0,) * 16, (2.0,) * 16, 2.0, 0)
    embed = EmbedState(0, 0.0, 0.0)
    price = FrozenPrice(4.0, 4, 8.0, 4)
    values = [
        constituent_value(
            price, merit, ExceptionAccumulator((charged,) * 16, charged, int(charged > 0)),
            embed, w=0.0, kappa=1.0,
        )
        for charged in (0.0, 2.0, 20.0)
    ]
    assert values[0] > values[1] > values[2]
    assert values[2] < 0.0


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
    registered, event = m1(
        state, base, target, map_graphs(base, target).alignment, 1,
        name="R", base_written_at=0, horizon=400,
    )
    assert event is not None
    assert registered.slot_history
    assert all(len(predicates) >= 1 for predicates in registered.slot_history.values())


def test_3_15_v0_never_uses_signature_fallback(
    prediction_counts: dict[str, dict[str, int]],
) -> None:
    assert sum(values["fallback"] for values in prediction_counts.values()) == 0


def _synthetic_merit(k: int) -> MeritAccumulator:
    ladder = decay_ladder(400)
    basis = (0.0,) * 16
    opportunity_basis = (0.0,) * 16
    for trial in range(1, 401):
        basis = tuple(value * factor + float(trial % k == 0) for value, factor in zip(basis, ladder))
        opportunity_basis = tuple(value * factor + 1.0 for value, factor in zip(opportunity_basis, ladder))
    return MeritAccumulator(0, 0, basis, opportunity_basis, 0.0, 0)


@pytest.mark.parametrize(
    ("k", "expected"),
    ((1, 1.000000), (2, 0.503055), (5, 0.205210), (10, 0.106179), (50, 0.027628)),
)
def test_5_17_participation_tracks_independent_opportunities(k: int, expected: float) -> None:
    assert participation(_synthetic_merit(k)) == pytest.approx(expected, rel=1e-4)


def test_5_18_participation_preserves_fulfilment_rate_difference() -> None:
    assert participation(_synthetic_merit(1)) / participation(_synthetic_merit(10)) >= 9.0


@pytest.mark.parametrize("base_age", (0, 100))
def test_5_19_d_cold_initial_participation_is_one(base_age: int) -> None:
    base = _graph("M1", definition=True)
    target = _graph("M1", definition=False)
    state = AgentState(p_hat=update_frequency(AgentState().p_hat, target.relations))
    registered, event = m1(
        state,
        base,
        target,
        map_graphs(base, target).alignment,
        trial=base_age,
        name="R",
        base_written_at=0,
        horizon=400,
    )
    assert event is not None
    for row in registered.definitions["R"].constituents:
        assert participation(
            registered.merit[("R", row.slot_index, row.registered_at)]
        ) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize(
    ("base_age", "expected"),
    ((0, 32.000000), (1, 28.276717), (5, 25.373605), (20, 22.883322), (100, 20.061277)),
)
def test_5_20_d_cold_strength_reflects_base_age(base_age: int, expected: float) -> None:
    assert sum(initial_merit(0, 0, base_age, 400).basis) == pytest.approx(expected, rel=1e-6)


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
    assert all(definition.m_alloc <= 6 for definition in state.definitions.values())


class _MemoryLedger:
    def __init__(self) -> None:
        self.records = []

    def append(self, record) -> None:
        self.records.append(record)


def _longitudinal_run(
    theta_prime: float,
    trial_count: int = 400,
    repair_scope: RepairScope = RepairScope.FIRST_ORDER,
):
    ledger = _MemoryLedger()
    result = run_longitudinal(
        generate_world(1, trial_count, ("agent",)),
        {"agent": AgentState()},
        {"agent": AgentConfig(
            0.0, CorrectionMode.NONE, theta_prime=theta_prime,
            repair_scope=repair_scope,
        )},
        ledger,
        snapshot_mode="full",
        calculate_counterfactuals=False,
    )
    return result.states["agent"], ledger.records


@pytest.fixture(scope="module")
def thinning_run():
    return _longitudinal_run(0.2637)


@pytest.fixture(scope="module")
def theta_runs(thinning_run):
    return {
        0.0410: _longitudinal_run(0.0410),
        0.1432: _longitudinal_run(0.1432),
        0.2637: thinning_run,
        0.3842: _longitudinal_run(0.3842),
    }


def _prototype_sizes(records) -> list[int]:
    return [len(record["state_snapshot"]["value"]["prototype"]["traces"]) for record in records]


def test_4_12_longitudinal_writes_a_prototype(thinning_run) -> None:
    state, _ = thinning_run
    assert state.prototype.traces


def test_4_13_longitudinal_produces_a_prediction(thinning_run) -> None:
    _, records = thinning_run
    assert any(record["prediction_kind"] != "Abstain" for record in records)


def test_4_14_longitudinal_records_a_deletion(thinning_run) -> None:
    _, records = thinning_run
    assert any(
        event["kind"] == "deletion"
        for record in records for event in record["deletion_event"]
    )


def test_4_15_prototype_does_not_grow_monotonically(thinning_run) -> None:
    _, records = thinning_run
    sizes = _prototype_sizes(records)
    assert len(set(sizes[-20:])) == 1


def test_4_16_definitions_and_allocations_are_bounded(thinning_run) -> None:
    state, _ = thinning_run
    assert all(definition.m_alloc <= 6 for definition in state.definitions.values())


def test_4_17_m_live_is_not_monotonically_increasing() -> None:
    _, records = _longitudinal_run(0.3842)
    values = [record["m_live"] for record in records]
    assert any(current < previous for previous, current in zip(values, values[1:]))


def test_4_18_prototype_converges_to_theta_specific_size(theta_runs) -> None:
    for theta_prime, expected in ((0.1432, 49), (0.2637, 14), (0.3842, 7)):
        _, records = theta_runs[theta_prime]
        sizes = _prototype_sizes(records)
        assert expected * 0.5 <= sum(sizes[-20:]) / 20 <= expected * 1.5
        assert max(sizes[-20:]) - min(sizes[-20:]) <= expected * 0.5


def test_4_19_public_history_contains_no_scene_graph(thinning_run) -> None:
    state, _ = thinning_run
    assert not any(isinstance(item, RelationGraph) for item in state.public_history)


@pytest.mark.parametrize("theta_prime", (0.0410, 0.1432, 0.2637, 0.3842))
def test_4_20_below_threshold_stays_low(theta_prime: float, theta_runs) -> None:
    _, records = theta_runs[theta_prime]
    below = sum(record["abstain_reason"] == "below_threshold" for record in records)
    assert below / 400 < 0.05


def test_4_21_definitions_are_used_at_every_theta(theta_runs) -> None:
    # 予測件数が theta_prime で動くのは設計どおりである。低い theta_prime では
    # 媒介入り m=5 の def が残り、媒介を伏せると no_projectable_relation で棄権する。
    # 棄権理由は毎試行の abstain_reason から走行後に再構成できる。
    for _, records in theta_runs.values():
        used = sum(record["R_used"] is not None for record in records)
        assert used / len(records) >= 0.10


def test_4_22_at_least_one_definition_reaches_four_allocations(theta_runs) -> None:
    state, _ = theta_runs[0.2637]
    assert any(definition.m_alloc >= 4 for definition in state.definitions.values())


def test_5_1_and_5_2_definitions_are_adopted_longitudinally(thinning_run) -> None:
    _, records = thinning_run
    adopted = sum(record["R_used"] is not None for record in records)
    assert adopted >= 100
    assert adopted / len(records) >= 0.10


def test_5_3_predictions_never_fall_back_to_verbatim(thinning_run) -> None:
    _, records = thinning_run
    assert all(
        record["R_used"] is not None or record["prediction_kind"] == "Abstain"
        for record in records
    )


def test_5_4_to_5_7_abstention_and_filling_paths_are_observable(thinning_run) -> None:
    _, records = thinning_run
    reasons = {record["abstain_reason"] for record in records}
    assert "below_tau" in reasons
    assert "no_definition" in reasons
    assert any(record["entity_map_covered"] for record in records)
    assert any(record["filled_predicate"] for record in records)


def test_5_12_filled_predictions_hit_the_held_out_edge(thinning_run) -> None:
    _, records = thinning_run
    filled = [record for record in records if record["filled_predicate"]]
    assert filled
    # NSIM 同定では def(R) 数が増え得るため、充填の経験的下限だけを検査する。
    assert sum(record["hit"] == 1 for record in filled) / len(filled) >= 0.30


def test_5_13_nsim_self_similarity_is_one() -> None:
    state = _prediction_state("M1")
    definition = next(iter(state.definitions.values()))
    assert _identify_definition(state, _graph("M1", definition=True), 0.95) == definition.name


def test_5_21_to_5_24_and_5_26_exception_ledger(theta_runs) -> None:
    _, records = theta_runs[0.3842]
    reasons = [
        reason for record in records
        for rows in record["constituent_reason_123"].values()
        for reason in rows.values()
    ]
    assert {"充足", "②", "③", "判定不能"} <= set(reasons)
    assert any(record["exception_bits_charged"] > 0.0 for record in records)
    assert any(record["constituent_reason_123"] for record in records)
    for record in records:
        sources = record["charge_source"]
        if sources is not None:
            assert not ({tuple(item) for item in sources["②"]} & {tuple(item) for item in sources["①"]}) or sources["①"]


def test_5_27_and_5_28_collision_accounting_uses_mean(theta_runs) -> None:
    collisions = [
        collision for record in theta_runs[0.3842][1]
        if record["charge_source"] is not None
        for collision in record["charge_source"]["衝突"]
    ]
    assert collisions
    assert all(item["平均"] == pytest.approx(sum(item["符号長"]) / len(item["符号長"])) for item in collisions)


@pytest.mark.parametrize(
    ("base_ids", "scope", "expected"),
    (
        ({"rid_core1", "rid_core2"}, RepairScope.FIRST_ORDER,
         {"rid_core1", "rid_core2", "rid_higher"}),
        ({"rid_core1", "rid_core2"}, RepairScope.SECOND_ORDER,
         {"rid_core1", "rid_core2", "rid_higher", "rid_tower"}),
        ({"rid_core1", "rid_core2"}, RepairScope.ALL,
         {"rid_core1", "rid_core2", "rid_higher", "rid_tower"}),
        ({"rid_med"}, RepairScope.FIRST_ORDER, {"rid_med", "rid_tower"}),
        ({"rid_med"}, RepairScope.SECOND_ORDER, {"rid_med", "rid_tower"}),
        ({"rid_med"}, RepairScope.ALL, {"rid_med", "rid_tower"}),
    ),
)
def test_5_25_repair_scope_reaches_expected_relations(
    base_ids: set[str], scope: RepairScope, expected: set[str],
) -> None:
    relations = (
        Relation("rid_core1", "break", ("a", "b")),
        Relation("rid_core2", "cut", ("a", "b")),
        Relation("rid_higher", "cause", ("rid_core1", "rid_core2")),
        Relation("rid_med", "stone", ("a", "e")),
        Relation("rid_tower", "allow", ("rid_med", "rid_higher")),
    )
    rows = tuple(
        Constituent(index, 0, relation, FrozenPrice(4.0, 7, 11.0, 6))
        for index, relation in enumerate(relations)
    )
    definition = NamedDefinition("R", rows, 5, 0)

    reached = _repair_targets(definition, base_ids, scope)

    assert len(reached) == len(expected)
    assert reached == expected


def test_5_14_universal_predicate_alone_does_not_identify() -> None:
    state = _prediction_state("M1")
    assert _identify_definition(state, _graph("M2", definition=False), 0.95) is None


def test_5_15_identification_order_does_not_depend_on_name() -> None:
    first = next(iter(_prediction_state("M1").definitions.values()))
    second = next(iter(_prediction_state("M2").definitions.values()))
    scene = _graph("M1", definition=False)
    state_a = AgentState(definitions={
        "zzz": NamedDefinition("zzz", first.constituents, first.m_alloc, 2, 4),
        "aaa": NamedDefinition("aaa", second.constituents, second.m_alloc, 1, 3),
    })
    state_b = AgentState(definitions={
        "aaa": NamedDefinition("aaa", first.constituents, first.m_alloc, 2, 4),
        "zzz": NamedDefinition("zzz", second.constituents, second.m_alloc, 1, 3),
    })
    assert _identify_definition(state_a, scene, 0.0) == "zzz"
    assert _identify_definition(state_b, scene, 0.0) == "aaa"


def test_5_16_nsim_threshold_endpoints() -> None:
    definition = next(iter(_prediction_state("M1").definitions.values()))
    scene = _graph("M1", definition=False)
    state = AgentState(definitions={definition.name: definition})
    assert _identify_definition(state, scene, 1.01) is None
    assert _identify_definition(state, scene, 0.0) == definition.name


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
        merit[("R", index, row.registered_at)] = MeritAccumulator(
            index, 0, (participation_level * 2,) * 16, (2.0,) * 16, 2.0, 0
        )
        embed[("R", index, row.registered_at)] = EmbedState(index, 0.0, 0.0)
    return AgentState(definitions={"R": definition}, merit=merit, embed=embed)
