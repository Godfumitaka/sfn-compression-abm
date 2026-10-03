import os,sys,json,hashlib
from pathlib import Path
from dataclasses import replace
from random import Random
from types import SimpleNamespace
R=Path(__file__).parent; os.environ['SW_TREE']=str(R/'source');os.environ['SW_FLAGS']='u_struct,relearn_init,tie_struct,amb_local'
import swcommon as sw
import v39,strictpc,answergap,v310be as B
from abm.definition import Constituent,NamedDefinition
from abm.domains import Entity,Relation,RelationGraph,Prototype,VerbatimTrace,AgentInput,EdgePrediction
strictpc.install(); answergap.install();sw.setup(T=1740)
rows=tuple(Constituent(k,0,Relation(i,p,args),sw.PRICE,True) for k,(i,p,args) in enumerate([('r0','fold',('x','y')),('r1','lock',('x','y')),('r2','cause',('r0','r1'))]))
d=NamedDefinition('D',rows,3,0,1)
sc=RelationGraph('scene',(Entity('a'),Entity('b')),(Relation('s1','lock',('a','b')),Relation('s2','cause',('hid','s1'))))
strictpc.record_kinds(sc)
ph=sw.ptable(fold=16,lock=8,cause=4)
sh={('D',k):{row.relation.predicate:1} for k,row in enumerate(rows)}
st=sw.S39(definitions={'D':d},slot_history=sh,p_hat=ph)
st=replace(st,prototype=Prototype((VerbatimTrace(0,sc),)))
st=v39.reconcile(st,0,'検査')
cfg=SimpleNamespace(threshold=0.,tau_acc=.67,local_lambda=1.,higher_order_predicates=frozenset({'cause'}),fill_selection='most_frequent',verbatim_threshold=.3842)
fp0=hashlib.sha256(repr(st).encode()).hexdigest()
out,pending=v39.predict(AgentInput(sc,sc,frozenset(r.relation_id for r in sc.relations)),st,cfg,Random(1))
held=Relation('hid','fold',('b','a'))
ans=v39.CTX['answers'];B.CTX['L_score']=v39.code_lengths(ph)
seats,scored=B.score_answers_role(st.v39_seats,ans,held,1)
expected=float(B.CTX['L_score']['fold'])
r={'definition':[(row.relation.relation_id,row.relation.predicate,row.relation.arguments) for row in rows],'visible':[(x.relation_id,x.predicate,x.arguments) for x in sc.relations],'held':held.to_dict(),'prediction':out.prediction.edge.to_dict() if isinstance(out.prediction,EdgePrediction) else str(out.prediction),'actual_hit':isinstance(out.prediction,EdgePrediction) and out.prediction.edge.predicate==held.predicate and out.prediction.edge.arguments==held.arguments,'support':out.trace.get('support_at_adoption'),'FH':out.trace.get('m_live'),'items':ans['items'],'expected_F_rewrite_bits':expected,'recorded_score':scored,'pre_state_unchanged':hashlib.sha256(repr(st).encode()).hexdigest()==fp0}
(R/'analysis/role_args_example.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
