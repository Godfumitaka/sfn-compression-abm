from __future__ import annotations

import inspect
import json
import subprocess
import sys

from abm import perturbations, seeds
from abm.domains import Abstain, EdgePrediction, Entity, Relation, RelationGraph
from abm.sme import apply_threshold, map_graphs, project, prototype_prior_score


def _role_divergence_mapping(weight: float = 1.0):
    seed = seeds.solar_system_atom()
    agent_input = perturbations.role_divergence(seed, perturbations.PerturbationParams()).agent_input
    return seed, agent_input, map_graphs(
        agent_input.base_graph,
        agent_input.target_graph_partial,
        prototype=seed.target_graph,
        prototype_prior_weight=weight,
    )


def _projection_support(relation_id: str, graph: RelationGraph, relation_mapping: dict[str, str]) -> float:
    return sum(
        1.0
        for relation in graph.relations
        if relation.relation_id != relation_id
        and relation_id in relation.arguments
        and relation.relation_id in relation_mapping
    )


def _ranked_candidates(mapping, agent_input, weight: float):
    by_id = {relation.relation_id: relation for relation in agent_input.base_graph.relations}
    ranked = []
    for relation_id in mapping.alignment.candidate_projections:
        relation = by_id[relation_id]
        arguments = tuple(mapping.alignment.entity_mapping[arg] for arg in relation.arguments)
        rank = _projection_support(relation_id, agent_input.base_graph, dict(mapping.alignment.relation_mapping))
        rank += weight * mapping.alignment.prototype_prior_terms.get(relation_id, 0.0)
        ranked.append((rank, relation_id, relation.predicate, arguments))
    return tuple(sorted(ranked, key=lambda item: (-item[0], item[1])))


def _rename_graph(graph: RelationGraph, mapping: dict[str, str]) -> RelationGraph:
    relation_ids = {relation.relation_id for relation in graph.relations}
    return RelationGraph(
        graph_id=f"renamed_{graph.graph_id}",
        entities=tuple(Entity(mapping.get(entity.entity_id, entity.entity_id), entity.label, entity.attributes) for entity in graph.entities),
        relations=tuple(
            Relation(
                relation.relation_id,
                relation.predicate,
                tuple(argument if argument in relation_ids else mapping.get(argument, argument) for argument in relation.arguments),
                relation.attributes,
            )
            for relation in graph.relations
        ),
    )


def test_project_uses_prototype_prior_inside_single_rank_without_changing_threshold_gate():
    seed, agent_input, mapping = _role_divergence_mapping(weight=2.0)
    structural = map_graphs(agent_input.base_graph, agent_input.target_graph_partial)

    assert project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial) == project(
        structural.alignment, agent_input.base_graph, agent_input.target_graph_partial
    )
    assert isinstance(project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial), Abstain)

    decision = apply_threshold(mapping, mapping.alignment.total_score + 0.25)
    assert decision.accepted is False
    assert mapping.alignment.total_score == mapping.alignment.score_breakdown["structural_score"] + 2.0 * mapping.alignment.score_breakdown["prototype_prior_score"]


def test_role_divergence_positive_weight_selects_highest_derived_rank_candidate():
    _, agent_input, mapping = _role_divergence_mapping(weight=1.0)

    zero = project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial, prototype_prior_weight=0.0)
    weighted = project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial, prototype_prior_weight=1.0)
    expected = _ranked_candidates(mapping, agent_input, 1.0)[0]

    assert isinstance(zero, Abstain)
    assert zero.reason == "ambiguous_projection"
    assert isinstance(weighted, EdgePrediction)
    assert (weighted.edge.predicate, weighted.edge.arguments) == (expected[2], expected[3])
    assert (weighted.edge.predicate, weighted.edge.arguments) == ("revolves_around", ("electron", "nucleus"))


def test_role_divergence_conflict_terms_are_lower_than_non_contradicting_canonical_candidate():
    _, _, mapping = _role_divergence_mapping(weight=1.0)
    terms = mapping.alignment.prototype_prior_terms

    by_id = {relation.relation_id: relation for relation in seeds.solar_system_atom().base_graph.relations}
    unary_terms = [terms[relation_id] for relation_id in mapping.alignment.candidate_projections if len(by_id[relation_id].arguments) == 1]
    binary_terms = [terms[relation_id] for relation_id in mapping.alignment.candidate_projections if len(by_id[relation_id].arguments) == 2]

    assert unary_terms
    assert binary_terms
    assert max(unary_terms) < min(binary_terms)


