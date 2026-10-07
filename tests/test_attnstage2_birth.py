"""誕生の第一材料だけの情報、仮の問いの重み、初期値の容器を検査。"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
from abm.definition import Constituent,FrozenPrice,NamedDefinition,FrequencyTable
from abm.domains import Relation,RelationGraph,Entity
import attnratio as A
import attnstage2_birth as B
from attnstage2_questions import Snapshot
import v39


def materials():
    first=RelationGraph('first',(Entity('x'),),(
          Relation('door','hold',('x',)),Relation('seal','sig_n',('x',))))
    second=RelationGraph('second',(Entity('y'),),(
          Relation('d2','hold_b',('y',)),Relation('s2','sig_e',('y',))))
    rows=tuple(Constituent(i,0,replace(r,predicate='should_not_be_copied'),FrozenPrice(3,0,0,2),
                           alive=(i==0)) for i,r in enumerate(first.relations))
    definition=NamedDefinition('new',rows,2,2)
    before=v39._state_class()(p_hat=FrequencyTable({'hold':1,'sig_n':1},2,.1,frozenset({'hold','sig_n'})))
    return first,second,definition,before


def test_first_only_state_never_copies_second_material_name_or_counts():
    first,second,d,before=materials();saved=repr(before)
    hypo=B.first_only_state(before,d,first,2)
    assert repr(before)==saved and hypo.p_hat is before.p_hat
    assert [r.relation.predicate for r in hypo.definitions['new'].constituents]==['hold','sig_n']
    assert hypo.slot_history=={('new',0):{'hold':1},('new',1):{'sig_n':1}}
    assert [r.state for r in hypo.v39_seats.values()]==['F','H']
    assert set(hypo.p_hat.counts).isdisjoint({'hold_b','sig_e','should_not_be_copied'})


def test_partial_virtual_question_has_no_hidden_relation_or_name():
    first,second,_,_=materials()
    partial=B.partial_question(second,'d2')
    assert [r.predicate for r in partial.relations]==['sig_e']
    assert second.relations[0].predicate=='hold_b'


def test_birth_weights_and_losses_use_only_public_material_and_no_frequency_update():
    first,second,d,before=materials();saved=repr(before)
    snapshot=Snapshot(3,1,frozenset({'hold_b'}),frozenset(),True)
    calls=[]
    class Session:
        def __init__(self,state,scene,door):
            # 関係の名前の選びは、隠されたyを引数にせず、控えた候補に置く。
            calls.append((scene,door));self.attention={};self.background={}
            missing='hold_b' if door else 'sig_e'
            self.candidates=(A.Candidate('new',1,2,0,(),(missing,('y',)),{}),)
        choose=staticmethod(A.select)
        def rematched(self,seat):return replace(self.candidates[0],answer=None)
    initial,record=B.birth_values(before,d,first,second,snapshot,2,session_factory=Session,
                      loss_mode='alpha',length_of=lambda name:4 if name=='hold_b' else 2)
    assert len(calls)==2 and [door for _,door in calls]==[True,False]
    assert record['delta_by_slot']=={0:3.5,1:3.5}
    assert initial[0].init==((0.,)*16,(3.5,)*16,(3.5,)*16,(1.,)*16)
    assert initial[1].init==((0.,)*16,(0.,)*16,(3.5,)*16,(1.,)*16)
    assert record['thinned_seats']==4 and record['rerankings']==6
    assert record['first_material_common_delta']==0 and repr(before)==saved
    assert (snapshot.door,snapshot.other,snapshot.door_names)==(3,1,frozenset({'hold_b'}))


def test_unexperienced_virtual_type_has_zero_weight_and_no_model_call():
    first,second,d,before=materials()
    def forbidden(*a):raise AssertionError('経験のない種類で計算した')
    _,record=B.birth_values(before,d,first,second,Snapshot(1,0,frozenset(),frozenset(),True),2,
                 session_factory=forbidden,loss_mode='top1',length_of=forbidden)
    assert record['evaluated_questions']==0 and record['delta_by_slot']=={0:0,1:0}
    assert record['virtual_counts']['unassigned_mass']==1


def test_initial_zero_A_and_virtual_comparators_are_separate():
    rec=v39.SeatRec(0,'F',2,2,((9.,)*16,)*4,v39.ZERO4)
    value=B.initial_record(rec,-2,.75)
    assert B.choose_initial(rec,mode='A') is rec
    assert B.choose_initial(rec,mode='zero').init==v39.ZERO4
    assert B.choose_initial(rec,mode='virtual',virtual=value).init==value.init
    assert value.init[1]==(-2.,)*16
    with pytest.raises(ValueError):B.choose_initial(rec,mode='virtual')
