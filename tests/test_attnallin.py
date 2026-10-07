"""全部入りの比・役割の鍵・開示だけのmixture学習の数値関門。"""
from dataclasses import replace
from pathlib import Path
import math
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import attnallin as I
import attnratio as A
import attnposition_keys as K
import attnstage2_readout as R


def scene(prefix='',seal='sig_e'):
    return [{'relation_id':prefix+'seal','predicate':seal,'arguments':(prefix+'entity',)},
            {'relation_id':prefix+'link','predicate':'attach','arguments':(prefix+'seal',prefix+'hole')}]


def test_F_mismatch_is_one_and_match_can_be_negative():
    base={'sig_e':.2,'sig_n':.8}
    mismatch=K.distribution('F','sig_n',{},base,epsilon=.01)
    matched=K.distribution('F','sig_e',{},base,epsilon=.01)
    bad,_=I.relative_mismatch(mismatch,base,'sig_e',epsilon=.01,length_of=lambda p:3.)
    good,_=I.relative_mismatch(matched,base,'sig_e',epsilon=.01,length_of=lambda p:3.)
    assert bad==pytest.approx(1.,abs=1e-15) and good<0


def test_probability_zero_uses_finite_native_escape_without_floor():
    value,audit=I.relative_mismatch({}, {'x':.5},'x',epsilon=.01,length_of=lambda p:4.)
    assert value==pytest.approx((4*math.log(2)+math.log(.5))/(-math.log(.01)))
    assert audit['zero_P'] and audit['P']==0 and math.isfinite(value)


def test_k2_is_role_shared_across_renamed_shop_entities_and_predicates():
    p1,_=I.visible_positions(scene('A','sig_e'),{'Aentity'}, {'Aseal':{'sig_e':.2},'Alink':{'attach':1.}})
    p2,_=I.visible_positions(scene('B','sig_n'),{'Bentity'}, {'Bseal':{'sig_e':.2},'Blink':{'attach':1.}})
    assert [p['key'] for p in p1]==[p['key'] for p in p2]
    assert all('sig_' not in p['key'] and 'A' not in p['key'] and 'B' not in p['key'] for p in p1)


def test_U_without_candidate_filter_is_zero_and_unmapped_never_calls_reader():
    positions,_=I.visible_positions(scene(),{'entity'},{'seal':{'sig_e':.2},'link':{'attach':1.}})
    c={'seats':[{'relation_id':'s','slot':0,'state':'U'}],'relation_mapping':{'s':'seal'}}
    called=[]
    def reader(seat,rid,b):called.append((seat['state'],rid));return b
    terms,details=I.candidate_features(positions,c,distribution_reader=reader,epsilon=.01,length_of=lambda p:3.)
    assert set(terms.values())=={0.} and called==[('U','seal')]
    assert details[1]['reason']=='unmapped_background'


def test_U_with_candidate_filter_keeps_signed_exact_ratio():
    positions,_=I.visible_positions(scene(),{'entity'},{'seal':{'sig_e':1/7},'link':{'attach':1.}})
    c={'seats':[{'relation_id':'s','slot':0,'state':'U'}],'relation_mapping':{'s':'seal'}}
    terms,details=I.candidate_features(positions,c,distribution_reader=lambda *a:{'sig_e':1/3},
                                     epsilon=.01,length_of=lambda p:3.)
    assert details[0]['m']==pytest.approx(math.log(3/7)/(-math.log(.01)),abs=1e-15)
    assert details[0]['m']<0 and details[0]['P']==1/3


def test_zero_common_base_uses_same_escape_length_as_native_log_cost():
    import v310be
    value,audit=I.relative_mismatch({'new':.1},{'seen':1.},'new',epsilon=.01,
                                   length_of=lambda p:v310be.log_cost({},p,{'seen':5}))
    assert audit['zero_b'] and audit['c_b']==6*math.log(2.)
    assert value==pytest.approx((-math.log(.1)-6*math.log(2.))/(-math.log(.01)))


