"""位置注意の解析勾配・開示順・既定のN3を変えないこと。"""
import copy
import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import attnposition as P
import attnposition_keys as K


def cs(rows):
    return tuple(P.Candidate(str(i), q, i+1, i, tuple(sorted(m.items())),
                 ('y' if good else 'n', ('a','b')), {'answer': i})
                 for i, (q, m, good) in enumerate(rows))


@pytest.mark.parametrize('rows', [
    [(0.8, {'seal': 1.}, False), (0.6, {'seal': 0.}, True)],
    [(0.8, {'seal': 2., 'other': .1}, False), (0.7, {'seal': .2}, True),
     (.4, {'seal': .6, 'other': 1.2}, True)],
    [(0.7, {'seal': 5.}, False), (.5, {'seal': 2.}, True),
     (.3, {'seal': 1., 'other': 3.}, False)]])
def test_analytic_gradient_finite_difference(rows):
    candidates = cs(rows)
    a = {'seal': .3, 'other': .7}
    loss, gradient, reason = P.loss_gradient(candidates, a, ('y', ('a','b')))
    assert reason is None and math.isfinite(loss)
    for key in gradient:
        plus, minus = dict(a), dict(a)
        plus[key] += 1e-5
        minus[key] -= 1e-5
        numeric = (P.loss_gradient(candidates, plus, ('y', ('a','b')))[0]-
                   P.loss_gradient(candidates, minus, ('y', ('a','b')))[0])/2e-5
        assert gradient[key] == pytest.approx(numeric, abs=2e-10)


def test_current_answer_before_update_and_next_answer_after():
    candidates = cs([(.8, {'seal': 1.}, False), (.6, {'seal': 0.}, True)])
    learner = P.Learner(eta=1.)
    prepared = learner.prepare(0, True, {}, candidates)
    assert prepared.payload == {'answer': 0}
    record = learner.finish(prepared, {'prediction_order': 0, 'f_fired': True,
         'f_realized': .5, 'feedback_content': {'predicate': 'y', 'arguments': ['a','b']}})
    assert record['updated'] and record['a_before']['seal'] == 0
    assert record['answer_before_update'] == {'answer': 0}
    assert learner.prepare(1, True, {}, candidates).payload == {'answer': 1}


def test_non_disclosure_does_not_read_answer():
    class Guard(dict):
        def __getitem__(self, key):
            assert key != 'feedback_content'
            return super().__getitem__(key)
    learner = P.Learner()
    candidates = cs([(.8, {'seal': 1.}, False), (.6, {'seal': 0.}, True)])
    prepared = learner.prepare(0, True, {}, candidates)
    result = learner.finish(prepared, Guard(prediction_order=0, f_fired=False, f_realized=.1))
    assert result['reason'] == 'not_disclosed' and result['L'] is None
    assert result['a_before'] == result['a_after']


def test_non_door_keeps_all_baseline_fields():
    baseline = {'prediction_kind': 'Abstain', 'predicted_edge': None, 'abstain_reason': 'original'}
    learner = P.Learner(fixed_one=True)
    prepared = learner.prepare(0, False, baseline, cs([(.8, {'seal': 1.}, False)]))
    assert prepared.payload is baseline


def test_zero_attention_keeps_n3_and_tie_order():
    candidates = cs([(.8, {}, False), (.8, {'seal': 10.}, True), (.7, {}, False)])
    assert P.select(candidates, {}).name == '1'
    assert P.select(tuple(reversed(candidates)), {}).name == '1'
    for c, z in P.log_scores(candidates, {}):
        assert z == math.log(c.q)


def test_no_correct_candidate_does_not_update():
    learner = P.Learner()
    p = learner.prepare(0, True, {}, cs([(.8, {'seal': 1.}, False)]))
    r = learner.finish(p, {'prediction_order':0,'f_fired':True,'f_realized':1.,
                           'feedback_content':{'predicate':'unknown','arguments':['a','b']}})
    assert r['reason'] == 'no_correct_candidates'
    assert r['a_before'] == r['a_after']


