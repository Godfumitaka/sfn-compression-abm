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
from typing import Any, Iterable, Mapping

from abm.domains import Entity, Relation, RelationGraph
from abm.seed import Seed, load_seed


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


def one_minus_h(pi_a: float, first_order_count: int = 2, higher_count: int = 0) -> float:
    """``1 - E[1/n]`` を返す。``1/E[n]`` ではない。

    ``n = F + H + 1 + Bernoulli(pi_A) + Uniform{1,2,3}``。
    F は展開した一階の本数、H は保持辺の候補に入れる二階の本数。
    既定の ``F=2, H=0`` は従来式 ``(1-pi)/(3+g) + pi/(4+g)`` と同一である。
    ★ SPEC_B0B2:165 の改訂（仮U-42・仮D-59）。H>0 は新種でのみ使う。
    """

    f = int(first_order_count) + int(higher_count)
    h_bar = sum((1.0 - pi_a) / (f + 1 + glue_count) + pi_a / (f + 2 + glue_count) for glue_count in (1, 2, 3)) / 3
    return 1.0 - h_bar


HOLDOUT_RATE_MODEL_STRUCTURAL = "structural_first_order_v1"
HOLDOUT_RATE_MODEL_SECOND_ORDER = "structural_with_second_order_v1"


def _second_order_count(data: Mapping[str, Any], motif: str) -> int:
    return sum(1 for _, node in _expand_motif(data, motif) if node[0] == 2)


def validate_holdout_rates(seed: Seed) -> None:
    model = seed.data.get("holdout_rate_model")
    known = (HOLDOUT_RATE_MODEL_STRUCTURAL, HOLDOUT_RATE_MODEL_SECOND_ORDER)
    if model is not None and model not in known:
        raise ValueError(f"未知の holdout_rate_model: {model}")
    for motif in seed.data["motif_structure"]:
        higher_count = 0
        if model == HOLDOUT_RATE_MODEL_SECOND_ORDER:
            # ★ 仮D-59  実態に合わせた式。保持辺の候補に二階を入れる新種でのみ使う。
            first_order_count = len(_first_order_paths(seed.data, motif))
            higher_count = _second_order_count(seed.data, motif)
        elif model == HOLDOUT_RATE_MODEL_STRUCTURAL:
            first_order_count = len(_first_order_paths(seed.data, motif))
        else:
            # ★ 欄が無い既存の種は従来式（F=2）のまま。値も検算も変えない。
            first_order_count = 2
        calculated = one_minus_h(float(seed.data["pi_A"][motif]), first_order_count, higher_count)
        expected = float(seed.data["one_minus_h"][motif])
        if abs(calculated - expected) > 1e-6:
            raise ValueError(f"{motif} の one_minus_h が不一致: {calculated} != {expected}")


def generate_world(
    run_seed: str | int,
    trial_count: int,
    agent_ids: Iterable[str],
    *,
    seed: Seed | None = None,
    holdout_include_second_order: bool = False,
) -> WorldSequence:
    checked_seed = seed or load_seed()
    validate_holdout_rates(checked_seed)
    agents = tuple(sorted(agent_ids))
    trials = tuple(generate_trial(run_seed, index, agents, seed=checked_seed,
                                  holdout_include_second_order=holdout_include_second_order)
                   for index in range(trial_count))
    return WorldSequence(trials=trials, world_hash=world_hash(trials))


#: 旧形状（根＋部分木 2・各 first_order 2）の役割名。★ 一文字も変えない。
_LEGACY_ROLE_BY_PATH = {
    "0.0": "fo_1", "0.1": "fo_2", "1.0": "fo_3", "1.1": "fo_4",
    "0": "higher_1", "1": "higher_2", "root": "third",
}


def _expand_node(subtrees: Mapping[str, Any], name: str, path: str, nodes: list) -> int:
    """``subtrees`` の 1 ノードを展開し、その階数を返す。★ 乱数を消費しない。"""

    node = subtrees[name]
    has_first_order = "first_order" in node
    has_children = "subtrees" in node
    if has_first_order == has_children:
        raise ValueError(f"subtrees[{name}] は first_order と subtrees のちょうど一方を持つ必要がある")
    if has_first_order:
        first_order_paths = []
        for index, predicate in enumerate(node["first_order"]):
            child_path = f"{path}.{index}"
            nodes.append((1, child_path, str(predicate), None))
            first_order_paths.append(child_path)
        if not first_order_paths:
            raise ValueError(f"subtrees[{name}].first_order が空である")
        nodes.append((2, path, str(node["higher"]), tuple(first_order_paths)))
        return 2
    child_paths: list[str] = []
    child_levels: list[int] = []
    for index, child_name in enumerate(node["subtrees"]):
        child_path = f"{path}.{index}"
        child_levels.append(_expand_node(subtrees, child_name, child_path, nodes))
        child_paths.append(child_path)
    if not child_paths:
        raise ValueError(f"subtrees[{name}].subtrees が空である")
    level = 1 + max(child_levels)
    nodes.append((level, path, str(node["higher"]), tuple(child_paths)))
    return level


