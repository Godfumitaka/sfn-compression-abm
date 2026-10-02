"""分類の重なりを、現行の予測が出す小例として保存する。分類の順は決めない。"""
from dataclasses import replace
import json
from stage1_examples import ROOT, SOURCE, graph, definition, predict, ratio, T, RR, answergap, strictpc, v39
from abm.definition import FrequencyTable
from abm.domains import AgentConfig, Prototype, VerbatimTrace
from abm.seed import load_seed, higher_order_predicates

sd=load_seed(str(SOURCE/'seeds/U-011_seed_v3a2.json'))
T.setup(T=1740)
RR._install(strict_pc=True)
answergap.install()
v39.CFG['amb_local']=True
motif=next(iter(sd.data['motif_structure']))
base,bids=graph(sd,motif,'B','base')
scene,sids=graph(sd,motif,'B','scene')
strictpc.record_kinds(base)
strictpc.record_kinds(scene)
original=definition(base,'R_B')
switch_ids={bids['0.0.0'],bids['1.0.0']}
d=replace(original,constituents=tuple(replace(r,alive=False,relation=replace(r.relation,predicate=v39.ERASED))
                                     if r.relation.relation_id in switch_ids else r for r in original.constituents))
hist={(d.name,r.slot_index):{r.relation.predicate:1} for r in d.constituents if r.alive}
counts={r.predicate:1 for r in base.relations}
counts['hold']=100
ph=FrequencyTable(counts,sum(counts.values()),.1,frozenset(counts))
state=replace(T.state([d],hist,{},ph=ph),prototype=Prototype((VerbatimTrace(0,base),)))
hid=sids['0.0.0']
truth=next(r for r in scene.relations if r.relation_id==hid)
partial=replace(scene,relations=tuple(r for r in scene.relations if r.relation_id!=hid))
config=AgentConfig(threshold=0,correction_mode='none',local_lambda=1,tau_acc=.67,
                   higher_order_predicates=higher_order_predicates(sd))
out,result=predict(state,partial,config)
switch_rows=[{'slot':r.slot_index,'rid':r.relation.relation_id,'state':v39.seat_state(d,r,hist)}
             for r in d.constituents if r.relation.relation_id in switch_ids]
saved={'motif':motif,'variant':'B','hidden_subtree':0,'truth':truth.to_dict(),
       'switch_rows':switch_rows,'result':result,'support':ratio(d,state,partial),
       'visible_switch':next(r for r in partial.relations if r.relation_id==sids['1.0.0']).to_dict(),
       'scene':partial.to_dict(),'definition_before_erasure':base.to_dict(),
       'definition_after_erasure':{'name':d.name,'rows':[r.relation.to_dict() for r in d.constituents]},
       'frequency_counts':counts,'fill_states':list(v39.CTX.get('fill_states',()))}
path=ROOT/'stage1'/'classification_overlap_example.json'
assert not path.exists()
path.write_text(json.dumps(saved,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'motif':motif,'truth':truth.predicate,'prediction':result['prediction'],
                  'switch_rows':switch_rows,'support':saved['support'],'fill_states':saved['fill_states']},ensure_ascii=False))