def test_no_rng_memory_or_input_mutation_and_no_positive_q():
    candidates = cs([(0., {'seal': 1.}, True)])
    before = copy.deepcopy(candidates)
    assert P.select(candidates, {}) is None
    assert P.loss_gradient(candidates, {}, ('y', ('a','b')))[2] == 'no_positive_q_candidates'
    assert candidates == before


def test_clipping_and_fixed_one():
    candidates = cs([(.8, {'seal': 100.}, False), (.6, {'seal': 0.}, True)])
    for fixed in (False, True):
        learner = P.Learner(eta=100., fixed_one=fixed)
        p = learner.prepare(0, True, {}, candidates)
        r = learner.finish(p, {'prediction_order':0,'f_fired':True,'f_realized':1.,
                             'feedback_content':{'predicate':'y','arguments':['a','b']}})
        assert learner.attention['seal'] == (1. if fixed else 10.)
        assert r['reason'] == ('fixed_attention_no_learning' if fixed else 'updated')


def test_infinite_mismatch_not_silently_smoothed():
    with pytest.raises(ValueError, match='確率0'):
        P.select(cs([(.8, {'seal': math.inf}, False)]), {})


def test_component_roots_path_shapes_collisions_and_renaming():
    rows = [{'relation_id':'link','arguments':['seal','cause']},
            {'relation_id':'seal','arguments':['a']},
            {'relation_id':'cause','arguments':['door','push']},
            {'relation_id':'door','arguments':['a','b']},
            {'relation_id':'push','arguments':['a','b']},
            {'relation_id':'role','arguments':['a']},
            {'relation_id':'glue1','arguments':['a','b']},
            {'relation_id':'glue2','arguments':['b','a']}]
    index = K.position_index(rows,{'a','b'})
    assert index['paths']['seal'] == ((((2,('relation','relation')),0),),)
    assert index['paths']['door'] == ((((2,('relation','relation')),1),((2,('relation','relation')),0)),)
    assert index['keys']['seal'] != index['keys']['role']
    assert index['counts'][index['keys']['glue1']] == 2
    rename = {x:'new'+x for x in ('link','seal','cause','door','push','role','glue1','glue2','a','b')}
    renamed = [{**r,'relation_id':rename[r['relation_id']],
                'arguments':[rename[a] for a in r['arguments']]} for r in reversed(rows)]
    other = K.position_index(renamed,{rename['a'],rename['b']})
    assert {rename[r]:k for r,k in index['keys'].items()} == other['keys']


def test_shared_child_all_paths_and_no_short_key_after_lost_ancestor():
    rows = [{'relation_id':'root','arguments':['p','q']},
            {'relation_id':'p','arguments':['child']},
            {'relation_id':'q','arguments':['child']},
            {'relation_id':'child','arguments':['a']}]
    index = K.position_index(rows,{'a'})
    assert len(index['paths']['child']) == 2
    cut = K.position_index(rows[1:],{'a'},ancestor_parents={'p':[('root',0)],'q':[('root',1)]})
    assert cut['keys']['child'] is None and cut['failures']['child']=='missing_ancestor'


def test_f_h_u_probability_and_zero_existing_code_cost():
    b,q = {'n':.8,'e':.2},{'n':.9,'e':.1}
    assert K.distribution('F','n',q,b)['e'] == .1
    # 十進数0.15を直接期待せず、腕Lと同じ浮動小数の加算式を使う。
    assert K.distribution('H',None,q,b)['e'] == .5*.1+.5*.2
    assert K.distribution('U',None,q,b) == b
    ph = {'counts':{'n':9,'e':1},'total':10}
    value,zero,inversions = K.surprise({'n':.999999,'e':.000001},'unseen',ph)
    assert zero and value == 5*math.log(2.)
    assert inversions == ['e']


def test_frequency_table_counts_collisions_but_not_unrevealed_query():
    rows = [{'relation_id':'x','predicate':'one','arguments':['a','b']},
            {'relation_id':'y','predicate':'two','arguments':['b','a']}]
    public = {'scene':rows,'entities':['a','b'],'feedback':{'f_fired':False}}
    index = K.position_index(rows,{'a','b'})
    table = {}
    K.count_after(table,public,index)
    assert table == {index['keys']['x']:{'one':1,'two':1}}
