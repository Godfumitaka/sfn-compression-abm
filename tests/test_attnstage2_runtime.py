"""第二段の接続で、開示の前後と局所Aの置換を検査する。"""
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
from random import Random
from types import SimpleNamespace
import json
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import abm.loop as loop
from abm.domains import Abstain, AgentOutput, EdgePrediction, Relation
import attnratio as A
import attnsme
import attnstage2_runtime as R
import smeshared as S
import v39
import v310be as B


@dataclass(frozen=True)
class State:
    v39_seats: dict
    definitions: dict
    slot_history: dict
    p_hat: object = None


def setup(monkeypatch, tmp_path, output):
    stream=StringIO()
    for module,attrs in ((loop,('predict','_update_accounting','_ledger_record')),
                         (v39,('score_answers','_init_rec','reconcile'))):
        for key in attrs:monkeypatch.setattr(module,key,getattr(module,key))
    monkeypatch.setattr(R,'ST',{})
    monkeypatch.setattr(B,'CFG',{'score_logp':True})
    monkeypatch.setattr(v39,'CFG',{'decay':(.5,)*16})
    monkeypatch.setattr(v39,'_POW',{})
    monkeypatch.setattr(v39,'_init_rec',lambda *a,**kw:a[0])
    monkeypatch.setattr(v39,'reconcile',lambda state,*a:state)
    monkeypatch.setattr(loop,'predict',lambda *a:(output,None))
    monkeypatch.setattr(loop,'_update_accounting',lambda state,*a:(state,{'native_accounting':True}))
    monkeypatch.setattr(loop,'_ledger_record',lambda *a,**kw:{'native_record':True})
    monkeypatch.setattr(S,'_text_gzip',lambda path:stream)
    monkeypatch.setattr(attnsme,'ST',{'individual':{'observations':object(),'a':{}},
                                    'door_task':True,'ranked':[],'mode':'binary','position':'k2'})
    return stream,tmp_path/'stage2.jsonl.gz'


def test_on_requires_attention_context_before_opening_output(tmp_path,monkeypatch):
    monkeypatch.setattr(attnsme,'ST',{})
    with pytest.raises(RuntimeError,match='初期値'):
        R.install(tmp_path/'not_created.jsonl.gz',loss_mode='arm')
    assert not (tmp_path/'not_created.jsonl.gz').exists()


def test_no_disclosure_never_reads_truth_or_builds_counterfactuals(monkeypatch,tmp_path):
    output=AgentOutput(prediction=Abstain(reason='no_definition'),trace={})
    stream,path=setup(monkeypatch,tmp_path,output)
    def forbidden(*a,**kw):raise AssertionError('非開示で読み取った')
    monkeypatch.setattr(R,'Session',forbidden)
    R.install(path,loss_mode='alpha',initial_policy=lambda rec,why,context:rec)
    state=State({}, {}, {})
    loop.predict(None,state,None,Random(1))
    # truthは属性を持たない。非開示ならアクセスする経路が無い。
    after,account=loop._update_accounting(state,output,None,None,16,None,
                   SimpleNamespace(t=1,f_fired=False,f_realized=.2),object())
    row=json.loads(stream.getvalue())
    assert after is state and account=={'native_accounting':True}
    assert row['reason']=='not_disclosed' and row['rows']==[] and row['rerankings']==0


def test_42five_global_background_is_wired_for_no_answer_slot(monkeypatch,tmp_path):
    output=AgentOutput(prediction=Abstain(reason='no_definition'),trace={})
    stream,path=setup(monkeypatch,tmp_path,output)
    state=State({}, {}, {},SimpleNamespace(counts={'hold':3,'other':2},total=5))
    monkeypatch.setattr(v39,'code_lengths',lambda *a:{})
    monkeypatch.setattr(B,'_ell',lambda *a:3.)
    seen=[]
    class Session:
        def __init__(self,ai,before,cfg,*a,**kw):
            self.candidates=()
            self.background=kw['readout_policy'].background(ai,before,cfg,True)
            seen.append(self.background)
        choose=staticmethod(A.select)
        def rematched(self,seat):raise AssertionError('定義が無い')
    monkeypatch.setattr(R,'Session',Session)
    R.install(path,loss_mode='top1',initial_mode='zero')
    loop.predict(None,state,None,Random(1))
    loop._update_accounting(state,output,None,None,16,None,
               SimpleNamespace(t=1,f_fired=True,f_realized=.2),Relation('answer','hold',('x',)))
    row=json.loads(stream.getvalue())
    assert seen==[{'hold':.6,'other':.4}]
    assert row['baseline_loss']['correct_mass']==.6
    assert row['baseline_loss']['source']=='background_no_candidate'
    assert row['baseline_readout'] is None


