"""42⁗では測る席の範囲だけを変え、同じ最終損の差を使う。"""
from dataclasses import replace
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import attnratio as A
import attnstage2 as T


@pytest.mark.parametrize('mode',('alpha','top1','mixture'))
def test_chosen_delta_is_exact_subset_of_all_same_trial(mode):
    def payload(p):return {'readout':{'gate_passed':True,'slot':0,'P':{'answer':p,'other':1-p}}}
    candidates=(A.Candidate('chosen',.7,2,0,(),('answer',('x',)),payload(.8)),
                A.Candidate('unselected',.5,2,0,(),('other',('x',)),payload(.2)))
    seats=(T.Seat('chosen',0,'F',0),T.Seat('chosen',1,'H',0),T.Seat('unselected',0,'F',0))
    seen=[]
    def rematch(seat):
        seen.append(seat)
        old=next(c for c in candidates if c.name==seat.definition)
        return replace(old,q=.4 if seat.definition=='chosen' else .9)
    common=dict(correct=('answer',('x',)),ell=3.,mode=mode,choose=A.select,
                background={'answer':.25},method='rematched')
    all_rows,_=T.compare_seats(candidates,{},seats,rematch,None,**common)
    seen.clear()
    chosen=T.measurement_seats(seats,scope='chosen',selected='chosen')
    rows,work=T.compare_seats(candidates,{},chosen,rematch,None,**common)
    assert rows==[row for row in all_rows if row['R']=='chosen']
    assert seen==list(chosen) and work['thinned_seats']==2
    assert work['baseline_loss']['selected']=='chosen'


def test_no_selected_definition_measures_no_seats():
    seats=(T.Seat('r',0,'H',0),)
    assert T.measurement_seats(seats,scope='chosen',selected=None)==()
    assert T.measurement_seats(seats,scope='all',selected=None)==seats
    with pytest.raises(ValueError,match='範囲'):
        T.measurement_seats(seats,scope='guess',selected='r')
