"""指示9のq・max・注意・誕生・入力の境界を、小さな手例で検査する。"""
from dataclasses import replace
from types import SimpleNamespace as NS
import copy
import json
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import pytest
import useforget as D
import useforget_cstar as N
import v39
import cstar_runtime as C
import cstar_probability as CP
import attnsme
import attnposition_keys as K
from abm.definition import Constituent, FrequencyTable
from abm.domains import Entity, Relation, RelationGraph, EdgePrediction


def fresh():
    return dict(S={}, used_t=set(), n_use={}, born={}, t=2, rec={'uses':[], 'struct':[], 'answer':None},
                stats={'uses':0, 'no_candidate_below_tau':0}, tau=.4)


@pytest.fixture
def case(monkeypatch, tmp_path):
    for module, names in [(D, ('ST', '_record_matching', '_record_answer', '_birth')),
                           (v39, ('CFG', '_POW', 'run_conversions')),
                           (C, ('CFG', 'CTX')), (N, ('AUDIT',)), (attnsme, ('ST',))]:
        for name in names:
            value = getattr(module, name)
            monkeypatch.setattr(module, name, {} if isinstance(value, dict) else value)
    monkeypatch.setattr(CP, 'BACKGROUND_SOURCE', None)
    v39.CFG.update(decay=(.5,) * 16, u_abstain=False)
    monkeypatch.setattr(v39, 'run_conversions', lambda state, trial: (state, ()))
    D.ST.update(fresh())
    C.CFG.update(match_eps='0', h_dirichlet=1, logp_eps=.01)
    attnsme.ST['individual'] = {'a':{}}
    row = Constituent(0, 0, Relation('s', 'a', ('x',)), True)
    definition = NS(name='D', registered_at=0, constituents=(row,))
    state = NS(definitions={'D':definition}, slot_history={('D',0):{'a':9}},
               p_hat=FrequencyTable({'a':8, 'b':2}, 10, .1, frozenset({'a','b'})))
    scene = RelationGraph('scene', (Entity('u'),), (Relation('t','a',('u',)),))
    config = NS(local_lambda=1., higher_order_predicates=frozenset())
    C.CTX.update(enabled=True, config=config)
    res = (1.,1,definition,None,NS(relation_mapping={'s':'t'}),1,False,())
    yield state, scene, config, res, tmp_path
    if N.AUDIT.get('f') is not None:
        N.close()


def legacy_snapshot():
    return json.dumps(dict(S=[[list(k),v] for k,v in D.ST['S'].items()],
                           n_use=[[list(k),v] for k,v in D.ST['n_use'].items()],
                           stats=D.ST['stats'], rec=D.ST['rec']), ensure_ascii=False).encode()


@pytest.mark.parametrize('attention', [False, True])
def test_q_one_and_zero_attention_keep_legacy_bytes(case, attention):
    state, scene, config, res, root = case
    D._record_matching(state, scene, res)
    old = legacy_snapshot()
    D.ST.clear(); D.ST.update(fresh())
    attnsme.ST['individual']['a'] = {'unseen':0.0}
    N.install(root/'audit.jsonl', expected_usage=True, attention_usage=attention)
    D._record_matching(state, scene, res)
    assert legacy_snapshot() == old


def test_zero_q_does_not_touch_existing_record(case):
    state, scene, config, res, root = case
    scene = replace(scene, relations=(Relation('t','b',('u',)),))
    D.ST['S'][('D',0,0)] = (0, [1.] * 16)
    old = copy.deepcopy(D.ST)
    N.install(root/'audit.jsonl', expected_usage=True)
    D._record_matching(state, scene, res)
    assert D.ST == old
    assert N.AUDIT['matching'][0]['q'] == 0.


@pytest.mark.parametrize('epsilon_mode', ['0', 'shared'])
def test_positive_H_q_uses_exact_native_distribution(case, epsilon_mode):
    state, scene, config, res, root = case
    d = res[2]; d.constituents = (replace(d.constituents[0], alive=False),)
    scene = replace(scene, relations=(Relation('t','b',('u',)),))
    before = repr(state), repr(scene)
    C.CFG['match_eps'] = epsilon_mode
    q = C.distributions(d, d.constituents[0], state, scene, config)['P' if epsilon_mode == 'shared' else 'q']['H']['b']
    assert q > 0 and 'b' not in state.slot_history['D',0]
    N.install(root/'audit.jsonl', expected_usage=True)
    D._record_matching(state, scene, res)
    assert D.ST['S']['D',0,0] == (2, [q] * 16)
    assert (repr(state), repr(scene)) == before