def test_real_query_frequency_once_and_disclosed_name_after_birth_accounting(monkeypatch,tmp_path):
    edge=Relation('answer','hold',('x',))
    output=AgentOutput(prediction=Abstain(reason='no_definition'),trace={})
    stream,path=setup(monkeypatch,tmp_path,output)
    R.install(path,loss_mode='alpha',initial_mode='zero')
    state=State({}, {}, {})
    loop.predict(None,state,None,Random(1))
    q=R.ST['question']
    assert (q.door,q.other,q.door_names)==(1,0,frozenset())
    loop._update_accounting(state,output,None,None,16,None,
               SimpleNamespace(t=1,f_fired=False,f_realized=.2),object())
    # m1は会計の後。この時点までは現在の未開示名も開示名も加えない。
    assert R.ST['current_pre'] is not None and R.ST['question'] is q
    result=loop._ledger_record('agent',object(),None,output,None,
               SimpleNamespace(f_fired=False),state)
    assert result=={'native_record':True} and R.ST['questions']['agent'].record()['door_names']==[]
    loop.predict(None,state,None,Random(1))
    assert R.ST['question'].door==2
    loop._ledger_record('agent',SimpleNamespace(held_out_edge=edge),None,output,None,
               SimpleNamespace(f_fired=True),state)
    assert R.ST['questions']['agent'].record()['door_names']==['hold']


def test_zero_birth_comparator_does_not_call_native_A_initial_value(monkeypatch,tmp_path):
    output=AgentOutput(prediction=Abstain(reason='no_definition'),trace={})
    stream,path=setup(monkeypatch,tmp_path,output)
    def forbidden(*a,**kw):raise AssertionError('zeroへAの初期値を混ぜた')
    monkeypatch.setattr(v39,'_init_rec',forbidden)
    monkeypatch.setattr(v39,'seat_state',lambda *a:'H')
    R.install(path,loss_mode='alpha',initial_mode='zero')
    state=State({}, {}, {})
    rec=v39._init_rec(object(),object(),state,object(),object(),2,1,None)
    assert rec.state=='H' and rec.init==v39.ZERO4 and rec.post==v39.ZERO4


def test_disclosed_delta_replaces_local_A_and_uses_prediction_memory(monkeypatch,tmp_path):
    edge=Relation('answer','hold',('x',))
    output=AgentOutput(prediction=EdgePrediction(edge),trace={})
    stream,path=setup(monkeypatch,tmp_path,output)
    rec=v39.SeatRec(0,'F',0,0,v39.ZERO4,v39.ZERO4)
    state=State({('good',0):rec},
                {'good':SimpleNamespace(name='good',constituents=(SimpleNamespace(slot_index=0),))},{})
    monkeypatch.setattr(v39,'seat_state',lambda *a:'F')
    monkeypatch.setattr(v39,'code_lengths',lambda *a:{})
    monkeypatch.setattr(B,'_ell',lambda *a:3.)
    seen=[]
    class Session:
        def __init__(self,ai,before,*a,**kw):
            seen.append(before)
            self.candidates=(A.Candidate('good',.6,1,0,(),('hold',('x',)),{}),
                             A.Candidate('wrong',.4,1,0,(),('other',('x',)),{}))
        choose=staticmethod(A.select)
        def rematched(self,seat):return replace(self.candidates[0],q=.1)
    monkeypatch.setattr(R,'Session',Session)
    R.install(path,loss_mode='alpha',initial_policy=lambda rec,why,context:rec)
    loop.predict(None,state,None,Random(1))
    assert v39.score_answers(state.v39_seats,object(),object(),1)==(state.v39_seats,[])
    after,_=loop._update_accounting(state,output,None,None,16,None,
              SimpleNamespace(t=1,f_fired=True,f_realized=.2),edge)
    row=json.loads(stream.getvalue())
    assert seen==[state] and state.v39_seats['good',0] is rec
    assert row['applied']==[['good',0]] and row['thinned_seats']==1 and row['rerankings']==2
    rf,rh,ru,n=v39.rec_means(after.v39_seats['good',0],1)
    assert rf==0 and rh==ru==row['rows'][0]['delta_fixed'] and n==1
    assert rh>0 and row['wrapper_seconds']>=row['seconds']>=0
