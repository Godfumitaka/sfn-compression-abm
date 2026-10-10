"""指示22：実受領の出所と、元assert・全観察・注意・乱数の不変。"""
import ast
from copy import deepcopy
from pathlib import Path
import pickle
from random import Random
from types import SimpleNamespace as NS

import pytest
import abm.loop as loop
from abm.domains import CorrectnessBit, Relation, RevealedEdge
import attnsme as attention
import smeshared as shared
import useforget_evaluation as evaluation
import attn_probe_names_instruction22 as receipts_module


def input_with(name):
    return NS(target_graph_partial=NS(relations=(Relation('r', name, ('e',)),),
                                     entities=(NS(entity_id='e'),)))


@pytest.fixture
def installed(monkeypatch, tmp_path):
    for module, names in ((loop, ('_agent_input', 'update', 'predict', '_ledger_record')),
                          (shared, ('_definition_choice',))):
        for name in names:
            monkeypatch.setattr(module, name, getattr(module, name))
    monkeypatch.setattr(evaluation, '_DEPTH', 0)
    monkeypatch.setattr(loop, '_agent_input', lambda trial, before: trial.actual_input)
    monkeypatch.setattr(loop, 'update', lambda pending, feedback: pending)
    definition = NS(name='definition', constituents=(), registered_at=0)
    ranking = [(0, 1, definition, None, NS(relation_mapping={}), 1, 1)]
    monkeypatch.setattr(shared, '_definition_choice', lambda ranked, scene: (ranked[0], False))

    def native_predict(ai, state, config, rng):
        return shared._definition_choice(ranking, []), None

    monkeypatch.setattr(loop, 'predict', native_predict)
    attention.install(tmp_path/'attention.gz', mode='global', position='k2', eta=.1,
                      task_instruction=lambda trial: True, research_record=lambda *args: {},
                      feature_policy=lambda *args: ([{'m': {}}], {}, {}))
    original_probe = attention.ST['predict_probe']
    receipts = receipts_module.install(attention)
    state = NS(p_hat=NS(counts={'old': 1}, total=1, lambda_mix=0., alive_vocab={'old'}))
    config = NS(higher_order_predicates=(), local_lambda=0.)
    loop._agent_input(NS(trial=99, actual_input=input_with('visible')), state)
    observations = attention.ST['individual']['observations']
    observations.names.add('old')
    observations.last_trial = 98
    attention.ST['individual']['a']['key'] = .25
    yield state, config, receipts, original_probe
    attention.ST['f'].close()


def run_probe(state, config, function=None):
    function = attention.ST['predict_probe'] if function is None else function
    return function(input_with('probe_only'), state, config, Random(7), instruction=True)


def test_original_assert_reproduced_and_only_real_visible_receipt_added(installed):
    state, config, receipts, original_probe = installed
    state.p_hat.counts['visible'] = 1
    with pytest.raises(AssertionError):
        run_probe(state, config, original_probe)
    before = pickle.dumps(attention.ST['individuals'])
    result = run_probe(state, config)
    assert result[0][0][2].name == 'definition'
    assert receipts['agent'] == {'trial': 99, 'names': {'visible'}}
    assert pickle.dumps(attention.ST['individuals']) == before
    assert attention.ST['individual']['observations'].names == {'old'}


@pytest.mark.parametrize('foreign', ['unreceived', 'probe_only'])
def test_original_assert_still_rejects_unreceived_and_fixed_probe_names(installed, foreign):
    state, config, receipts, original_probe = installed
    state.p_hat.counts[foreign] = 1
    before = pickle.dumps(attention.ST['individuals'])
    with pytest.raises(AssertionError):
        run_probe(state, config)
    assert pickle.dumps(attention.ST['individuals']) == before
    assert receipts['agent']['names'] == {'visible'}


def test_only_actual_accepted_revealed_edge_can_supply_a_disclosed_name(installed):
    state, config, receipts, original_probe = installed
    assert loop.update(state, CorrectnessBit(True)) is state
    assert receipts['agent']['names'] == {'visible'}
    assert loop.update(state, RevealedEdge(Relation('d', 'disclosed', ('e',)))) is state
    state.p_hat.counts['disclosed'] = 1
    before = pickle.dumps(attention.ST['individuals'])
    run_probe(state, config)
    assert receipts['agent']['names'] == {'visible', 'disclosed'}
    assert pickle.dumps(attention.ST['individuals']) == before


def test_probe_and_counterfactual_cannot_update_receipts(installed):
    state, config, receipts, original_probe = installed
    before = deepcopy(receipts)
    with evaluation.evaluation():
        loop._agent_input(NS(trial=900, actual_input=input_with('synthetic')), state)
        loop.update(state, RevealedEdge(Relation('d', 'synthetic_disclosure', ('e',))))
    assert receipts == before


def test_matching_predictions_attention_observations_and_random_state_unchanged(installed):
    state, config, receipts, original_probe = installed
    before = pickle.dumps(attention.ST['individuals'])
    rng = Random(23)
    rng_before = rng.getstate()
    ai = input_with('probe_only')
    left = original_probe(ai, state, config, rng, instruction=False)
    right = attention.ST['predict_probe'](ai, state, config, rng, instruction=False)
    assert left == right and rng.getstate() == rng_before
    assert pickle.dumps(attention.ST['individuals']) == before
    assert attention.ST['trial'] == 99


def test_missing_or_stale_receipts_are_not_invented(installed):
    state, config, receipts, original_probe = installed
    receipts['agent']['trial'] = 98
    with pytest.raises(RuntimeError, match='受領記録'):
        run_probe(state, config)
    receipts.clear()
    with pytest.raises(RuntimeError, match='受領記録'):
        run_probe(state, config)


def test_original_asserts_and_name_readers_are_preserved():
    tree = ast.parse(Path(attention.__file__).read_text())
    name_reads = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                  and node.attr == 'names' and isinstance(node.ctx, ast.Load)]
    asserts = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    assert len(name_reads) == 3
    assert all(any(node in list(ast.walk(check)) for check in asserts) for node in name_reads)
    # 入力と実開示以外を読む追加入口を、構造で拒否する。
    added = ast.parse(Path(receipts_module.__file__).read_text())
    attributes = {node.attr for node in ast.walk(added) if isinstance(node, ast.Attribute)}
    assert not attributes & {'p_hat', 'counts', 'held_out_edge', 'G_star', 'target_type', 'seed_id'}