def test_same_name_at_two_roles_keeps_two_keys_and_common_b_for_all_candidates():
    rows=[{'relation_id':'a','predicate':'same','arguments':('entity',)},
          {'relation_id':'b','predicate':'same','arguments':('a','hole')}]
    positions,_=I.visible_positions(rows,{'entity'},{'a':{'same':.2},'b':{'same':.8}})
    seen=[]
    def reader(seat,rid,b):seen.append((rid,b));return b
    for label in ('d0','d1'):
        candidate={'seats':[{'relation_id':label+rid,'slot':i,'state':'F'} for i,rid in enumerate(('a','b'))],
                   'relation_mapping':{label+rid:rid for rid in ('a','b')}}
        terms,_=I.candidate_features(positions,candidate,distribution_reader=reader,epsilon=.01,length_of=lambda p:2.)
        assert len(terms)==2 and set(terms.values())=={0.}
    assert seen[:2]==seen[2:]


def candidate(name,q,m,p):
    return A.Candidate(name,q,1,0,(('role',m),),None,
          {'readout':{'gate_passed':True,'slot':0,'P':{'answer':p,'other':1-p}}})


def test_common_background_cost_cancels_in_softmax_for_all_visible_positions():
    bases=(.2,.6);probs=((.8,.4),(.1,.7));a=(.3,.9);q=(.6,.5)
    norm=-math.log(.01)
    direct=[math.log(qi)-sum(ai*(-math.log(pi))/norm for ai,pi in zip(a,ps)) for qi,ps in zip(q,probs)]
    relative=[math.log(qi)-sum(ai*math.log(b/pi)/norm for ai,pi,b in zip(a,ps,bases)) for qi,ps in zip(q,probs)]
    def softmax(z):
        e=[math.exp(x-max(z)) for x in z];return [x/sum(e) for x in e]
    assert softmax(direct)==pytest.approx(softmax(relative),abs=2e-16)


@pytest.mark.parametrize('disclosed,door_task',((False,True),(True,False),(False,False)))
def test_non_disclosed_or_non_door_never_reads_feedback(disclosed,door_task):
    def forbidden():raise AssertionError('正解を読んだ')
    a={'role':.5}
    after,record=I.learn((),a,disclosed=disclosed,door_task=door_task,
                         feedback_reader=forbidden,background={})
    assert a==after and record['L'] is None and not record['updated']


def test_all_Q_zero_returns_background_without_softmax():
    cs=(candidate('zero',0,1,.9),)
    after,record=I.learn(cs,{},disclosed=True,door_task=True,
                        feedback_reader=lambda:(('answer',('x',)),3.),background={'answer':.4})
    assert after=={} and record['reason']=='no_positive_candidate'
    assert record['L']==pytest.approx(-math.log(.4))


def test_mixture_step_uses_probabilities_not_modal_answer_indicator_and_no_normalization():
    cs=(candidate('first',.6,1,.9),candidate('second',.5,0,.1))
    a={'role':.5,'untouched':2.}
    after,record=I.learn(cs,a,disclosed=True,door_task=True,
                        feedback_reader=lambda:(('answer',('x',)),3.),background={},eta=.1)
    assert record['gradient']['role']>0 and after['role']<a['role']
    assert after['untouched']==2. and a['role']==.5
    final,_,_=R.mixture_gradient(cs,after,('answer',('x',)),3.,background={},bits=False)
    assert final<record['L']


def test_a_zero_restores_Q_order_and_step_clips_at_ten():
    cs=(candidate('first',.6,1,.1),candidate('second',.5,0,.9))
    assert A.select(cs,{}).name=='first'
    after,record=I.learn(cs,{'role':9.9},disclosed=True,door_task=True,
                        feedback_reader=lambda:(('answer',('x',)),3.),background={},eta=1e6)
    assert 0<=after['role']<=10 and after['role']==10.
