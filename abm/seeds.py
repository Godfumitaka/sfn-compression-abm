"""BUILD ORDER 第4段の seed graph 定義。

SPEC §4・§11-4 に従い、source 役の base graph と target 側の完全 graph、
および target 側で hold-out 可能な候補推論辺だけを置く。ここでは世界や可観測性を
操作せず、後続の perturbation や redaction に先立つ静的な素材だけを定義する。
"""

from __future__ import annotations

from dataclasses import dataclass

from abm.domains import Entity, Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class SeedGraphs:
    """base/target の対と、target 側 candidate inference 候補の束。"""

    seed_id: str
    base_graph: RelationGraph
    target_graph: RelationGraph
    held_out_candidates: tuple[Relation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "held_out_candidates", tuple(self.held_out_candidates))
        target_relation_ids = {relation.relation_id for relation in self.target_graph.relations}
        missing = [
            relation.relation_id
            for relation in self.held_out_candidates
            if relation.relation_id not in target_relation_ids
        ]
        if missing:
            raise ValueError(f"held_out_candidates must be target relations: {missing}")


def solar_system_atom() -> SeedGraphs:
    """太陽系と原子構造の seed graph を返す。"""

    base_entities = (
        Entity("sun", "sun", {"role": "center"}),
        Entity("planet", "planet", {"role": "orbiter"}),
        Entity("gravity", "gravity", {"role": "force"}),
    )
    base_relations = (
        Relation("solar_r1", "more_massive_than", ("sun", "planet")),
        Relation("solar_r2", "attracts", ("sun", "planet", "gravity")),
        Relation("solar_r3", "revolves_around", ("planet", "sun")),
        Relation("solar_r4", "causes", ("solar_r2", "solar_r3")),
        Relation("solar_r5", "central_body", ("sun",)),
        Relation("solar_r6", "orbiting_body", ("planet",)),
        Relation("solar_r7", "enables", ("solar_r1", "solar_r2")),
    )

    target_entities = (
        Entity("nucleus", "nucleus", {"role": "center"}),
        Entity("electron", "electron", {"role": "orbiter"}),
        Entity("electromagnetic_force", "electromagnetic force", {"role": "force"}),
    )
    target_relations = (
        Relation("atom_r1", "more_massive_than", ("nucleus", "electron")),
        Relation("atom_r2", "attracts", ("nucleus", "electron", "electromagnetic_force")),
        Relation("atom_r3", "revolves_around", ("electron", "nucleus")),
        Relation("atom_r4", "causes", ("atom_r2", "atom_r3")),
        Relation("atom_r5", "central_body", ("nucleus",)),
        Relation("atom_r6", "orbiting_body", ("electron",)),
        Relation("atom_r7", "enables", ("atom_r1", "atom_r2")),
    )

    held_out = (target_relations[2], target_relations[3])
    return SeedGraphs(
        seed_id="solar_system_atom",
        base_graph=RelationGraph("solar_system", base_entities, base_relations),
        target_graph=RelationGraph("atom", target_entities, target_relations),
        held_out_candidates=held_out,
    )


def water_heat_flow() -> SeedGraphs:
    """水流と熱流の seed graph を返す。"""

    base_entities = (
        Entity("upper_tank", "upper tank", {"role": "source"}),
        Entity("lower_tank", "lower tank", {"role": "sink"}),
        Entity("water", "water", {"role": "medium"}),
        Entity("pipe", "pipe", {"role": "path"}),
    )
    base_relations = (
        Relation("water_r1", "greater_potential_than", ("upper_tank", "lower_tank")),
        Relation("water_r2", "connected_by", ("upper_tank", "lower_tank", "pipe")),
        Relation("water_r3", "flows_from_to", ("water", "upper_tank", "lower_tank")),
        Relation("water_r4", "causes", ("water_r1", "water_r3")),
        Relation("water_r5", "requires_path", ("water_r3", "pipe")),
        Relation("water_r6", "source_role", ("upper_tank",)),
        Relation("water_r7", "sink_role", ("lower_tank",)),
    )

    target_entities = (
        Entity("hot_object", "hot object", {"role": "source"}),
        Entity("cold_object", "cold object", {"role": "sink"}),
        Entity("heat", "heat", {"role": "medium"}),
        Entity("thermal_contact", "thermal contact", {"role": "path"}),
    )
    target_relations = (
        Relation("heat_r1", "greater_potential_than", ("hot_object", "cold_object")),
        Relation("heat_r2", "connected_by", ("hot_object", "cold_object", "thermal_contact")),
        Relation("heat_r3", "flows_from_to", ("heat", "hot_object", "cold_object")),
        Relation("heat_r4", "causes", ("heat_r1", "heat_r3")),
        Relation("heat_r5", "requires_path", ("heat_r3", "thermal_contact")),
        Relation("heat_r6", "source_role", ("hot_object",)),
        Relation("heat_r7", "sink_role", ("cold_object",)),
    )

    held_out = (target_relations[2], target_relations[4])
    return SeedGraphs(
        seed_id="water_heat_flow",
        base_graph=RelationGraph("water_flow", base_entities, base_relations),
        target_graph=RelationGraph("heat_flow", target_entities, target_relations),
        held_out_candidates=held_out,
    )


def seed_graphs() -> tuple[SeedGraphs, ...]:
    """第4段で登録する seed graph を固定順で返す。"""

    return (solar_system_atom(), water_heat_flow())
