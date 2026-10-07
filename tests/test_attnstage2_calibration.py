"""第二段の損の差を積んだ実Vを較正へ渡し、実変換だけを止める。"""
from dataclasses import replace
from pathlib import Path
import io
import json
import math
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
               str(Path(__file__).resolve().parents[1])]
import pytest
import attnratio as A
import attnstage2 as T
import calibration
import v310be
import v39
from test_v39_budget import setup, definition, row, state, rec


def test_no_forget_collects_accumulated_second_stage_V_and_preserves_real_state(monkeypatch):
    # 元の検査環境の大域状態を残さず、較正が参照する本物の候補関数を使う。
    for module, names in ((v39, ('CFG', 'STATS', 'CTX', 'REG', '_POW')),
                          (v310be, ('STATS', 'CTX')), (calibration, ('ST',))):
        for name in names:
            monkeypatch.setattr(module, name, {})
    monkeypatch.setattr(v39, '_candidates', v310be.candidates)
    setup(price=100)
    v310be.STATS.update(retire_candidate_evals=0, zero_release=0)
    d = definition(row(0, 'fold', ('x', 'y')),
                   row(1, v39.ERASED, ('y', 'z'), alive=False))
    st = state([d], {('R_x', 0): {'fold': 1}, ('R_x', 1): {'lock': 1}},
               {('R_x', 0): rec('F'), ('R_x', 1): rec('H')})
    base = A.Candidate('R_x', 1, 2, 0, (), 'yes',
                       {'readout': {'gate_passed': True, 'slot': 0,
                                    'P': {'yes': .8, 'no': .2}}})
    seats = (T.Seat('R_x', 0, 'F', 0), T.Seat('R_x', 1, 'H', 0))

    def rematched(seat):
        p = .4 if seat.state == 'F' else 1.
        return replace(base, payload={'readout': {'gate_passed': True, 'slot': 0,
                                                 'P': {'yes': p, 'no': 1-p}}})

    rows, _ = T.compare_seats((base,), {}, seats, rematched, None,
                             correct='yes', ell=5, mode='top1', choose=A.select,
                             background={'yes': .5, 'no': .5}, method='rematched')
    deltas = {r['slot']: r['delta_fixed'] for r in rows}
    assert deltas == pytest.approx({0: 1., 1: math.log2(.8)}, abs=1e-12)
    accumulated, applied = T.accumulate(st.v39_seats, rows, 10)
    assert applied == [('R_x', 0), ('R_x', 1)]
    st = replace(st, v39_seats=accumulated)
    saved = repr(st)
    stream = io.StringIO()
    calibration.ST.update(f=stream, world=2, seed=1, trials=0)
    v39.CFG['no_forget_exec'] = True
    out, events, before, after, ties, boundary = v39.run_conversions(st, 10)
    assert out is st and repr(st) == saved and events == [] and before == after
    assert ties == 0 and boundary is None
    actual = [r for r in json.loads(stream.getvalue())['candidates'] if not r['reference']]
    assert {(r['slot'], r['kind']) for r in actual} == {(0, 'FH'), (1, 'HU')}
    for r in actual:
        assert r['numerator'] == pytest.approx(deltas[r['slot']], abs=1e-12)
        assert r['V'] == pytest.approx(deltas[r['slot']] / r['denominator'], abs=1e-12)
    # この価格なら実変換の対象となることも同じ状態で確認する。
    v39.CFG.pop('no_forget_exec')
    converted, events, _, _, _, _ = v39.run_conversions(st, 10)
    assert events and converted != st and repr(st) == saved
