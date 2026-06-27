"""BUILD ORDER 第7段の MDL 風・記述長モジュール。

公開入力と公開入力から作られた SME 対応だけを使い、観測済み relation の
符号化コストを返す。ここで返す値は分析・ログ用であり、SME の
``total_score >= threshold`` 判定や予測の当否には接続しない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from abm.domains import AgentInput, Relation, RelationGraph
from abm.sme import Alignment, MappingResult, ThresholdDecision


@dataclass(frozen=True, slots=True)
class MDLParams:
    """固定 codebook の単純な価格表。"""

    relation_base_cost: float = 1.0
    entity_mapping_cost: float = 1.0
    predicate_mapping_cost: float = 1.0
    unexplained_relation_cost: float = 2.0
    structural_complexity_weight: float = 1.0


@dataclass(frozen=True, slots=True)
class CodeLengthBreakdown:
    """合計記述長を構成する加法的な内訳。"""

    hypothesis_cost: float
    observed_data_cost: float
    unexplained_observation_cost: float
    structural_complexity_cost: float
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", dict(sorted(self.details.items())))


@dataclass(frozen=True, slots=True)
class DescriptionLength:
    """合計記述長と内訳。"""

    total: float
    breakdown: CodeLengthBreakdown

    def __post_init__(self) -> None:
        assert self.total == _breakdown_total(self.breakdown)


@dataclass(frozen=True, slots=True)
class MDLResult:
    """観測済み target relation に対する MDL 風の集計結果。"""

    description_length: DescriptionLength
    n_observed_relations: int
    n_explained_observed_relations: int
    n_unexplained_observed_relations: int
    explained_observed_content: tuple[tuple[str, tuple[str, ...]], ...] = ()
    unexplained_observed_content: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "explained_observed_content",
            tuple(sorted(self.explained_observed_content)),
        )
        object.__setattr__(
            self,
            "unexplained_observed_content",
            tuple(sorted(self.unexplained_observed_content)),
        )


def hypothesis_cost(
    agent_input: AgentInput,
    mapping_or_alignment: MappingResult | Alignment | ThresholdDecision | None,
    params: MDLParams | None = None,
) -> tuple[float, float, Mapping[str, Any]]:
    """候補対応そのものを符号化するコストを公開情報だけから計算する。"""

    codebook = params or MDLParams()
    alignment = _extract_alignment(mapping_or_alignment)
    if alignment is None:
        details = {
            "mapped_entities": 0,
            "mapped_predicates": 0,
            "mapped_relations": 0,
            "structural_relations": 0,
        }
        return 0.0, 0.0, details

    base_relations = _relations_by_id(agent_input.base_graph)
    mapped_base_ids = tuple(sorted(alignment.relation_mapping))
    mapped_predicates = tuple(
        sorted(
            {
                base_relations[relation_id].predicate
                for relation_id in mapped_base_ids
                if relation_id in base_relations
            }
        )
    )
    structural_relations = tuple(sorted((*mapped_base_ids, *alignment.candidate_projections)))
    structural_complexity_cost = (
        codebook.structural_complexity_weight
        * codebook.relation_base_cost
        * len(set(structural_relations))
    )
    mapping_cost = (
        codebook.entity_mapping_cost * len(alignment.entity_mapping)
        + codebook.predicate_mapping_cost * len(mapped_predicates)
    )
    details = {
        "mapped_entities": len(alignment.entity_mapping),
        "mapped_predicates": len(mapped_predicates),
        "mapped_relations": len(mapped_base_ids),
        "structural_relations": len(set(structural_relations)),
    }
    return mapping_cost, structural_complexity_cost, details


def observed_data_cost(
    agent_input: AgentInput,
    mapping_or_alignment: MappingResult | Alignment | ThresholdDecision | None,
    params: MDLParams | None = None,
) -> tuple[float, float, int, int, tuple[tuple[str, tuple[str, ...]], ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    """観測済み target relation だけを、説明済みコストと未説明コストに分ける。"""

    codebook = params or MDLParams()
    observed_content = _relation_content(agent_input.target_graph_partial)
    explained_content = _explained_content(
        agent_input.base_graph,
        agent_input.target_graph_partial,
        _extract_alignment(mapping_or_alignment),
    )
    explained = tuple(sorted(observed_content.intersection(explained_content)))
    unexplained = tuple(sorted(observed_content.difference(explained_content)))
    explained_cost = codebook.relation_base_cost * len(explained)
    unexplained_cost = codebook.unexplained_relation_cost * len(unexplained)
    return explained_cost, unexplained_cost, len(explained), len(unexplained), explained, unexplained


def description_length(
    agent_input: AgentInput,
    mapping_or_alignment: MappingResult | Alignment | ThresholdDecision | None = None,
    params: MDLParams | None = None,
) -> MDLResult:
    """公開入力と任意の公開対応から、分析用の記述長を返す。"""

    codebook = params or MDLParams()
    hypothesis, structural, hypothesis_details = hypothesis_cost(
        agent_input,
        mapping_or_alignment,
        codebook,
    )
    (
        observed_cost,
        unexplained_cost,
        n_explained,
        n_unexplained,
        explained,
        unexplained,
    ) = observed_data_cost(
        agent_input,
        mapping_or_alignment,
        codebook,
    )
    breakdown = CodeLengthBreakdown(
        hypothesis_cost=hypothesis,
        observed_data_cost=observed_cost,
        unexplained_observation_cost=unexplained_cost,
        structural_complexity_cost=structural,
        details=hypothesis_details,
    )
    total = _breakdown_total(breakdown)
    return MDLResult(
        description_length=DescriptionLength(total=total, breakdown=breakdown),
        n_observed_relations=len(agent_input.target_graph_partial.relations),
        n_explained_observed_relations=n_explained,
        n_unexplained_observed_relations=n_unexplained,
        explained_observed_content=explained,
        unexplained_observed_content=unexplained,
    )


def _extract_alignment(
    mapping_or_alignment: MappingResult | Alignment | ThresholdDecision | None,
) -> Alignment | None:
    if isinstance(mapping_or_alignment, MappingResult):
        return mapping_or_alignment.alignment
    if isinstance(mapping_or_alignment, Alignment):
        return mapping_or_alignment
    return None


def _breakdown_total(breakdown: CodeLengthBreakdown) -> float:
    return (
        breakdown.hypothesis_cost
        + breakdown.observed_data_cost
        + breakdown.unexplained_observation_cost
        + breakdown.structural_complexity_cost
    )


def _explained_content(
    base_graph: RelationGraph,
    target_graph_partial: RelationGraph,
    alignment: Alignment | None,
) -> frozenset[tuple[str, tuple[str, ...]]]:
    if alignment is None:
        return frozenset()

    base_relation_ids = _relation_ids(base_graph)
    target_relation_ids = _relation_ids(target_graph_partial)
    explained: set[tuple[str, tuple[str, ...]]] = set()
    for relation in sorted(base_graph.relations, key=_relation_key):
        mapped_arguments = _map_arguments(
            relation,
            base_relation_ids,
            target_relation_ids,
            alignment.entity_mapping,
            alignment.relation_mapping,
        )
        if mapped_arguments is not None:
            explained.add((relation.predicate, mapped_arguments))
    return frozenset(explained)


def _map_arguments(
    relation: Relation,
    base_relation_ids: frozenset[str],
    target_relation_ids: frozenset[str],
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
) -> tuple[str, ...] | None:
    mapped: list[str] = []
    for argument in relation.arguments:
        if argument in base_relation_ids:
            target_relation_id = relation_mapping.get(argument)
            if target_relation_id is None or target_relation_id not in target_relation_ids:
                return None
            mapped.append(target_relation_id)
        else:
            target_entity_id = entity_mapping.get(argument)
            if target_entity_id is None:
                return None
            mapped.append(target_entity_id)
    return tuple(mapped)


def _relations_by_id(graph: RelationGraph) -> dict[str, Relation]:
    return {relation.relation_id: relation for relation in sorted(graph.relations, key=_relation_key)}


def _relation_ids(graph: RelationGraph) -> frozenset[str]:
    return frozenset(relation.relation_id for relation in graph.relations)


def _relation_content(graph: RelationGraph) -> frozenset[tuple[str, tuple[str, ...]]]:
    return frozenset(
        (relation.predicate, tuple(relation.arguments))
        for relation in sorted(graph.relations, key=_relation_key)
    )


def _relation_key(relation: Relation) -> tuple[str, str, tuple[str, ...]]:
    return (relation.predicate, relation.relation_id, tuple(relation.arguments))