def _expand_motif(data: Mapping[str, Any], motif: str) -> tuple:
    """モチーフ 1 つの関係の骨格を返す。階数の昇順、階内は左からの出現順。

    ★ 階数は参照構造から導く。述語名や版名では分岐しない。
    ★ ``third`` は「根の述語」の互換フィールドとして読む。
    """

    motif_row = data["motif_structure"][motif]
    subtrees = data["subtrees"]
    nodes: list = []
    child_paths: list[str] = []
    child_levels: list[int] = []
    for index, child_name in enumerate(motif_row["subtrees"]):
        child_path = str(index)
        child_levels.append(_expand_node(subtrees, child_name, child_path, nodes))
        child_paths.append(child_path)
    nodes.append((1 + max(child_levels), "root", str(motif_row["third"]), tuple(child_paths)))
    return tuple(sorted(enumerate(nodes), key=lambda pair: (pair[1][0], pair[0])))


def _first_order_paths(data: Mapping[str, Any], motif: str) -> tuple[str, ...]:
    return tuple(node[1] for _, node in _expand_motif(data, motif) if node[0] == 1)


def _is_legacy_shape(data: Mapping[str, Any], motif: str) -> bool:
    """旧形状かどうかを構造だけで判定する。"""

    motif_row = data["motif_structure"][motif]
    names = tuple(motif_row["subtrees"])
    if len(names) != 2:
        return False
    for name in names:
        node = data["subtrees"][name]
        if "subtrees" in node or "first_order" not in node:
            return False
        if len(node["first_order"]) != 2:
            return False
    return True


def generate_trial(
    run_seed: str | int,
    trial_index: int,
    agent_ids: Iterable[str],
    *,
    seed: Seed,
    holdout_include_second_order: bool = False,
) -> WorldTrial:
    motif = _motif_for_trial(run_seed, trial_index, tuple(seed.data["motif_structure"]))
    rng = _trial_rng(run_seed, trial_index)
    motif_row = seed.data["motif_structure"][motif]
    # ★ 構造の展開では乱数を消費しない（B-2）。周縁コインより前に置いてよい。
    skeleton = _expand_motif(seed.data, motif)
    legacy = _is_legacy_shape(seed.data, motif)
    has_peripheral = rng.random() < float(seed.data["pi_A"][motif])
    glue_count = rng.randint(1, 3)

    entity_roles = ["a", "b", "mediator_entity"]
    if has_peripheral:
        entity_roles.append("peripheral_entity")
    entity_ids = {role: opaque_id(run_seed, trial_index, f"entity:{role}") for role in entity_roles}

    def role_name(path: str) -> str:
        # 旧形状は fo_1..fo_4 / higher_1 / higher_2 / third をそのまま使う（B-3）。
        if legacy:
            return _LEGACY_ROLE_BY_PATH[path]
        return f"tree:{path}"

    relation_ids = {
        path: opaque_id(run_seed, trial_index, f"relation:{role_name(path)}")
        for _, (_, path, _, _) in skeleton
    }
    for role in ("mediator", "role_unary"):
        relation_ids[role] = opaque_id(run_seed, trial_index, f"relation:{role}")

    def args(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(relation_ids[value] if value in relation_ids else entity_ids[value] for value in values)

    bag = tuple(word for word, motifs in seed.data["bags"].items() if motif in motifs)
    # ★ 階数の昇順・階内は左からの出現順（B-4）。一階は (a,b)、親は子の関係 ID を取る。
    relations = [
        Relation(relation_ids[path], predicate,
                 args(("a", "b")) if children is None else args(children))
        for _, (_, path, predicate, children) in skeleton
    ]
    relations.append(
        Relation(relation_ids["mediator"], rng.choice(bag), (entity_ids["a"], entity_ids["mediator_entity"]))
    )
    relations.append(
        Relation(relation_ids["role_unary"], str(seed.data["role_unary"][motif]), (entity_ids["b"],))
    )
    # ★ 保持辺の候補は展開した一階リストの順序。二階以上と役割ユナリーは候補にしない（B-5）。
    # ★ 仮U-42／仮D-59  旗が True のとき二階も保持辺の候補に入れる（SPEC_B0B2:151 の改訂）。
    #   既定は False で、従来どおり一階だけ。★ 役割ユナリーは依然として候補にしない。
    _holdout_levels = (1, 2) if holdout_include_second_order else (1,)
    holdout_candidates = [relation_ids[path] for _, (level, path, _, _) in skeleton if level in _holdout_levels]
    holdout_candidates.append(relation_ids["mediator"])
    if has_peripheral:
        peripheral_id = opaque_id(run_seed, trial_index, "relation:peripheral")
        relations.append(
            Relation(peripheral_id, str(motif_row["peripheral"]), (entity_ids["a"], entity_ids["peripheral_entity"]))
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


def _motif_for_trial(run_seed: str | int, trial_index: int, motif_names: tuple[str, ...]) -> str:
    block_index, offset = divmod(trial_index, len(motif_names))
    motifs = list(motif_names)
    _block_rng(run_seed, block_index).shuffle(motifs)
    return motifs[offset]


def _block_rng(run_seed: str | int, block_index: int) -> Random:
    material = f"{run_seed}\x1fblock:{block_index}\x1fmotif_order".encode("utf-8")
    return Random(int.from_bytes(sha256(material).digest(), "big"))


def _u_coin(run_seed: str | int, agent_id: str, trial_index: int) -> float:
    material = f"{run_seed}\x1f{agent_id}\x1f{trial_index}\x1fu".encode("utf-8")
    integer = int.from_bytes(sha256(material).digest()[:8], "big")
    return integer / 2**64
