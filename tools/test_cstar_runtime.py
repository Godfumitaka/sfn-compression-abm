"""41′の門・背景の凍結・誕生の情報の境界の小さな検査。"""
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import replace
from unittest.mock import patch
from random import Random
import math,sys,unittest
sys.path[:0] = [str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from abm.definition import Constituent,FrequencyTable
from abm.domains import Relation,RelationGraph
import cstar_runtime as runtime
import cstar_probability as probability
import v39,v310be,argorder


class RuntimeGates(unittest.TestCase):
    def setUp(self):
        self.saved = [(d,dict(d)) for d in (runtime.CFG,runtime.CTX,runtime.STATS,v39.CFG,v39.CTX,v310be.CFG,v310be.CTX)]
        self.background = probability.BACKGROUND_SOURCE
        probability.BACKGROUND_SOURCE = None
        for d,_ in self.saved:
            d.clear()
        runtime.CFG.update(h_dirichlet=1,logp_eps=.5,birth_score='seq',match_eps='0')
        v39.CFG.update(init='two',u_abstain=False,decay=(1.,)*16)
        v39.CTX['births_rec'] = []
        self.row = Constituent(0,0,Relation('s','a',('x','y')),True)
        self.d = NS(name='D',constituents=(self.row,))
        self.state = NS(slot_history={('D',0):{'a':9,'b':4}},p_hat=FrequencyTable({'a':8,'b':2},10,.1,frozenset({'a','b'})))
        self.scene = RelationGraph('scene',relations=(Relation('t','b',('u','v')),))
        self.config = NS(local_lambda=1.,higher_order_predicates=frozenset())

    def tearDown(self):
        probability.BACKGROUND_SOURCE = self.background
        for d,saved in self.saved:
            d.clear(); d.update(saved)

    def test_positive_probability_does_not_pass_name_gate(self):
        alignment = NS(relation_mapping={'s':'t'})
        self.assertFalse(runtime.support(self.d,self.row,self.state.slot_history,alignment,self.scene))
        h = replace(self.row,alive=False)
        self.assertTrue(runtime.support(self.d,h,self.state.slot_history,alignment,self.scene))
        self.assertFalse(runtime.support(self.d,h,{},alignment,self.scene))
        self.assertTrue(runtime.support(self.d,self.row,{},alignment,RelationGraph('hidden')))
        self.assertFalse(runtime.support(self.d,h,{},alignment,RelationGraph('hidden')))

    def test_dirichlet_same_source_for_answer_value_match(self):
        out = runtime.distributions(self.d,self.row,self.state,self.scene,self.config)
        self.assertEqual(out['b'],v310be.probabilities(self.d,self.row,self.state,self.scene,self.config)['U'])
        q = runtime.h_distribution(self.d,self.row,self.state.slot_history,self.state.p_hat,self.scene,frozenset())
        self.assertEqual(q,out['q']['H'])
        self.assertAlmostEqual(q['a'],(9+out['b']['a'])/14)
        self.assertAlmostEqual(out['P']['H']['a'],.5*q['a']+.5*out['b']['a'])

    def test_expected_distribution_does_not_change_memory_or_rng(self):
        rnd = Random(1)
        before = repr(self.state),rnd.getstate()
        with runtime.phase(self.state,self.config,self.scene,True):
            runtime.distributions(self.d,self.row,self.state,self.scene,self.config)
            runtime.distributions(self.d,self.row,self.state,self.scene,self.config)
        self.assertEqual((repr(self.state),rnd.getstate()),before)
        self.assertFalse(runtime.active())

    def test_zero_probability_keeps_escape_cost(self):
        self.assertEqual(v310be.log_cost({'a':1.},'new',{'a':5}),6)

    def test_seq_freezes_b_and_first_material_name(self):
        v310be.CFG['score_logp'] = True
        v310be.CTX['score_state'] = self.state
        changed = NS(slot_history={},p_hat=FrequencyTable({'a':10000,'b':2},10002,.1,frozenset({'a','b'})))
        observation = ((self.row.relation,('x','y')),(Relation('t','b',('u','v')),('u','v')))
        with patch.object(argorder,'birth_observations',return_value=observation):
            rec = runtime.initialize(self.d,self.row,changed,self.scene,self.scene,2,1,self.config)
        record = v39.CTX['births_rec'][-1]
        b = record['b']
        self.assertAlmostEqual(b['a'],.8)
        self.assertAlmostEqual(record['P_current']['F']['a'],.9)
        self.assertEqual(record['P_old']['F'],record['P_old']['H'])
        self.assertEqual(record['P_old']['H'],record['P_old']['U'])
        self.assertAlmostEqual(rec.init[0][0],-math.log2(.8)-math.log2(.1))

    def test_seq_actual_F_name_mismatch_stops(self):
        observation = ((Relation('s','b',('x','y')),('x','y')),(self.row.relation,('x','y')))
        with patch.object(argorder,'birth_observations',return_value=observation):
            with self.assertRaisesRegex(RuntimeError,'固定名が異なる'):
                runtime.initialize(self.d,self.row,self.state,self.scene,self.scene,2,1,self.config)
        self.assertEqual(runtime.STATS['birth_fixed_name_mismatch'],1)


if __name__ == '__main__':
    unittest.main()