@pytest.mark.parametrize('matching,answer', [(.2,1.), (1.,1.), (1.5,1.)])
def test_same_trial_uses_max_once_and_next_trial_decays(case, matching, answer):
    N.AUDIT.update(trial=None)
    key = ('D',0,0)
    N.use_amount(key,2,matching); N.use_amount(key,2,answer)
    assert D.ST['S'][key] == (2,[max(matching,answer)] * 16)
    assert D.ST['n_use'][key] == 1 and D.ST['stats']['uses'] == 1
    D.ST['used_t'].clear()
    N.use_amount(key,3,.3)
    assert D.ST['S'][key] == (3,[max(matching,answer)*.5+.3] * 16)
    assert D.ST['n_use'][key] == 2


def test_fixed_mean_changes_only_the_target_seat(case):
    before = {'target':1., 'untouched':1., 'unused':2.}
    after = {'target':2., 'untouched':1., 'unused':1.}
    keys = ['target','untouched']
    amounts_before = [N.attention_weight(k,before)[0]*.4 for k in keys]
    amounts_after = [N.attention_weight(k,after)[0]*.4 for k in keys]
    assert amounts_after[0] > amounts_before[0]
    assert amounts_after[1] == amounts_before[1]
    assert N.attention_weight(None,after)[0] == 1.
    assert N.attention_weight('absent',after)[0] == 1/(1+sum(after.values())/len(after))
    assert N.attention_weight('absent',{})[0] == 1.


def test_native_k2_weight_changes_only_matching_seat_strength(case):
    state, scene, config, res, root = case
    definition = res[2]
    definition.constituents += (Constituent(1,0,Relation('s2','a',('x','y')),True),)
    scene = RelationGraph('scene',(Entity('u'),Entity('v')),
                          (Relation('t','a',('u',)),Relation('t2','a',('u','v'))))
    res = (1.,2,definition,None,NS(relation_mapping={'s':'t','s2':'t2'}),2,False,())
    index = K.position_index([r.to_dict() for r in scene.relations], {'u','v'})
    first, second = index['keys']['t'], index['keys']['t2']
    attnsme.ST['individual']['a'] = {first:1.,second:1.,'unused':2.}
    N.install(root/'audit.jsonl', expected_usage=True, attention_usage=True)
    D._record_matching(state, scene, res)
    before = copy.deepcopy(D.ST['S'])
    D.ST.clear(); D.ST.update(fresh()); N.AUDIT['trial'] = None
    attnsme.ST['individual']['a'] = {first:2.,second:1.,'unused':1.}
    D._record_matching(state, scene, res)
    assert D.strength(D.ST['S']['D',0,0],2) > D.strength(before['D',0,0],2)
    assert D.ST['S']['D',1,0] == before['D',1,0]
    assert all(r['key'] == index['keys'][r['mapped_to']] for r in N.AUDIT['matching'])


def test_birth_stays_one_without_attention_weight(case):
    root = case[-1]
    attnsme.ST['individual']['a'] = {'key':10.}
    N.install(root/'audit.jsonl', expected_usage=True, attention_usage=True)
    D._birth(('D',0,0),2)
    assert D.ST['S']['D',0,0] == (2,[1.] * 16)
    assert D.ST['born']['D',0,0] == 2 and D.ST['n_use']['D',0,0] == 0


def test_answer_one_is_unweighted_and_updates_same_seat_by_max(case):
    state, scene, config, res, root = case
    C.CFG['match_eps'] = 'shared'
    attnsme.ST['individual']['a'] = {'unused':10.}
    N.install(root/'audit.jsonl', expected_usage=True, attention_usage=True)
    D._record_matching(state, scene, res)
    prediction = EdgePrediction(Relation('sme_projection__s','a',('u',)))
    D._record_answer(state, NS(prediction=prediction,trace={'R_used':'D'}))
    assert D.ST['S']['D',0,0] == (2,[1.] * 16)
    assert D.ST['n_use']['D',0,0] == 1


def test_U_and_hidden_positions_only_record_structure(case):
    state, scene, config, res, root = case
    res[2].constituents = (replace(res[2].constituents[0], alive=False),)
    state.slot_history.clear()
    N.install(root/'audit.jsonl', expected_usage=True)
    D._record_matching(state, scene, res)
    assert not D.ST['S'] and D.ST['rec']['struct'] == [[0,'U']]


def test_abstention_does_not_remove_pre_gate_matching_use(case):
    state, scene, config, res, root = case
    N.install(root/'audit.jsonl', expected_usage=True)
    D._record_matching(state, scene, res)
    assert D.ST['S']['D',0,0] == (2,[1.] * 16)
