"""BUILD ORDER 第6段の SME 風・離散写像エンジン。

公開された base graph と partial graph だけから alignment を作り、単一の
``total_score >= threshold`` 判定を通った場合だけ候補 relation を投影する。
エンティティ名や注釈メタデータには依存せず、predicate・arity・argument 位置の
整合性と高階 relation の接続保存だけを使う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Mapping

from abm.domains import Abstain, AgentInput, EdgePrediction, Prediction, Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class SMEParams:
    """oracle-free な写像スコア重み。threshold はここには入れない。"""

    predicate_match_weight: float = 4.0
    argument_consistency_weight: float = 1.0
    higher_order_weight: float = 2.0
    unmatched_penalty: float = 0.25


@dataclass(frozen=True, slots=True)
class Alignment:
    """base 側から partial 側への対応集合と構造スコア。"""

    entity_mapping: Mapping[str, str]
    relation_mapping: Mapping[str, str]
    total_score: float
    score_breakdown: Mapping[str, float]
    systematicity_contribution: float
    matched_predicates_count: int
    unmatched_count: int
    candidate_projections: tuple[str, ...] = ()
    prototype_prior_terms: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_mapping", dict(sorted(self.entity_mapping.items())))
        object.__setattr__(self, "relation_mapping", dict(sorted(self.relation_mapping.items())))
        object.__setattr__(self, "score_breakdown", dict(sorted(self.score_breakdown.items())))
        terms = dict(sorted(self.prototype_prior_terms.items()))
        object.__setattr__(self, "prototype_prior_terms", terms)
        object.__setattr__(self, "candidate_projections", tuple(sorted(self.candidate_projections)))




@dataclass(frozen=True, slots=True)
class PrototypePriorParams:
    """prototype prior 内部の暫定係数。外側の設定重みとは分離する。"""

    theta: float = 1.0
    conflict_beta: float = 0.5
    size_exponent: float = 1.0


@dataclass(frozen=True, slots=True)
class PrototypePriorResult:
    """候補ごとに分解可能な prototype prior の結果。"""

    total: float
    per_candidate: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "per_candidate", dict(sorted(self.per_candidate.items())))


@dataclass(frozen=True, slots=True)
class AlignmentCandidate:
    """relation pair を一つ追加したときの中間候補。"""

    base_relation_id: str
    partial_relation_id: str
    predicate: str
    arity: int
    entity_pairs: tuple[tuple[str, str], ...]
    relation_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class MappingResult:
    """写像器の結果。候補が無い場合も alignment は空で返す。"""

    alignment: Alignment
    candidates: tuple[AlignmentCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class ThresholdDecision:
    """単一 threshold 判定の結果。"""

    accepted: bool
    total_score: float
    threshold: float


def map_graphs(
    base_graph: RelationGraph,
    target_graph_partial: RelationGraph,
    params: SMEParams | None = None,
    *,
    prototype: RelationGraph | None = None,
    prototype_prior_weight: float = 0.0,
) -> MappingResult:
    """観測済み二グラフだけから、決定的な greedy alignment を作る。"""

    weights = params or SMEParams()
    base_relation_ids = _relation_ids(base_graph)
    partial_relation_ids = _relation_ids(target_graph_partial)
    pairs = _alignment_candidates(base_graph, target_graph_partial)
    entity_mapping: dict[str, str] = {}
    used_entities: dict[str, str] = {}
    relation_mapping: dict[str, str] = {}
    used_relations: dict[str, str] = {}
    accepted: list[AlignmentCandidate] = []

    for pair in pairs:
        if pair.base_relation_id in relation_mapping or pair.partial_relation_id in used_relations:
            continue
        if not _candidate_fits(pair, entity_mapping, used_entities, relation_mapping, used_relations):
            continue
        for left, right in pair.entity_pairs:
            entity_mapping[left] = right
            used_entities[right] = left
        for left, right in pair.relation_pairs:
            relation_mapping[left] = right
            used_relations[right] = left
        relation_mapping[pair.base_relation_id] = pair.partial_relation_id
        used_relations[pair.partial_relation_id] = pair.base_relation_id
        accepted.append(pair)

    systematicity = _systematicity_score(base_graph, target_graph_partial, relation_mapping)
    matched = len(accepted)
    unmatched = _unmatched_count(base_graph, relation_mapping)
    argument_score = sum(len(pair.entity_pairs) + len(pair.relation_pairs) for pair in accepted)
    structural_score = (
        weights.predicate_match_weight * matched
        + weights.argument_consistency_weight * argument_score
        + weights.higher_order_weight * systematicity
        - weights.unmatched_penalty * unmatched
    )
    candidate_projections = _projectable_base_relation_ids(
        base_graph,
        target_graph_partial,
        entity_mapping,
        relation_mapping,
        base_relation_ids,
        partial_relation_ids,
    )
    prior = prototype_prior_score(
        entity_mapping=entity_mapping,
        candidate_projections=candidate_projections,
        prototype=prototype,
        base_graph=base_graph,
        target_graph_partial=target_graph_partial,
        enabled=prototype_prior_weight != 0.0,
    )
    total = structural_score + prototype_prior_weight * prior.total
    alignment = Alignment(
        entity_mapping=entity_mapping,
        relation_mapping=relation_mapping,
        total_score=total,
        score_breakdown={
            "predicate_match": weights.predicate_match_weight * matched,
            "argument_consistency": weights.argument_consistency_weight * argument_score,
            "systematicity": weights.higher_order_weight * systematicity,
            "unmatched_penalty": weights.unmatched_penalty * unmatched,
            "structural_score": structural_score,
            "prototype_prior_score": prior.total,
            "prototype_prior_weight": prototype_prior_weight,
            "prototype_prior_contribution": prototype_prior_weight * prior.total,
            "total_score": total,
        },
        systematicity_contribution=systematicity,
        matched_predicates_count=matched,
        unmatched_count=unmatched,
        candidate_projections=candidate_projections,
        prototype_prior_terms=prior.per_candidate,
    )
    return MappingResult(alignment=alignment, candidates=tuple(accepted))


def apply_threshold(mapping_result: MappingResult, threshold: float) -> ThresholdDecision:
    """threshold が作用する唯一の場所: total_score(best_alignment) >= threshold。"""

    score = mapping_result.alignment.total_score
    return ThresholdDecision(accepted=score >= threshold, total_score=score, threshold=threshold)


def project(
    alignment: Alignment,
    base_graph: RelationGraph,
    target_graph_partial: RelationGraph,
) -> Prediction:
    """alignment で partial 側へ写像可能な未観測一階 relation を投影する。"""

    base_relations = _relations_by_id(base_graph)
    partial_relation_ids = _relation_ids(target_graph_partial)
    existing_content = _relation_content(target_graph_partial)
    candidates: list[tuple[float, str, Relation]] = []
    for relation_id in alignment.candidate_projections:
        relation = base_relations[relation_id]
        mapped_arguments = tuple(alignment.entity_mapping[arg] for arg in relation.arguments)
        content = (relation.predicate, mapped_arguments)
        if content in existing_content:
            continue
        contribution = _projection_support(relation, base_graph, alignment.relation_mapping)
        projected = Relation(
            relation_id=f"sme_projection__{relation.relation_id}",
            predicate=relation.predicate,
            arguments=mapped_arguments,
        )
        candidates.append((-contribution, relation.relation_id, projected))
    if not candidates:
        return Abstain(reason="no_projectable_relation")
    ordered = sorted(candidates, key=lambda item: (item[0], item[1]))
    if len(ordered) > 1 and ordered[0][0] == ordered[1][0]:
        return Abstain(reason="ambiguous_projection")
    _ = partial_relation_ids
    return EdgePrediction(edge=ordered[0][2])


def run_sme(
    agent_input: AgentInput,
    params: SMEParams | None = None,
    threshold: float = 0.0,
    *,
    prototype: RelationGraph | None = None,
    prototype_prior_weight: float = 0.0,
) -> Prediction:
    """AgentInput の公開グラフだけで map→threshold→project を実行する。"""

    mapping = map_graphs(
        agent_input.base_graph,
        agent_input.target_graph_partial,
        params,
        prototype=prototype,
        prototype_prior_weight=prototype_prior_weight,
    )
    decision = apply_threshold(mapping, threshold)
    if not decision.accepted:
        return Abstain(reason="below_threshold")
    return project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial)


def _alignment_candidates(
    base_graph: RelationGraph,
    partial_graph: RelationGraph,
) -> tuple[AlignmentCandidate, ...]:
    base_relation_ids = _relation_ids(base_graph)
    partial_relation_ids = _relation_ids(partial_graph)
    candidates: list[AlignmentCandidate] = []
    for left in sorted(base_graph.relations, key=_relation_key):
        for right in sorted(partial_graph.relations, key=_relation_key):
            if left.predicate != right.predicate or len(left.arguments) != len(right.arguments):
                continue
            entity_pairs: list[tuple[str, str]] = []
            relation_pairs: list[tuple[str, str]] = []
            compatible = True
            for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                left_is_relation = left_arg in base_relation_ids
                right_is_relation = right_arg in partial_relation_ids
                if left_is_relation != right_is_relation:
                    compatible = False
                    break
                if left_is_relation:
                    relation_pairs.append((left_arg, right_arg))
                else:
                    entity_pairs.append((left_arg, right_arg))
            if compatible:
                candidates.append(
                    AlignmentCandidate(
                        base_relation_id=left.relation_id,
                        partial_relation_id=right.relation_id,
                        predicate=left.predicate,
                        arity=len(left.arguments),
                        entity_pairs=tuple(sorted(entity_pairs)),
                        relation_pairs=tuple(sorted(relation_pairs)),
                    )
                )
    return tuple(sorted(candidates, key=_candidate_order_key))


def _candidate_order_key(candidate: AlignmentCandidate) -> tuple[int, str, str, str]:
    return (-candidate.arity, candidate.predicate, candidate.base_relation_id, candidate.partial_relation_id)


def _candidate_fits(
    candidate: AlignmentCandidate,
    entity_mapping: Mapping[str, str],
    used_entities: Mapping[str, str],
    relation_mapping: Mapping[str, str],
    used_relations: Mapping[str, str],
) -> bool:
    for left, right in candidate.entity_pairs:
        if left in entity_mapping and entity_mapping[left] != right:
            return False
        if right in used_entities and used_entities[right] != left:
            return False
    for left, right in candidate.relation_pairs:
        if left in relation_mapping and relation_mapping[left] != right:
            return False
        if right in used_relations and used_relations[right] != left:
            return False
    return True


def _projectable_base_relation_ids(
    base_graph: RelationGraph,
    partial_graph: RelationGraph,
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
    base_relation_ids: frozenset[str],
    partial_relation_ids: frozenset[str],
) -> tuple[str, ...]:
    existing = _relation_content(partial_graph)
    result: list[str] = []
    for relation in sorted(base_graph.relations, key=_relation_key):
        if relation.relation_id in relation_mapping:
            continue
        if any(argument in base_relation_ids for argument in relation.arguments):
            continue
        mapped = []
        for argument in relation.arguments:
            if argument not in entity_mapping:
                mapped = []
                break
            mapped.append(entity_mapping[argument])
        if not mapped and relation.arguments:
            continue
        content = (relation.predicate, tuple(mapped))
        if content not in existing:
            result.append(relation.relation_id)
    _ = partial_relation_ids
    return tuple(result)


def _projection_support(
    relation: Relation,
    graph: RelationGraph,
    relation_mapping: Mapping[str, str],
) -> float:
    support = 0.0
    for other in graph.relations:
        if other.relation_id == relation.relation_id:
            continue
        if relation.relation_id in other.arguments and other.relation_id in relation_mapping:
            support += 1.0
    return support


def _systematicity_score(
    base_graph: RelationGraph,
    partial_graph: RelationGraph,
    relation_mapping: Mapping[str, str],
) -> float:
    partial_by_id = _relations_by_id(partial_graph)
    score = 0.0
    for left_id, right_id in sorted(relation_mapping.items()):
        left = _relations_by_id(base_graph)[left_id]
        right = partial_by_id[right_id]
        for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
            if relation_mapping.get(left_arg) == right_arg:
                score += 1.0
    return score


def _unmatched_count(graph: RelationGraph, relation_mapping: Mapping[str, str]) -> int:
    return sum(1 for relation in graph.relations if relation.relation_id not in relation_mapping)


def _relation_ids(graph: RelationGraph) -> frozenset[str]:
    return frozenset(relation.relation_id for relation in graph.relations)


def _relations_by_id(graph: RelationGraph) -> dict[str, Relation]:
    return {relation.relation_id: relation for relation in sorted(graph.relations, key=_relation_key)}


def _relation_content(graph: RelationGraph) -> frozenset[tuple[str, tuple[str, ...]]]:
    return frozenset((relation.predicate, tuple(relation.arguments)) for relation in graph.relations)


def _relation_key(relation: Relation) -> tuple[str, str, tuple[str, ...]]:
    return (relation.predicate, relation.relation_id, tuple(relation.arguments))


def prototype_prior_score(
    *,
    entity_mapping: Mapping[str, str],
    candidate_projections: tuple[str, ...],
    prototype: RelationGraph | None,
    base_graph: RelationGraph,
    target_graph_partial: RelationGraph,
    enabled: bool = True,
    params: PrototypePriorParams | None = None,
) -> PrototypePriorResult:
    """alignment 依存の role correspondence で prototype prior を候補ごとに計算する。"""

    if not enabled or prototype is None or not prototype.relations:
        return PrototypePriorResult(0.0, {relation_id: 0.0 for relation_id in sorted(candidate_projections)})

    weights = params or PrototypePriorParams()
    base_relations = _relations_by_id(base_graph)
    target_signatures = _role_signatures(target_graph_partial)
    prototype_signatures = _role_signatures(prototype)
    target_to_prototype = _role_correspondence(target_signatures, prototype_signatures)
    prototype_relation_patterns = _prototype_relation_patterns(prototype)
    predicate_frequencies = _predicate_frequencies(prototype, base_graph)

    terms: dict[str, float] = {}
    for relation_id in sorted(candidate_projections):
        relation = base_relations[relation_id]
        mapped = tuple(entity_mapping[arg] for arg in relation.arguments)
        correspondent_options = tuple(target_to_prototype.get(entity, ()) for entity in mapped)
        shared = False
        if correspondent_options and all(correspondent_options):
            for prototype_arguments in product(*correspondent_options):
                if prototype_arguments in prototype_relation_patterns.get(relation.predicate, frozenset()):
                    shared = True
                    break
        conflict = _has_visible_role_conflict(
            relation.predicate,
            mapped,
            target_to_prototype,
            prototype_relation_patterns,
            target_graph_partial,
        )
        size_weight = 1.0 / (predicate_frequencies.get(relation.predicate, 0) + 1.0) ** weights.size_exponent
        terms[relation_id] = weights.theta * size_weight * float(shared) - weights.conflict_beta * float(conflict)
    return PrototypePriorResult(sum(terms.values()), terms)


def _role_signatures(graph: RelationGraph) -> dict[str, tuple[tuple[str, int], ...]]:
    relation_ids = _relation_ids(graph)
    entity_ids = sorted(entity.entity_id for entity in graph.entities)
    signatures: dict[str, list[tuple[str, int]]] = {entity_id: [] for entity_id in entity_ids}
    for relation in sorted(graph.relations, key=_relation_key):
        for position, argument in enumerate(relation.arguments):
            if argument in relation_ids:
                continue
            signatures.setdefault(argument, []).append((relation.predicate, position))
    return {entity_id: tuple(sorted(values)) for entity_id, values in sorted(signatures.items())}


def _role_correspondence(
    target_signatures: Mapping[str, tuple[tuple[str, int], ...]],
    prototype_signatures: Mapping[str, tuple[tuple[str, int], ...]],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for target_entity, target_signature in sorted(target_signatures.items()):
        target_roles = frozenset(target_signature)
        matches = [
            prototype_entity
            for prototype_entity, prototype_signature in sorted(prototype_signatures.items())
            if target_roles.issubset(frozenset(prototype_signature))
        ]
        result[target_entity] = tuple(sorted(matches))
    return result


def _prototype_relation_patterns(prototype: RelationGraph) -> dict[str, frozenset[tuple[str, ...]]]:
    relation_ids = _relation_ids(prototype)
    patterns: dict[str, set[tuple[str, ...]]] = {}
    for relation in sorted(prototype.relations, key=_relation_key):
        if any(argument in relation_ids for argument in relation.arguments):
            continue
        patterns.setdefault(relation.predicate, set()).add(tuple(relation.arguments))
    return {predicate: frozenset(sorted(arguments)) for predicate, arguments in sorted(patterns.items())}


def _predicate_frequencies(prototype: RelationGraph, base_graph: RelationGraph) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for graph in (prototype, base_graph):
        for relation in sorted(graph.relations, key=_relation_key):
            frequencies[relation.predicate] = frequencies.get(relation.predicate, 0) + 1
    return dict(sorted(frequencies.items()))


def _has_visible_role_conflict(
    predicate: str,
    mapped_arguments: tuple[str, ...],
    target_to_prototype: Mapping[str, tuple[str, ...]],
    prototype_relation_patterns: Mapping[str, frozenset[tuple[str, ...]]],
    target_graph_partial: RelationGraph,
) -> bool:
    prototype_patterns = prototype_relation_patterns.get(predicate, frozenset())
    if not prototype_patterns:
        return False
    relation_ids = _relation_ids(target_graph_partial)
    mapped_set = set(mapped_arguments)
    for relation in sorted(target_graph_partial.relations, key=_relation_key):
        if relation.predicate != predicate or len(relation.arguments) != len(mapped_arguments):
            continue
        if any(argument in relation_ids for argument in relation.arguments):
            continue
        if not mapped_set.intersection(relation.arguments):
            continue
        options = tuple(target_to_prototype.get(argument, ()) for argument in relation.arguments)
        if all(options) and not any(arguments in prototype_patterns for arguments in product(*options)):
            return True
    return False
