"""符号つき相対費用・共通基底・開示時点の構造検査。"""
from fractions import Fraction
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import attnratio as P
import attnratio_features as F

def cand(name,q,m,answer):
    return P.Candidate(name,Fraction(q),2,0,(('k',m),),answer,{'name':name})

def test_negative_cost_and_zero_reduction():
    cs=(cand('a',.8,0.,('a',())),cand('b',.7,-1.,('b',())))
    assert P.select(cs,{}).name=='a'
    assert P.select(cs,{'k':1.}).name=='b'

def test_gradient_with_signed_cost():
    cs=(cand('a',.8,-.5,('a',())),cand('b',.7,.6,('b',())))
    loss,g,_=P.loss_gradient(cs,{'k':.3},('b',()))
    num=(P.loss_gradient(cs,{'k':.30001},('b',()))[0]-P.loss_gradient(cs,{'k':.29999},('b',()))[0])/.00002
    assert abs(num-g['k'])<1e-9

def test_common_base_has_no_candidate_input():
    scene=[{'relation_id':'r','predicate':'x','arguments':['e']}]
    ph={'alive_vocab':['x','y','z'],'counts':{'x':2,'y':1,'z':8},'total':11,'lambda_mix':.1}
    shapes={'x':{(1,('entity',))},'y':{(1,('entity',))},'z':{(2,('entity','entity'))}}
    bases,_=F.common_bases(scene,['e'],ph,set(),{},shapes)
    b=next(iter(bases.values()));assert set(b['global'])=={'x','y'}
    assert abs(b['global']['x']-2/3)<1e-15 and abs(b['global']['y']-1/3)<1e-15
    assert b['position']==b['global']

def test_undisclosed_truth_unreachable_and_next_trial_update():
    class NoTruth(dict):
        def __getitem__(self,k):
            assert k!='feedback_content'
            return super().__getitem__(k)
    cs=(cand('a',.8,.6,('a',())),cand('b',.7,-.5,('b',())))
    learner=P.Learner(.5);prepared=learner.prepare(0,True,{},cs)
    record=learner.finish(prepared,NoTruth(prediction_order=0,f_realized=.5,f_fired=False))
    assert record['reason']=='not_disclosed' and learner.attention=={'k':0.}
    prepared=learner.prepare(1,True,{},cs);assert prepared.selected=='a'
    learner.finish(prepared,{'prediction_order':1,'f_realized':.5,'f_fired':True,
                             'feedback_content':{'predicate':'b','arguments':[]}})
    assert learner.attention['k']>0 and prepared.selected=='a'
    assert learner.prepare(2,True,{},cs).selected=='b'

def test_common_constant_softmax_equivalence():
    cs=(cand('a',.8,-.5,('a',())),cand('b',.7,.6,('b',())))
    relative=[z for _,z in P.log_scores(cs,{'k':.7})]
    direct=[z-3.4 for z in relative]
    def pi(z):
        e=[math.exp(x-max(z)) for x in z];return [x/sum(e) for x in e]
    assert all(abs(x-y)<1e-15 for x,y in zip(pi(relative),pi(direct)))
