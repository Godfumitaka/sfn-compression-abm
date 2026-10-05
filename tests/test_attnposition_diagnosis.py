"""事後診断の会計と、選びの一位／発話の門の区別を確かめる。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import attnposition_diagnosis as D


def test_gate_abstention_is_not_missing_winner():
    payload = {'predicted_edge': None, 'abstain_reason': 'below_tau', 'R_used': None}
    assert D.silence_cause(payload) == 'below_speech_gate'
    assert D.answer_key(payload) is None


def test_seat_kinds_use_saved_history_membership():
    detail = {'reason': None, 'visible_name': 'x'}
    assert D.seat_kind({'state': 'F', 'predicate': 'x'}, detail) == 'F_match'
    assert D.seat_kind({'state': 'F', 'predicate': 'y'}, detail) == 'F_mismatch'
    assert D.seat_kind({'state': 'H', 'history': {'x': 2}}, detail) == 'H_present'
    assert D.seat_kind({'state': 'H', 'history': {'y': 2}}, detail) == 'H_absent'
    assert D.seat_kind({'state': 'U'}, detail) == 'U'
    assert D.seat_kind({'state': 'U'}, {'reason': 'missing_ancestor'}) is None


def test_absolute_surprise_counts_U_and_separates_exclusions():
    c = {'R': 'winner', 'n': 2, 'q_numerator': 1, 'q_denominator': 2,
         'payload': {'predicted_edge': None, 'R_used': None, 'abstain_reason': 'below_tau'},
         'details': [{'state': 'U', 'reason': None, 'm_global': 2.},
                     {'state': 'F', 'reason': 'missing_ancestor'},
                     {'state': 'H', 'reason': 'queried_hidden_position'}],
         'm': {'global': {D.SEAL_KEY: 2., 'other': 0.}}}
    r = D.describe(c, {D.SEAL_KEY: .5}, 'global')
    assert r['seats_total'] == 3 and r['alive_F'] == 1
    assert r['m_counted'] == r['U_counted'] == 1
    assert r['U_numeric_zero'] == 0
    assert r['excluded_missing_ancestor'] == r['excluded_queried_hidden_position'] == 1
    assert r['penalty'] == r['penalty_seal'] == 1. and r['penalty_other'] == 0.


def test_ambiguous_reason_does_not_invent_U_tie():
    assert D.silence_cause({'predicted_edge': None, 'abstain_reason': 'ambiguous_projection'}) == 'ambiguous_projection_U_or_H_tie_unknown'


def test_gap_rejection_has_its_saved_reason():
    assert D.silence_cause({'predicted_edge': None, 'abstain_reason': 'no_gap_candidate'}) == 'no_answer_at_visible_gap'