def test_isomorphic_positive_weight_does_not_create_spurious_abstain_or_change_prediction_content():
    seed = seeds.solar_system_atom()
    agent_input = perturbations.isomorphic(seed, perturbations.PerturbationParams()).agent_input
    unweighted = map_graphs(agent_input.base_graph, agent_input.target_graph_partial, prototype=seed.target_graph, prototype_prior_weight=0.0)
    weighted = map_graphs(agent_input.base_graph, agent_input.target_graph_partial, prototype=seed.target_graph, prototype_prior_weight=1.0)

    p0 = project(unweighted.alignment, agent_input.base_graph, agent_input.target_graph_partial, prototype_prior_weight=0.0)
    p1 = project(weighted.alignment, agent_input.base_graph, agent_input.target_graph_partial, prototype_prior_weight=1.0)

    assert isinstance(p0, EdgePrediction)
    assert isinstance(p1, EdgePrediction)
    assert (p1.edge.predicate, p1.edge.arguments) == (p0.edge.predicate, p0.edge.arguments)


def test_entity_renaming_preserves_rank_ordering_and_renames_selected_prediction():
    seed, agent_input, mapping = _role_divergence_mapping(weight=1.0)
    rename = {entity.entity_id: f"renamed_{index}" for index, entity in enumerate((*agent_input.base_graph.entities, *seed.target_graph.entities), start=1)}
    renamed_base = _rename_graph(agent_input.base_graph, rename)
    renamed_target = _rename_graph(agent_input.target_graph_partial, rename)
    renamed_prototype = _rename_graph(seed.target_graph, rename)

    renamed_mapping = map_graphs(renamed_base, renamed_target, prototype=renamed_prototype, prototype_prior_weight=1.0)
    original_order = tuple((rank, relation_id, predicate) for rank, relation_id, predicate, _ in _ranked_candidates(mapping, agent_input, 1.0))
    renamed_order = tuple((rank, relation_id, predicate) for rank, relation_id, predicate, _ in _ranked_candidates(renamed_mapping, type("AI", (), {"base_graph": renamed_base})(), 1.0))

    original_prediction = project(mapping.alignment, agent_input.base_graph, agent_input.target_graph_partial, prototype_prior_weight=1.0)
    renamed_prediction = project(renamed_mapping.alignment, renamed_base, renamed_target, prototype_prior_weight=1.0)

    assert original_order == renamed_order
    assert isinstance(original_prediction, EdgePrediction)
    assert isinstance(renamed_prediction, EdgePrediction)
    assert renamed_prediction.edge.predicate == original_prediction.edge.predicate
    assert renamed_prediction.edge.arguments == tuple(rename[arg] for arg in original_prediction.edge.arguments)


def test_stage11c2_signatures_remain_oracle_free():
    forbidden = {"oracle_view", "scoring_key", "G_star", "held_out_edge", "target_type", "seed_id"}
    assert forbidden.isdisjoint(inspect.signature(prototype_prior_score).parameters)
    assert forbidden.isdisjoint(inspect.signature(project).parameters)


def test_project_rank_is_deterministic_across_python_hash_seeds():
    code = """
import json
from abm import perturbations, seeds
from abm.sme import map_graphs, project
s=seeds.solar_system_atom()
ai=perturbations.role_divergence(s, perturbations.PerturbationParams()).agent_input
m=map_graphs(ai.base_graph, ai.target_graph_partial, prototype=s.target_graph, prototype_prior_weight=1.0)
p=project(m.alignment, ai.base_graph, ai.target_graph_partial, prototype_prior_weight=1.0)
r=[]
by={x.relation_id:x for x in ai.base_graph.relations}
for rid in m.alignment.candidate_projections:
    rel=by[rid]
    r.append([rid, m.alignment.prototype_prior_terms[rid], rel.predicate, [m.alignment.entity_mapping[a] for a in rel.arguments]])
print(json.dumps({"prediction": [p.edge.predicate, list(p.edge.arguments)], "terms": r}, sort_keys=True))
"""
    outputs = []
    for hash_seed in ("1", "37"):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": hash_seed, "PYTHONPATH": "."},
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1]
