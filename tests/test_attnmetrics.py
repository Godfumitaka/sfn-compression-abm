"""段C・Dの測度と、記録専用の答え直しの構造検査。"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools')]
import attndoor as D
import attnmetrics as M
import attnsel as A


def edge(name='hold', args=('a', 'b')):
    return {'prediction_kind': 'EdgePrediction', 'predicted_edge': {'predicate': name, 'arguments': args}, 'abstain_reason': None}


def test_score_uses_ordered_arguments_and_world1_overlap_is_explicit():
    assert M.outcome(edge(), ('hold', ('b', 'a'))) == 'wrong'
    assert M.response_class(edge(), 'hold', 'hold') == 'normal_door'
    assert M.availability([None], [('hold', ('a', 'b'))], ('hold', ('a', 'b'))) == ('below', 0, 1)
    assert M.availability([], [], ('hold', ('a', 'b'))) == ('absent', 0, 0)


def test_dprime_extreme_all_cells_and_no_response_not_filled():
    value = M.dprime_cells(4, 0, 0, 8)
    assert value['corrected'] and value['adjusted_hit_rate'] == 4.5/5
    assert value['adjusted_false_alarm_rate'] == .5/9
    value = M.dprime_cells(0, 0, 3, 8)
    assert value['dprime'] is None and not value['corrected']
    value = M.dprime_cells(3, 2, 2, 6)
    assert not value['corrected'] and value['hit_rate'] == .6


def test_final_answer_and_vote_do_not_change_weights_candidates_or_finish():
    tt = A.Terms((('sig_e', 1),), (('sig_e', 1), ('hold', 1)), (), 2, 3, (('sig_e', 1),), 2)
    candidates = (D.FrozenCandidate(SimpleNamespace(name='R', registered_at=1), 1, 1, tt,
                  ('hold', ('a', 'b')), edge()),)
    frame = {'door_task': True, 'baseline': edge('hold_b')}
    weights = {'sig_e': 2., 'hold': .2, 'hold_b': .7}
    before = deepcopy((frame, weights, candidates))
    assert M.static_answer(frame, candidates, weights, 1)[0] == edge()
    assert M.vote(frame, candidates, weights, 1)['groups'][0]['Q_sum'] == str(tt.value(weights))
    assert frame == before[0] and weights == before[1] and candidates == before[2]
    assert tt.value(weights) == Fraction(20, 23)
    frame['door_task'] = False
    assert M.static_answer(frame, candidates, weights, 1)[0] is frame['baseline']
    assert M.vote(frame, candidates, weights, 1) is None
