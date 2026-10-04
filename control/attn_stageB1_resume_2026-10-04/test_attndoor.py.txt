"""段Bの構造の検査。世界の成績は読まず、手例だけを使う。"""
from dataclasses import replace
from pathlib import Path
from random import Random
import sys

SOURCE=Path(__file__).resolve().parents[2]/'source'
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import attnsel as A
import attnsel_checks as C
import attndoor as D
import v39


def test_B4_door_names_swapped_in_F_and_H_keep_Q_exact():
    state,ai,config,truth=C.example()
    weights=dict.fromkeys(C.SEEN,1.)
    weights.update(hold=3.,hold_b=.3,sig_e=1.9)
    with C.matching(),A.isolated():
        for status in ('F','H'):
            current=state
            if status=='H':
                definitions={d.name:replace(d,constituents=tuple(replace(r,alive=False,relation=replace(r.relation,predicate=v39.ERASED)) if r.slot_index==0 else r for r in d.constituents)) for d in state.definitions.values()}
                history={**state.slot_history,**{(d.name,0):{'hold':2,'hold_b':3} for d in state.definitions.values()}}
                current=replace(state,definitions=definitions,slot_history=history)
            def swap(p):return {'hold':'hold_b','hold_b':'hold'}.get(p,p)
            changed=replace(current,definitions={d.name:replace(d,constituents=tuple(replace(r,relation=replace(r.relation,predicate=swap(r.relation.predicate))) if r.slot_index==0 else r for r in d.constituents)) for d in current.definitions.values()},slot_history={key:({swap(p):n for p,n in value.items()} if key[1]==0 else value) for key,value in current.slot_history.items()})
            left=A.candidates(current,ai.target_graph_partial)
            right=A.candidates(changed,ai.target_graph_partial)
            def values(candidates):
                return {c.definition.name:replace(c.terms,fixed_names=D.DOOR_NAMES).value(weights) for c in candidates}
            assert values(left)==values(right)
            assert len(left)==len(right)==2
            for c in left+right:
                tt=replace(c.terms,fixed_names=D.DOOR_NAMES)
                assert tt.gradient(weights)['hold']==tt.gradient(weights)['hold_b']==0.


def test_B5_H_ties_history_and_candidate_order_keep_actual_update_exact():
    state,ai,cfg,truth=C.example(extra_unknown=True)
    d=state.definitions['R_exception']
    d=replace(d,constituents=tuple(replace(r,alive=False) if r.slot_index==3 else r for r in d.constituents))
    state=replace(state,definitions={**state.definitions,d.name:d},slot_history={**state.slot_history,(d.name,3):{'sig_e':1,'sig_n':1}})
    with C.matching():
        for arm in (1,2):
            learner=A.Attention(enabled=True,seen=C.SEEN)
            frozen=learner.prepare('agent',1,ai,state,cfg,Random(1)).candidates
            candidates=tuple(D.FrozenCandidate(c.definition,c.n,c.support,c.terms,c.answer,{'R':c.definition.name}) for c in frozen)
            shuffled=tuple(replace(c,terms=replace(c.terms,histories=tuple(tuple(reversed(h)) for h in reversed(c.terms.histories)))) for c in reversed(candidates))
            assert any(('sig_e','sig_n') in c.terms.histories for c in candidates)
            a,b=D.DoorAttention(arm),D.DoorAttention(arm)
            x=a.prepare('agent',1,C.SEEN,True,{},candidates)
            y=b.prepare('agent',1,tuple(reversed(C.SEEN)),True,{},shuffled)
            ra,rb=a.finish(x,C.feedback(1,truth)),b.finish(y,C.feedback(1,truth))
            assert ra['updated'] and rb['updated']
            assert ra['L']==rb['L'] and ra['weights_after']==rb['weights_after']
            assert x.selected==y.selected


def test_static_fixed_names_do_not_insert_unseen_names_and_no_door_update():
    a=D.DoorAttention(2)
    baseline={'prediction_kind':'Abstain','abstain_reason':'no_prototype','predicted_edge':None}
    p=a.prepare('agent',0,['sig_n'],False,baseline,())
    assert a.weights=={'sig_n':1.} and p.payload is baseline
    record=a.finish(p,{'agent_id':'agent','prediction_order':0,'f_realized':.125,'f_fired':False})
    assert record['reason']=='not_door_task' and not record['updated']
    assert record['weights_before']==record['weights_after']=={'sig_n':1.}
    p=a.prepare('agent',1,['sig_n'],False,baseline,())
    record=a.finish(p,{'agent_id':'agent','prediction_order':1,'f_realized':.75,'f_fired':True,'feedback_content':{'predicate':'hold'}})
    assert a.weights=={'sig_n':1.,'hold':1.} and 'hold_b' not in a.weights
    assert record['reason']=='not_door_task' and not record['updated']
