"""段C・Dの記録専用の測度。選択・学習へ評価の結果を戻さない。"""
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from statistics import NormalDist

import attndoor as D
import attnsel as A


def answer_key(payload):
    edge = payload.get('predicted_edge')
    return None if edge is None else (edge['predicate'], tuple(edge['arguments']))


def outcome(payload, truth):
    key = answer_key(payload)
    return 'silent' if key is None else 'correct' if key == truth else 'wrong'


def response_class(payload, normal, exception):
    key = answer_key(payload)
    if key is None:
        return 'silent'
    # 世界1では同じ名前。例外の列は適用不能として別途明記する。
    if key[0] == normal:
        return 'normal_door'
    return 'exception_door' if key[0] == exception else 'other_name'


def availability(actual_answers, potential_answers, truth):
    above = sum(a == truth for a in actual_answers)
    potential = sum(a == truth for a in potential_answers)
    return ('above' if above else 'below' if potential else 'absent'), above, potential


def dprime_cells(hit, miss, false_alarm, correct_rejection):
    """二つのドア回答に限る。極端率だけ全4セルに0.5を加える。"""
    if min(hit, miss, false_alarm, correct_rejection) < 0:
        raise ValueError('件数は非負')
    signal, noise = hit + miss, false_alarm + correct_rejection
    if not signal or not noise:
        return {'dprime': None, 'criterion': None, 'hit_rate': None if not signal else hit/signal,
                'false_alarm_rate': None if not noise else false_alarm/noise,
                'corrected': False, 'undefined_reason': 'no_two_door_answers_in_a_condition'}
    h, f = hit/signal, false_alarm/noise
    correction = h in (0., 1.) or f in (0., 1.)
    hc = (hit+.5)/(signal+1.) if correction else h
    fc = (false_alarm+.5)/(noise+1.) if correction else f
    zh, zf = NormalDist().inv_cdf(hc), NormalDist().inv_cdf(fc)
    return {'dprime': zh-zf, 'criterion': -.5*(zh+zf), 'hit_rate': h,
            'false_alarm_rate': f, 'adjusted_hit_rate': hc, 'adjusted_false_alarm_rate': fc,
            'corrected': correction, 'undefined_reason': None}


def ranked_candidates(candidates, weights, arm):
    fixed = D.DOOR_NAMES if arm == 2 else ()
    return A.rank(tuple(replace(c, terms=replace(c.terms, fixed_names=fixed)) for c in candidates), weights)


def static_answer(frame, candidates, weights, arm):
    """答える時だけの介入。重み・候補・記憶を変更せず、finishを呼ばない。"""
    if not frame['door_task'] or not arm:
        return frame['baseline'], None
    ranked = ranked_candidates(candidates, weights, arm)
    return (ranked[0].payload, ranked[0].definition.name) if ranked else (frame['baseline'], None)


def vote(frame, candidates, weights, arm):
    """現在のQの総和。黙りも一つの回答、同点は最上位候補の回答。"""
    if not frame['door_task']:
        return None
    ranked = ranked_candidates(candidates, weights, arm)
    if not ranked:
        return {'payload': frame['baseline'], 'groups': [], 'selected_R': None}
    scores = defaultdict(Fraction)
    representatives = {}
    for c in ranked:
        scores[c.answer] += c.terms.value(weights)
        representatives.setdefault(c.answer, c)
    top = max(scores.values())
    winning = next(c.answer for c in ranked if scores[c.answer] == top)
    return {'payload': representatives[winning].payload,
            'selected_R': representatives[winning].definition.name,
            'groups': [{'answer': key, 'Q_sum': str(value), 'Q_sum_float': float(value)}
                       for key, value in scores.items()]}
