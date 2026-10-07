"""第二段の損の単位・全候補の順位・減衰・固定対応を検査する。"""
from dataclasses import replace
from pathlib import Path
from random import Random
import math
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import attnratio as A
import attnstage2 as T
from attnstage2_sme import fixed_score
from sme2017 import Graph,Node,Matcher


def c(name,q,answer,m=()):
    return A.Candidate(name,q,2,0,m,answer,{})


def test_losses_hand_calculation():
    cs = (c('wrong',.6,'b'),c('right',.4,'a'))
    assert T.loss(cs,{},'a',3,mode='alpha',choose=A.select).value == 3
    r = T.loss(cs,{},'a',3,mode='beta',choose=A.select)
    assert r.value == -math.log2(.4)
    # 42′で主のlog Pの損は、最頻回答群の質量から席の分布へ変更。
    assert T.resolve_loss('arm',score_logp=True) == 'top1'
    assert T.resolve_loss('arm',score_logp=False) == 'alpha'


def test_preventing_unselected_candidate_has_value():
    cs = (c('normal',.4,'b'),c('exception',.6,'a'))
    seat = T.Seat('normal',0,'H',0)
    rows,work = T.compare_seats(cs,{},[seat],lambda s:replace(cs[0],q=.8),None,
                               correct='a',ell=3,mode='alpha',choose=A.select)
    assert rows[0]['delta_fixed'] == 3 and rows[0]['selected_fixed'] == 'normal'
    assert work['thinned_seats'] == 1 and work['rerankings'] == 2


def test_only_affected_definition_replaced_and_all_candidates_reranked():
    cs = (c('a',.5,'yes'),c('b',.4,None),c('c',.3,'no'))
    seats = [T.Seat('b',0,'H',0)]
    rows,_ = T.compare_seats(cs,{},seats,lambda s:replace(cs[1],q=.6,answer='yes'),None,
                            correct='yes',ell=3,mode='beta',choose=A.select)
    expected = -math.log2(1.1/1.4)+math.log2(.5/1.2)
    assert abs(rows[0]['delta_fixed']-expected)<1e-14


@pytest.mark.parametrize('scale',[.3,1.,2.])
def test_bits_gradient_is_natural_gradient_div_ln2_and_central_difference(scale):
    cs = (c('a',.4,'yes',(('s',-.7),('other',.8))),
          c('b',.6,'no',(('s',.4),('other',-.2))))
    a = {'s':scale,'other':scale}
    natural,g,_ = A.loss_gradient(cs,a,'yes')
    bits,gb,_ = T.bit_gradient(cs,a,'yes')
    assert bits == natural/math.log(2.)
    for key in a:
        assert gb[key] == g[key]/math.log(2.)
        plus,minus = dict(a),dict(a);plus[key]+=1e-5;minus[key]-=1e-5
        numeric = (T.loss(cs,plus,'yes',3,mode='beta',choose=A.select).value-
                   T.loss(cs,minus,'yes',3,mode='beta',choose=A.select).value)/2e-5
        assert abs(numeric-gb[key]) < 1e-9


def test_zero_correct_mass_is_explicit_and_undefined_delta_never_accumulated():
    cs = (c('wrong',.4,'b'),)
    assert T.loss(cs,{},'a',3,mode='beta',choose=A.select).reason == 'no_correct_candidates'
    with pytest.raises(ArithmeticError):
        T.compare_seats(cs,{},[T.Seat('wrong',0,'F',0)],lambda s:cs[0],None,
                        correct='a',ell=3,mode='beta',choose=A.select)


def test_rec_add_delta_keeps_native_unit_decay_and_new_H_zero(monkeypatch):
    import v39
    monkeypatch.setattr(v39,'CFG',{'decay':(.5,)*16});monkeypatch.setattr(v39,'_POW',{})
    rec = v39.SeatRec(0,'F',0,0,v39.ZERO4,v39.ZERO4)
    rows = [{'R':'d','slot':0,'state':'F','gen':0,'delta_fixed':3.}]
    scored,applied = T.accumulate({('d',0):rec},rows,1)
    RF,RH,RU,n = v39.rec_means(scored['d',0],2)
    assert RH-RF == 1.5 and RU-RH == 0. and n == .5
    assert applied == [('d',0)] and rec.post == v39.ZERO4
    rows[0]['gen'] = 1
    assert T.accumulate({('d',0):rec},rows,1)[0][('d',0)] is rec


def graphs(state='F',name='sig_n'):
    left = Graph((Node('a','entity'),Node('seal','relation',frozenset({name}) if state!='U' else frozenset(),('a',),state),
                  Node('anchor','relation',frozenset({'fold'}),('a',)),
                  Node('door','relation',frozenset({'hold'}),('a',)),
                  Node('link','relation',frozenset({'attach'}),('seal','door'))))
    right = Graph((Node('x','entity'),Node('s','relation',frozenset({'sig_e'}),('x',)),
                   Node('an','relation',frozenset({'fold'}),('x',)),
                   Node('hole','unknown',args=None),
                   Node('l','relation',frozenset({'attach'}),('s','hole'))))
    return left,right


@pytest.mark.parametrize('st',['F','H','U'])
def test_fixed_original_mapping_score_is_native(st):
    left,right = graphs(st,'sig_e')
    m = Matcher();best = m.match(left,right).best
    got,em,rm = fixed_score(left,right,dict(best.entity_mapping),dict(best.relation_mapping),m.settings)
    assert got == best.score
    assert em == dict(best.entity_mapping) and rm == dict(best.relation_mapping)


def test_U05j_new_seal_and_parent_pair_excluded_by_fixed_mapping():
    left,right = graphs()
    m = Matcher();old = m.match(left,right).best
    thin,_ = graphs('U')
    fixed,_,rm = fixed_score(thin,right,dict(old.entity_mapping),dict(old.relation_mapping),m.settings)
    exact = m.match(thin,right).best
    assert 'seal' not in rm and 'link' not in rm
    assert dict(exact.relation_mapping)['seal']=='s'
    assert dict(exact.relation_mapping)['link']=='l'
    assert exact.score > fixed
