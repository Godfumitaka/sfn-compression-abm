"""BUILD ORDER 第4段の seed graph 定義。

このモジュールは `solar_system_atom` と `water_heat_flow` の二グラフ提示単位を
定義するだけに留める。redaction、operator、oracle 評価、SME/MDL 接続は後続段の
責務なのでここでは扱わない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from abm.domains import Entity, Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class SeedGraphs:
    """base/source と target の完全グラフ、および target 側 hold-out 候補。"""

    seed_id: str
    base_graph: RelationGraph
    target_graph: RelationGraph
    held_out_candidates: tuple[Relation, ...]
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "held_out_candidates", tuple(self.held_out_candidates))
        object.__setattr__(self, "notes", dict(self.notes))
        target_relation_ids = {relation.relation_id for relation in self.target_graph.relations}
        missing = [
            relation.relation_id
            for relation in self.held_out_candidates
            if relation.relation_id not in target_relation_ids
        ]
        if missing:
            raise ValueError("held_out_candidates must be relations in target_graph")


def solar_system_atom() -> SeedGraphs:
    """太陽系から原子系への構造写像に使う seed graph を返す。"""

    base_entities = (
        Entity("sun", label="sun"),
        Entity("planet", label="planet"),
    )
    base_relations = (
        Relation("solar_distinct_sun_planet", "distinct", ("sun", "planet")),
        Relation("solar_central_body_sun", "central_body", ("sun",)),
        Relation("solar_orbiting_body_planet", "orbiting_body", ("planet",)),
        Relation("solar_more_massive_sun_planet", "more_massive_than", ("sun", "planet")),
        Relation("solar_attracts_sun_planet", "attracts", ("sun", "planet")),
        Relation("solar_revolves_around_planet_sun", "revolves_around", ("planet", "sun")),
        Relation(
            "solar_cause_attraction_orbit",
            "cause",
            ("solar_attracts_sun_planet", "solar_revolves_around_planet_sun"),
        ),
        Relation(
            "solar_systematicity_cluster",
            "and",
            (
                "solar_more_massive_sun_planet",
                "solar_attracts_sun_planet",
                "solar_revolves_around_planet_sun",
                "solar_cause_attraction_orbit",
            ),
        ),
    )

    target_entities = (
        Entity("nucleus", label="nucleus"),
        Entity("electron", label="electron"),
    )
    target_revolves = Relation(
        "atom_revolves_around_electron_nucleus",
        "revolves_around",
        ("electron", "nucleus"),
    )
    target_relations = (
        Relation("atom_distinct_nucleus_electron", "distinct", ("nucleus", "electron")),
        Relation("atom_central_body_nucleus", "central_body", ("nucleus",)),
        Relation("atom_orbiting_body_electron", "orbiting_body", ("electron",)),
        Relation(
            "atom_more_massive_nucleus_electron",
            "more_massive_than",
            ("nucleus", "electron"),
        ),
        Relation("atom_attracts_nucleus_electron", "attracts", ("nucleus", "electron")),
        target_revolves,
        Relation(
            "atom_cause_attraction_orbit",
            "cause",
            ("atom_attracts_nucleus_electron", "atom_revolves_around_electron_nucleus"),
        ),
        Relation(
            "atom_systematicity_cluster",
            "and",
            (
                "atom_more_massive_nucleus_electron",
                "atom_attracts_nucleus_electron",
                "atom_revolves_around_electron_nucleus",
                "atom_cause_attraction_orbit",
            ),
        ),
    )
    return SeedGraphs(
        seed_id="solar_system_atom",
        base_graph=RelationGraph("solar_system_base", base_entities, base_relations),
        target_graph=RelationGraph("atom_target", target_entities, target_relations),
        held_out_candidates=(target_revolves,),
        notes={"candidate_role": "target-side candidate inference connected to cause/and"},
    )


def water_heat_flow() -> SeedGraphs:
    """水流から熱流への構造写像に使う seed graph を返す。"""

    base_entities = (
        Entity("high_pressure_reservoir", label="high pressure reservoir"),
        Entity("low_pressure_reservoir", label="low pressure reservoir"),
        Entity("pipe", label="pipe"),
        Entity("water", label="water"),
    )
    base_relations = (
        Relation(
            "water_distinct_reservoirs",
            "distinct",
            ("high_pressure_reservoir", "low_pressure_reservoir"),
        ),
        Relation(
            "water_connected_by_pipe",
            "connected_by",
            ("high_pressure_reservoir", "low_pressure_reservoir", "pipe"),
        ),
        Relation(
            "water_pressure_difference",
            "greater_pressure_than",
            ("high_pressure_reservoir", "low_pressure_reservoir"),
        ),
        Relation(
            "water_flows_high_to_low",
            "flows_from_to",
            ("water", "high_pressure_reservoir", "low_pressure_reservoir"),
        ),
        Relation(
            "water_cause_pressure_flow",
            "cause",
            ("water_pressure_difference", "water_flows_high_to_low"),
        ),
        Relation(
            "water_systematicity_cluster",
            "and",
            (
                "water_connected_by_pipe",
                "water_pressure_difference",
                "water_flows_high_to_low",
                "water_cause_pressure_flow",
            ),
        ),
    )

    target_entities = (
        Entity("hot_region", label="hot region"),
        Entity("cold_region", label="cold region"),
        Entity("conductor", label="conductor"),
        Entity("heat", label="heat"),
    )
    target_flow = Relation(
        "heat_flows_hot_to_cold",
        "flows_from_to",
        ("heat", "hot_region", "cold_region"),
    )
    target_relations = (
        Relation("heat_distinct_regions", "distinct", ("hot_region", "cold_region")),
        Relation(
            "heat_connected_by_conductor",
            "connected_by",
            ("hot_region", "cold_region", "conductor"),
        ),
        Relation(
            "heat_temperature_difference",
            "greater_temperature_than",
            ("hot_region", "cold_region"),
        ),
        target_flow,
        Relation(
            "heat_cause_temperature_flow",
            "cause",
            ("heat_temperature_difference", "heat_flows_hot_to_cold"),
        ),
        Relation(
            "heat_systematicity_cluster",
            "and",
            (
                "heat_connected_by_conductor",
                "heat_temperature_difference",
                "heat_flows_hot_to_cold",
                "heat_cause_temperature_flow",
            ),
        ),
    )
    return SeedGraphs(
        seed_id="water_heat_flow",
        base_graph=RelationGraph("water_flow_base", base_entities, base_relations),
        target_graph=RelationGraph("heat_flow_target", target_entities, target_relations),
        held_out_candidates=(target_flow,),
        notes={"candidate_role": "target-side flow inference connected to cause/and"},
    )


def seed_graphs() -> tuple[SeedGraphs, ...]:
    """第4段で定義する seed graph を安定順で返す。"""

    return (solar_system_atom(), water_heat_flow())
