"""e0a1f2edのL二旗だけの検査。Tの検査は移さない。"""
import math,sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import replace
from random import Random
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
import v39
import v310be as be
from abm.definition import Constituent,FrequencyTable
from abm.domains import Relation,RelationGraph

class Gates(unittest.TestCase):
    def setUp(self):
        v39.CFG.clear();v39.CTX.clear();be.CFG.clear();be.CTX.clear();be.STATS.clear()
        v39.CFG.update(u_abstain=False,init='two',decay=(1.0,)*16,dict_index={})
        v39.CTX.update(births_rec=[],struct_cache={})
        be.STATS['retire_candidate_evals']=0;be.STATS['score_other_position']=0;be.CTX.update(L_score={'a':5,'b':5},R_B_trial=0.0)
        self.row=Constituent(0,0,Relation('s','a',('x','y')),True)
        self.d=NS(name='D',constituents=(self.row,),registered_at=0)
        self.scene=RelationGraph('x',relations=(Relation('t','a',('u','v')),))
        self.cfg=NS(local_lambda=1.0,higher_order_predicates=frozenset())
        self.state=NS(slot_history={('D',0):{'a':9,'b':4}},p_hat=FrequencyTable({'a':8,'b':2},10,.1,frozenset({'a','b'})))

    def test_normalization_empty_history_unseen_ties(self):
        for hist in ({},{('D',0):{}},{('D',0):{'a':9,'b':4}},{('D',0):{'a':1,'b':4}},{('D',0):{'unseen':1}}):
            st=NS(slot_history=hist,p_hat=self.state.p_hat)
            for dist in be.probabilities(self.d,self.row,st,self.scene,self.cfg).values():
                self.assertAlmostEqual(sum(dist.values()),1)
                self.assertTrue(all(p>=0 for p in dist.values()))
        st=NS(slot_history={},p_hat=FrequencyTable.empty())
        for dist in be.probabilities(self.d,self.row,st,self.scene,self.cfg).values():self.assertAlmostEqual(sum(dist.values()),1)
        tied=replace(self.state.p_hat,counts={'a':1,'b':1},total=2)
        self.assertEqual(v39.u_answer(self.d,self.row,self.scene,tied,frozenset()),(None,'同点'))
        self.assertEqual(be.log_cost({'a':1.0},'unseen',{'a':5}),6)

    def test_signature_and_order(self):
        st=NS(slot_history={},p_hat=FrequencyTable({'a':8,'b':2,'high':1},11,.1,frozenset({'a','b','high'})))
        scene=RelationGraph('s',relations=(Relation('b','b',('x',)),))
        cfg=NS(local_lambda=1,higher_order_predicates=frozenset({'high'}))
        self.assertEqual(be.probabilities(self.d,self.row,st,scene,cfg)['U'],{'a':1.0})

    def test_hand_cost_and_value(self):
        P=be.probabilities(self.d,self.row,self.state,self.scene,self.cfg)
        self.assertAlmostEqual(P['U']['a'],.8);self.assertAlmostEqual(P['H']['a'],.85);self.assertAlmostEqual(P['F']['a'],.9)
        rH=be.log_cost(P['H'],'a',{'a':5});rU=be.log_cost(P['U'],'a',{'a':5})
        self.assertAlmostEqual(rH,-math.log2(.85));self.assertAlmostEqual(rU,-math.log2(.8))
        rec=v39.rec_add(v39.SeatRec(0,'H',0,0,v39.ZERO4,v39.ZERO4),0,(0,rH,rU,1))
        d=NS(name='D',constituents=(replace(self.row,alive=False),),registered_at=0)
        st=NS(definitions={'D':d},slot_history=self.state.slot_history,v39_seats={('D',0):rec})
        old=v39.definition_bits
        try:
            v39.definition_bits=lambda *args:10
            c=be.candidates(st,d,0,{'a':5,'b':5},1)[0]
            self.assertAlmostEqual(c[0],(rU-rH)/(10+v39.I(1)-v39.I(0)))
        finally:v39.definition_bits=old

    def test_score_snapshot_before_disclosure_and_flag_off(self):
        P=be.probabilities(self.d,self.row,self.state,self.scene,self.cfg)
        it={'slot':0,'st':'F','pos':['x','y'],'gen':0,'ans':{'F':'a','H':'a','U':'a'},'P':P}
        seats={('D',0):v39.SeatRec(0,'F',0,0,v39.ZERO4,v39.ZERO4)}
        received=Relation('s','a',('x','y'))
        _,old=be.score_answers(seats,{'R':'D','items':[it]},received,0)
        self.assertEqual(old,[[0,'F',0.0,0.0,0.0]])
        be.CFG['score_logp']=True;self.state.slot_history.clear()
        _,new=be.score_answers(seats,{'R':'D','items':[it]},received,0)
        self.assertAlmostEqual(new[0][3],-math.log2(.85));self.assertAlmostEqual(new[0][4],-math.log2(.8))

    def test_initial_values_and_no_rng(self):
        rng=Random(123);before=rng.getstate();be.CFG['score_logp']=True
        P=be.probabilities(self.d,self.row,self.state,self.scene,self.cfg)
        rec=be.init_rec(self.d,self.row,self.state,self.scene,self.scene,2,1,self.cfg)
        for i,name in enumerate(('F','H','U')):self.assertAlmostEqual(rec.init[i][0],2*be.log_cost(P[name],'a',v39.code_lengths(self.state.p_hat)))
        self.assertEqual(rng.getstate(),before)

    def test_initial_values_use_before_disclosure_memory(self):
        be.CFG['score_logp']=True
        before=NS(slot_history={},p_hat=self.state.p_hat)
        be.CTX['score_state']=before
        after=NS(slot_history={('D',0):{'a':1000}},p_hat=FrequencyTable({'a':1000,'b':2},1002,.1,frozenset({'a','b'})))
        P=be.probabilities(self.d,self.row,before,self.scene,self.cfg)
        rec=be.init_rec(self.d,self.row,after,self.scene,self.scene,2,1,self.cfg)
        for i,name in enumerate(('F','H','U')):
            self.assertAlmostEqual(rec.init[i][0],2*be.log_cost(P[name],'a',v39.code_lengths(before.p_hat)))
        self.assertAlmostEqual(rec.init[1][0],-2*math.log2(.8))
        self.assertAlmostEqual(rec.init[2][0],-2*math.log2(.8))

    def test_direct_H09_U08_ell5(self):
        rh=be.log_cost({'a':.9,'b':.1},'a',{'a':5})
        ru=be.log_cost({'a':.8,'b':.2},'a',{'a':5})
        self.assertAlmostEqual(rh,.15200309344504995)
        self.assertAlmostEqual(ru,.3219280948873623)
        self.assertAlmostEqual((ru-rh)/12,.014160416786859363)
        self.assertEqual(be.log_cost({},'unknown',{'a':5}),6)

    def test_role_score_uses_snapshot_and_L_creates_no_RNG(self):
        from unittest.mock import patch
        P=be.probabilities(self.d,self.row,self.state,self.scene,self.cfg)
        it={'slot':0,'st':'F','pos':['x','y'],'gen':0,'ans':{'F':'a','H':'a','U':'a'},'P':P,'cid':'s'}
        seats={('D',0):v39.SeatRec(0,'F',0,0,v39.ZERO4,v39.ZERO4)}
        be.CFG['score_logp']=True
        be.STATS.update(score_role_scored=0,score_role_scored_pos_differs=0)
        with patch('random.Random',side_effect=AssertionError('L が乱数を作った')),patch('random.random',side_effect=AssertionError('L が共用乱数を使った')):
            be.probabilities(self.d,self.row,self.state,self.scene,self.cfg)
            be.init_rec(self.d,self.row,self.state,self.scene,self.scene,1,1,self.cfg)
            _,new=be.score_answers_role(seats,{'R':'D','items':[it]},Relation('s','a',('x','y')),0)
        self.assertAlmostEqual(new[0][3],-math.log2(.85))
        self.assertAlmostEqual(new[0][4],-math.log2(.8))

    def test_E_logp_H_matches_and_misses_F_unchanged(self):
        from unittest.mock import patch
        import abm.sme as sme
        d=NS(name='D',constituents=(replace(self.row,alive=False),),registered_at=0)
        st=NS(definitions={'D':d},slot_history=self.state.slot_history,p_hat=self.state.p_hat)
        al=NS(alignment=NS(relation_mapping={'s':'t'}))
        for name,P in (('a',.85),('b',.15)):
            scene=RelationGraph('x',relations=(Relation('t',name,('u','v')),))
            with patch.object(sme,'map_graphs',return_value=al):
                be.CFG.clear();old,parts_old=be.rewrite(st,'D',scene,{'a':5,'b':5},self.cfg,{'t'})
                be.CFG['score_logp_e']=True
                new,parts_new=be.rewrite(st,'D',scene,{'a':5,'b':5},self.cfg,{'t'})
            self.assertAlmostEqual(new-old,-math.log2(P)-(5 if name=='b' else 0))
            self.assertEqual(parts_old['書換数'],parts_new['書換数'])
            self.assertEqual(parts_new['H_logp_count'],1)
        d=NS(name='D',constituents=(self.row,),registered_at=0);st.definitions={'D':d}
        with patch.object(sme,'map_graphs',return_value=al):
            be.CFG.clear();old,_=be.rewrite(st,'D',self.scene,{'a':5,'b':5},self.cfg,{'t'})
            be.CFG['score_logp_e']=True;new,_=be.rewrite(st,'D',self.scene,{'a':5,'b':5},self.cfg,{'t'})
        self.assertEqual(old,new)


if __name__=='__main__':unittest.main()
