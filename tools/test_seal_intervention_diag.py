"""条件介入の構造・記録・元の状態の不変性を検査。予想の方向は検査しない。"""
import sys,unittest,tempfile
from types import SimpleNamespace
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
import seal_intervention_diag as diag,v39
from abm.definition import Constituent,NamedDefinition,FrequencyTable
from abm.domains import AgentState,Relation,RelationGraph,AgentOutput,EdgePrediction,Abstain


class Gates(unittest.TestCase):
    def setUp(self):
        self.rows=(Constituent(0,3,Relation('seal','ERASED',('a',)),None,False),
                   Constituent(1,3,Relation('door','content',('a','b')),None,True),
                   Constituent(2,3,Relation('other','ERASED',('b',)),None,False))
        self.d=NamedDefinition('D',self.rows,3,3)
        self.state=AgentState(definitions={'D':self.d},p_hat=FrequencyTable.empty(),slot_history={('D',2):{'past':1}})
        self.names={diag.seat_key(self.d,self.rows[0]):{'predicate':'birth_condition','birth_trial':3,'source':'材料'}}

    def test_only_U_seals_in_all_definitions(self):
        d2=replace(self.d,name='D2');state=replace(self.state,definitions={'D':self.d,'D2':d2})
        names={**self.names,diag.seat_key(d2,d2.constituents[0]):{'predicate':'second_condition','birth_trial':3}}
        changed,edits,missing=diag.restore_conditions(state,names,{'seal'})
        self.assertEqual(len(edits),2);self.assertFalse(missing)
        for old in state.definitions.values():
            new=changed.definitions[old.name]
            self.assertTrue(new.constituents[0].alive)
            self.assertEqual(new.constituents[1:],old.constituents[1:])
            self.assertFalse(old.constituents[0].alive)
            self.assertEqual(new.constituents[0].relation.arguments,old.constituents[0].relation.arguments)
        for field in ('p_hat','slot_history','rng_state','prototype','merit','exceptions','embed'):
            self.assertIs(getattr(changed,field),getattr(state,field))

    def test_F_H_and_nonseal_U_unchanged(self):
        state=replace(self.state,slot_history={('D',0):{},('D',2):{'past':1}})
        new,edits,missing=diag.restore_conditions(state,self.names,{'seal','door'})
        self.assertEqual(new,state);self.assertEqual(edits,[]);self.assertEqual(missing,[])
        new,edits,missing=diag.restore_conditions(self.state,{}, {'seal'})
        self.assertEqual(new,self.state);self.assertEqual(len(missing),1)

    def test_birth_identity_is_not_reused(self):
        d=replace(self.d,registered_at=4)
        new,edits,missing=diag.restore_conditions(replace(self.state,definitions={'D':d}),self.names,{'seal'})
        self.assertEqual(len(missing),1);self.assertEqual(edits,[])
        self.assertFalse(new.definitions['D'].constituents[0].alive)

    def test_birth_material_only_and_no_later_overwrite(self):
        post={'definitions':{'D':{'name':'D','registered_at':3,'constituents':[{'slot_index':0,'registered_at':3,'alive':False,'relation':{'relation_id':'seal','predicate':v39.ERASED}}]}}}
        names={};observed={'seal':{'predicate':'from_record','trial':2,'source':'過去の観測'}}
        diag.update_birth_names(post,observed,3,names,{'seal'})
        self.assertEqual(names[('D',3,0,3)]['predicate'],'from_record')
        diag.update_birth_names(post,{'seal':{'predicate':'later','trial':4,'source':'後の観測'}},4,names,{'seal'})
        self.assertEqual(names[('D',3,0,3)]['predicate'],'from_record')
        none={};diag.update_birth_names(post,{'seal':{'predicate':'future','trial':4,'source':'未来'}},3,none,{'seal'})
        self.assertFalse(none)

    def test_birth_material_conflict_stops(self):
        post={'definitions':{'D':{'name':'D','registered_at':3,'constituents':[{'slot_index':0,'registered_at':3,'alive':True,'relation':{'relation_id':'seal','predicate':'one'}}]}}}
        with self.assertRaises(RuntimeError):diag.update_birth_names(post,{'seal':{'predicate':'two','trial':2,'source':'記録'}},3,{}, {'seal'})

    def test_content_adds_one_definition_and_preserves_links(self):
        scene=RelationGraph('complete',relations=(Relation('r1','a',('e',)),Relation('r2','link',('r1','e'))))
        new,d=diag.add_content_definition(self.state,scene,9,'DIAG_TEST')
        self.assertEqual(set(new.definitions),{'D','DIAG_TEST'})
        self.assertIs(new.definitions['D'],self.d)
        self.assertEqual(set(self.state.definitions),{'D'})
        self.assertTrue(all(r.alive for r in d.constituents))
        self.assertEqual(d.constituents[1].relation.arguments,(d.constituents[0].relation.relation_id,'e'))
        self.assertIs(new.slot_history,self.state.slot_history);self.assertIs(new.p_hat,self.state.p_hat)
        with self.assertRaises(ValueError):diag.add_content_definition(new,scene,9,'DIAG_TEST')

    def test_prediction_comparison_checks_argument_order(self):
        out=AgentOutput(EdgePrediction(Relation('x','p',('a','b'))),{'R_used':'D'})
        row={'R_used':'D','predicted_edge':{'predicate':'p','arguments':['a','b']}}
        self.assertTrue(diag.same_prediction(out,row))
        row['predicted_edge']['arguments']=['b','a'];self.assertFalse(diag.same_prediction(out,row))

    def test_past_latest_two_per_shop_and_only_actual_disclosure(self):
        partial=RelationGraph('seen',relations=(Relation('visible','p',('a',)),))
        held=Relation('hidden','q',('b',));wt=SimpleNamespace(target_graph_partial=partial,held_out_edge=held)
        past={}
        diag.record_experience(past,wt,{'shop_cue':'n','shop_type':'A'},True,0)
        self.assertFalse(past)
        for t,shop,disclosed in ((1,'A',False),(2,'B',True),(3,'A',True),(4,'A',False)):
            diag.record_experience(past,wt,{'shop_cue':'e','shop_type':shop},disclosed,t)
        self.assertEqual([t for t,g in past['A']],[3,4])
        self.assertEqual([t for t,g in past['B']],[2])
        self.assertEqual(past['A'][0][1].relations,(*partial.relations,held))
        self.assertEqual(past['A'][1][1].relations,partial.relations)
        self.assertEqual(wt.target_graph_partial,partial)

    def test_past_material_requires_two_strictly_earlier_scenes(self):
        scene=RelationGraph('s')
        out,d,reason=diag.add_past_definition(self.state,[(1,scene)],3,None,99,'test')
        self.assertIs(out,self.state);self.assertIsNone(d);self.assertEqual(reason,'材料なし')
        with self.assertRaises(ValueError):diag.add_past_definition(self.state,[(1,scene),(3,scene)],3,None,99,'test')

    def test_past_uses_birth_function_and_only_adopts_new_definition(self):
        import v310be,abm.sme as sme
        base=RelationGraph('old');target=RelationGraph('recent');alignment=object();seen={}
        cfg=SimpleNamespace(pricing_rule='test_price',refill_rule='test_refill',local_lambda=0.7)
        def birth(s,b,t,a,trial,name,kw):
            seen.update(state=s,base=b,target=t,alignment=a,trial=trial,name=name,kw=kw)
            born=replace(self.d,registered_at=trial)
            return replace(s,definitions={'D':born},slot_history={('D',0):{'extra':99}}),'D'
        with patch.object(sme,'map_graphs',return_value=SimpleNamespace(alignment=alignment)),patch.object(v310be,'hypo_m1',side_effect=birth):
            new,d,reason=diag.add_past_definition(self.state,[(1,base),(2,target)],9,cfg,1740,'test')
        self.assertIsNone(reason);self.assertEqual(d.name,'D_DIAG_test')
        self.assertEqual(set(new.definitions),{'D','D_DIAG_test'});self.assertIs(new.definitions['D'],self.d)
        self.assertIs(new.slot_history,self.state.slot_history);self.assertIs(new.p_hat,self.state.p_hat)
        self.assertEqual(seen['state'].definitions,{});self.assertEqual(seen['state'].slot_history,{})
        self.assertIs(seen['base'],base);self.assertIs(seen['target'],target);self.assertIsNone(seen['name'])
        self.assertEqual(seen['kw'],{'base_written_at':1,'horizon':1740,'pricing_rule':'test_price','refill_rule':'test_refill','local_lambda':0.7})
        self.assertEqual(set(self.state.definitions),{'D'})

    def test_model_uses_installed_selector_and_records_before_gate(self):
        import abm.loop as loop
        seen=[]
        def installed(st,scene,cfg):seen.append(st);return (0,0,self.d)
        def predict(ai,st,cfg,rng):
            v39.select_definition(st,None,cfg)
            return AgentOutput(Abstain('below_tau'),{'R_used':None}),None
        with patch.object(v39,'select_definition',side_effect=installed) as selector,patch.object(loop,'predict',side_effect=predict):
            result=diag.model_answer(self.state,None,None,123,Relation('held','p',()),'D')
            self.assertIs(v39.select_definition,selector)
        self.assertEqual(seen,[self.state]);self.assertTrue(result['added_selected'])
        self.assertEqual(result['selected_R'],'D');self.assertIsNone(result['R_used'])
        self.assertEqual(result['outcome'],'黙り')

    def test_inventory_missing_is_not_zero_result(self):
        with tempfile.TemporaryDirectory() as folder:
            inv=diag.inventory([Path(folder)])[0]
            self.assertFalse(inv['ready']);self.assertEqual(inv['missing'],list(range(1,21)))
            self.assertEqual(inv['present'],[])

    def test_initial_state_is_the_models_empty_v39_state(self):
        state=diag.initial_state()
        self.assertEqual(state.definitions,{})
        self.assertEqual(state.prototype.traces,())
        self.assertEqual(state.p_hat.counts,{})
        self.assertEqual(state.v39_seats,{})


if __name__=='__main__':unittest.main()
