"""42′の分布の損・確率0・符号つきΔ・代理勾配の独立の検査。"""
from dataclasses import replace
from pathlib import Path
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pytest
import attnratio as A
import attnstage2 as T
import attnstage2_readout as R


def candidate(name,q,p,m=(),answer='yes',gate=True,slot=0):
    return A.Candidate(name,q,2,0,m,answer,
                {'readout':{'gate_passed':gate,'slot':slot,'P':{'yes':p,'no':1-p}}})


def loss(cs,a=None,mode='top1',background=None):
    return R.loss(cs,a or {},'yes',7,mode=mode,choose=A.select,background=background or {'yes':.25,'no':.75})


@pytest.mark.parametrize('mode',['top1','mixture'])
def test_single_candidate_distribution_loss_changes_despite_same_modal_answer(mode):
    before=loss((candidate('a',1,.99),),mode=mode)
    after=loss((candidate('a',1,.51),),mode=mode)
    assert before.value == -math.log2(.99) and after.value == -math.log2(.51)
    assert after.value>before.value


@pytest.mark.parametrize('mode',['top1','mixture'])
def test_zero_probability_uses_native_escape_length_on_either_side(mode):
    cs=(candidate('a',1,0),)
    base=loss(cs,mode=mode)
    assert base.value==7 and base.escaped
    for p in (0,.5,1):
        rows,_=T.compare_seats(cs,{},[T.Seat('a',0,'F',0)],
                   lambda seat:replace(cs[0],payload=candidate('a',1,p).payload),None,
                   correct='yes',ell=7,mode=mode,choose=A.select,background={'yes':0})
        expected=R.cost(p,7)-7
        assert rows[0]['delta_fixed']==expected and math.isfinite(expected)
        reverse=loss((candidate('a',1,p),),mode=mode)
        assert base.value-reverse.value==-expected


def test_negative_delta_is_not_clipped_and_not_added_to_A(monkeypatch):
    import v39
    monkeypatch.setattr(v39,'CFG',{'decay':(.5,)*16});monkeypatch.setattr(v39,'_POW',{})
    rec=v39.SeatRec(0,'F',0,0,v39.ZERO4,v39.ZERO4)
    scored,_=T.accumulate({('a',0):rec},[{'R':'a','slot':0,'state':'F','gen':0,'delta_fixed':-2}],1)
    rf,rh,ru,e=v39.rec_means(scored['a',0],1)
    assert (rf,rh,ru,e)==(0,-2,-2,1)


def test_gate_closed_or_no_answer_slot_uses_supplied_background():
    for c in (candidate('a',1,.99,gate=False),candidate('a',1,.99,slot=None)):
        value=loss((c,))
        assert value.correct_mass==.25 and value.value==2 and value.source.startswith('background_')
    assert loss(()).value==2


def test_modal_tie_silence_still_scores_existing_answer_distribution():
    c=candidate('a',1,.5,answer=None)
    assert loss((c,)).value==1 and loss((c,)).source=='selected_slot'
    assert loss((c,),mode='alpha').value==7


def test_top1_is_unaffected_by_other_distribution_but_mixture_uses_it():
    cs=(candidate('chosen',.6,.9),candidate('other',.4,.1))
    changed=(cs[0],replace(cs[1],payload=candidate('other',.4,.8).payload))
    assert loss(cs).value==loss(changed).value
    assert loss(cs,mode='mixture').value!=loss(changed,mode='mixture').value
    assert loss(cs,mode='mixture').correct_mass==pytest.approx(.6*.9+.4*.1)


@pytest.mark.parametrize('trial',[.3,1,2])
def test_mixture_gradient_matches_three_central_differences(trial):
    cs=(candidate('a',.4,.8,(('seal',-.7),('other',.8))),
        candidate('b',.6,.2,(('seal',.4),('other',-.2)),answer='no'))
    attention={'seal':trial,'other':trial}
    value,g,reason=R.mixture_gradient(cs,attention,'yes',7,background={'yes':.25})
    natural,gn,_=R.mixture_gradient(cs,attention,'yes',7,background={'yes':.25},bits=False)
    assert reason is None and value==pytest.approx(natural/math.log(2.))
    for key in attention:
        assert g[key]==pytest.approx(gn[key]/math.log(2.))
        plus,minus=dict(attention),dict(attention);plus[key]+=1e-5;minus[key]-=1e-5
        numerical=(loss(cs,plus,'mixture').value-loss(cs,minus,'mixture').value)/2e-5
        assert numerical==pytest.approx(g[key],abs=1e-9)


def test_first_stage_indicator_gradient_is_not_distribution_mixture_gradient():
    cs=(candidate('a',.4,.8,(('seal',-.7),)),candidate('b',.6,.2,(('seal',.4),),answer='no'))
    _,old,_=A.loss_gradient(cs,{'seal':1},'yes')
    _,new,_=R.mixture_gradient(cs,{'seal':1},'yes',7,background={'yes':.25},bits=False)
    assert old['seal']!=pytest.approx(new['seal'])
    # 正解の分布が指示関数の特殊例では、初めて同じになる。
    exact=(replace(cs[0],payload=candidate('a',.4,1).payload),
           replace(cs[1],payload=candidate('b',.6,0).payload))
    _,special,_=R.mixture_gradient(exact,{'seal':1},'yes',7,background={'yes':.25},bits=False)
    assert old['seal']==pytest.approx(special['seal'])


def test_zero_probability_escape_is_constant_in_fixed_distribution_gradient():
    cs=(candidate('a',.4,0,(('seal',.7),)),candidate('b',.6,0,(('seal',.2),)))
    value,g,reason=R.mixture_gradient(cs,{'seal':1},'yes',7,background={'yes':0})
    assert (value,g,reason)==(7,{},'zero_probability_escape')


def test_redundant_two_seats_each_has_zero_value_after_full_reranking():
    cs=(candidate('two_roles',.8,.9),candidate('backup',.6,.9))
    seats=[T.Seat('two_roles',i,'H',0) for i in (0,1)]
    rows,_=T.compare_seats(cs,{},seats,lambda seat:replace(cs[0],q=.7),None,
                      correct='yes',ell=7,mode='top1',choose=A.select,background={'yes':.25})
    assert [r['delta_fixed'] for r in rows]==[0,0]
