"""SPEC B0+B2 §B.3〜§B.5 の場面と世界列。

不透明 ID の ``run_seed ‖ trial_index ‖ 役割名`` は、各値の文字列を
UTF-8 化し、境界バイト ``0x1f`` で連結した後に blake2b-8B へ入れる。
この表現は world_hash の再現性のため固定する。
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b, sha256
import json
from random import Random
from typing import Iterable, Mapping

from abm.domains import Entity, Relation, RelationGraph
from abm.seed import Seed, load_seed


MOTIF_ROWS = {
    "M1": (("hold", ("a", "b")), ("push", ("b", "a")), ("require", ("core1", "core2")), "carry", ("a", "b")),
    "M2": (("carry", ("a", "b")), ("lift", ("a", "b")), ("cause", ("core2", "core1")), "cold", ("a", "b")),
    "M3": (("break", ("a", "b")), ("cut", ("a", "b")), ("cause", ("core2", "core1")), "carry", ("a", "b")),
    "M4": (("push", ("a", "b")), ("turn", ("b", "c")), ("cause", ("core1", "core2")), "hard", ("a", "b", "c")),
}


@dataclass(frozen=True, slots=True)
class WorldTrial:
    trial: int
    motif: str
    G_star: RelationGraph
    target_graph_partial: RelationGraph
    held_out_edge: Relation
    u_coins: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "u_coins", dict(sorted(self.u_coins.items())))


@dataclass(frozen=True, slots=True)
class WorldSequence:
    trials: tuple[WorldTrial, ...]
    world_hash: str


def opaque_id(run_seed: str | int, trial_index: int, role_name: str) -> str:
    parts = (str(run_seed).encode("utf-8"), str(trial_index).encode("utf-8"), role_name.encode("utf-8"))
    return blake2b(b"\x1f".join(parts), digest_size=8).hexdigest()


def one_minus_h(pi_a: float) -> float:
    """``1 - E[1/n]`` を返す。``1/E[n]`` ではない。"""

    h_bar = sum((1.0 - pi_a) / (3 + glue_count) + pi_a / (4 + glue_count) for glue_count in (1, 2, 3)) / 3
    return 1.0 - h_bar


def validate_holdout_rates(seed: Seed) -> None:
    for motif in MOTIF_ROWS:
        calculated = one_minus_h(float(seed.data["pi_A"][motif]))
        expected = float(seed.data["one_minus_h"][motif])
        if abs(calculated - expected) > 1e-6:
            raise ValueError(f"{motif} の one_minus_h が不一致: {calculated} != {expected}")


def generate_world(
    run_seed: str | int,
    trial_count: int,
    agent_ids: Iterable[str],
    *,
    seed: Seed | None = None,
) -> WorldSequence:
    checked_seed = seed or load_seed()
    validate_holdout_rates(checked_seed)
    agents = tuple(sorted(agent_ids))
    trials = tuple(generate_trial(run_seed, index, agents, seed=checked_seed) for index in range(trial_count))
    return WorldSequence(trials=trials, world_hash=world_hash(trials))


def generate_trial(
    run_seed: str | int,
    trial_index: int,
    agent_ids: Iterable[str],
    *,
    seed: Seed,
) -> WorldTrial:
    motif = tuple(MOTIF_ROWS)[trial_index % len(MOTIF_ROWS)]
    rng = _trial_rng(run_seed, trial_index)
    core1, core2, higher, peripheral_predicate, core_entity_roles = MOTIF_ROWS[motif]
    has_peripheral = rng.random() < float(seed.data["pi_A"][motif])
    glue_count = rng.randint(1, 3)

    entity_roles = [*core_entity_roles, "mediator_entity"]
    if has_peripheral:
        entity_roles.append("peripheral_entity")
    entity_ids = {role: opaque_id(run_seed, trial_index, f"entity:{role}") for role in entity_roles}
    relation_ids = {
        role: opaque_id(run_seed, trial_index, f"relation:{role}")
        for role in ("core1", "core2", "higher", "mediator", "tower", "role_unary")
    }

    def args(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(relation_ids[value] if value in relation_ids else entity_ids[value] for value in values)

    bag = tuple(word for word, motifs in seed.data["bags"].items() if motif in motifs)
    relations = [
        Relation(relation_ids["core1"], core1[0], args(core1[1])),
        Relation(relation_ids["core2"], core2[0], args(core2[1])),
        Relation(relation_ids["higher"], higher[0], args(higher[1])),
        Relation(relation_ids["mediator"], rng.choice(bag), (entity_ids["a"], entity_ids["mediator_entity"])),
        Relation(relation_ids["tower"], "allow", (relation_ids["mediator"], relation_ids["core1"])),
        Relation(relation_ids["role_unary"], str(seed.data["role_unary"][motif]), (entity_ids["b"],)),
    ]
    holdout_candidates = [relation_ids["core1"], relation_ids["core2"], relation_ids["mediator"]]
    if has_peripheral:
        peripheral_id = opaque_id(run_seed, trial_index, "relation:peripheral")
        relations.append(
            Relation(peripheral_id, peripheral_predicate, (entity_ids["a"], entity_ids["peripheral_entity"]))
        )
        holdout_candidates.append(peripheral_id)

    available_entities = tuple(entity_ids.values())
    for index in range(glue_count):
        glue_id = opaque_id(run_seed, trial_index, f"relation:glue:{index}")
        left, right = rng.sample(available_entities, 2)
        relations.append(Relation(glue_id, rng.choice(tuple(seed.data["glue"])), (left, right)))
        holdout_candidates.append(glue_id)

    held_out_id = rng.choice(holdout_candidates)
    held_out = next(relation for relation in relations if relation.relation_id == held_out_id)
    graph = RelationGraph(
        graph_id=opaque_id(run_seed, trial_index, "graph"),
        entities=tuple(Entity(entity_id) for entity_id in available_entities),
        relations=tuple(relations),
    )
    visible_relations = tuple(relation for relation in relations if relation.relation_id != held_out_id)
    relation_id_set = frozenset(relation.relation_id for relation in visible_relations)
    reachable_entities = frozenset(
        argument
        for relation in visible_relations
        for argument in relation.arguments
        if argument not in relation_id_set and argument in available_entities
    )
    partial = RelationGraph(
        graph_id=graph.graph_id,
        entities=tuple(entity for entity in graph.entities if entity.entity_id in reachable_entities),
        relations=visible_relations,
    )
    coins = {agent_id: _u_coin(run_seed, agent_id, trial_index) for agent_id in sorted(agent_ids)}
    return WorldTrial(trial_index, motif, graph, partial, held_out, coins)


def canonical_world_bytes(trials: Iterable[WorldTrial]) -> bytes:
    sequence = []
    for item in sorted(trials, key=lambda value: value.trial):
        sequence.append(
            {
                "trial": item.trial,
                "motif": item.motif,
                "relations": [
                    {"id": relation.relation_id, "predicate": relation.predicate, "arguments": list(relation.arguments)}
                    for relation in item.G_star.relations
                ],
                "entities": [entity.entity_id for entity in item.G_star.entities],
                "held_out_relation_id": item.held_out_edge.relation_id,
                "u_coins": dict(item.u_coins),
            }
        )
    return json.dumps(sequence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def world_hash(trials: Iterable[WorldTrial]) -> str:
    return sha256(canonical_world_bytes(trials)).hexdigest()


def _trial_rng(run_seed: str | int, trial_index: int) -> Random:
    material = f"{run_seed}\x1f{trial_index}\x1fworld".encode("utf-8")
    return Random(int.from_bytes(sha256(material).digest(), "big"))


def _u_coin(run_seed: str | int, agent_id: str, trial_index: int) -> float:
    material = f"{run_seed}\x1f{agent_id}\x1f{trial_index}\x1fu".encode("utf-8")
    integer = int.from_bytes(sha256(material).digest()[:8], "big")
    return integer / 2**64
