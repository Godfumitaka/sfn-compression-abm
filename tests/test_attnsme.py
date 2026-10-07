"""位置の対応・共通基底・開示順・符号つき費用を独立に確認する。"""
from pathlib import Path
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import attnposition_keys as K
import attnratio as P
from attnsme_features import Observations,features


def fixture():
    scene=[{'relation_id':'seal','predicate':'sig_e','arguments':['e']},
           {'relation_id':'parent','predicate':'attach','arguments':['seal','gap']}]
    obs=Observations();obs.after(0,[{'relation_id':'old','predicate':'sig_n','arguments':['e']},
                                  {'relation_id':'op','predicate':'attach','arguments':['old','gap']}],{'e'})
    obs.after(1,[{'relation_id':'old2','predicate':'sig_e','arguments':['e']},
                {'relation_id':'op2','predicate':'attach','arguments':['old2','gap']}],{'e'})
    obs.structure(scene,{'e'})
    p={'counts':{'sig_n':1,'sig_e':1,'attach':2},'total':4,'alive_vocab':['sig_n','sig_e','attach'],'lambda_mix':.1}
    s={'relation_id':'old2','arguments':['e'],'slot':0,'state':'F','predicate':'sig_e'}
    c={'R':'d','seats':[s],'signature_rows':[s],'relation_mapping':{'old2':'seal'}}
    return scene,obs,p,c


def test_k2_scores_fixed_seat_without_ancestors():
    scene,obs,p,c=fixture()
    args=(scene,{'e'},p,{'attach'},1.,obs,[c])
    k1=features(*args,position='k1',mode='global')[0][0]
    k2=features(*args,position='k2',mode='global')[0][0]
    assert k1['details'][0]['reason']=='missing_ancestor'
    d=k2['details'][0]
    assert d['reason'] is None and d['P']==.75 and d['b']==.5
    assert d['m']==-math.log(.75)+math.log(.5)


def test_u_relative_and_binary_zero():
    scene,obs,p,c=fixture();c['seats'][0].update(state='U');c['seats'][0].pop('predicate')
    for mode in ('binary','global','position'):
        d=features(scene,{'e'},p,{'attach'},1.,obs,[c],position='k2',mode=mode)[0][0]['details'][0]
        assert d['m']==0. and d['P']==d['b']


def test_common_base_does_not_use_candidate_shape_or_name():
    scene,obs,p,c=fixture();other={**c,'R':'other','signature_rows':[]}
    cs,bases,_=features(scene,{'e'},p,{'attach'},1.,obs,[c,other],position='k2',mode='global')
    assert cs[0]['details'][0]['b']==cs[1]['details'][0]['b']==.5
    assert bases[next(iter(cs[0]['m']))]['global']=={'sig_e':.5,'sig_n':.5}


def test_position_observations_only_before_prediction():
    scene,obs,p,c=fixture();before={k:dict(v) for k,v in obs.table.items()}
    features(scene,{'e'},p,{'attach'},1.,obs,[c],position='k2',mode='position')
    assert obs.table==before and obs.last_trial==1
    obs.after(2,scene,{'e'})
    assert sum(sum(c.values()) for c in obs.table.values())==6


def test_hidden_and_duplicate_positions_excluded():
    scene,obs,p,c=fixture();c['relation_mapping']={'old2':'gap'}
    d=features(scene,{'e'},p,{'attach'},1.,obs,[c],position='k2',mode='global')[0][0]['details'][0]
    assert d['reason']=='queried_hidden_position' and d['m']==0.
    scene.append({'relation_id':'parent2','predicate':'attach','arguments':['seal','gap']})
    c['relation_mapping']={'old2':'parent'}
    assert features(scene,{'e'},p,{'attach'},1.,obs,[c],position='k2',mode='global')[0][0]['details'][0]['reason']=='scene_key_collision'


def test_signed_gradient_central_difference():
    cs=(P.Candidate('a',.4,2,1,(('seal',-.7),('other',.8)),('good',()),{}),
        P.Candidate('b',.6,2,1,(('seal',.4),('other',-.2)),('bad',()),{}))
    a={'seal':.3,'other':.4}
    L,g,r=P.loss_gradient(cs,a,('good',()));assert r is None
    for key in a:
        plus=dict(a);minus=dict(a);plus[key]+=1e-5;minus[key]-=1e-5
        numeric=(P.loss_gradient(cs,plus,('good',()))[0]-P.loss_gradient(cs,minus,('good',()))[0])/2e-5
        assert abs(numeric-g[key])<1e-10


def test_zero_probability_uses_existing_bits_without_epsilon():
    p={'counts':{'a':3,'b':1},'total':4,'alive_vocab':['a','b'],'lambda_mix':.1}
    value,zero,_=K.surprise({},'unknown',p)
    assert zero and value==3*math.log(2.)
