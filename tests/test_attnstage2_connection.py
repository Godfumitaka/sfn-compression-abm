"""現SMEの小世界で、固定対応と再照合を全席で並べる。"""
from dataclasses import replace
from pathlib import Path
from random import Random
import sys
import pytest
import csv,json,os
from collections import Counter
from abm.definition import FrequencyTable
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
from test_sme2017_connection import separate,memory,partial
from abm.domains import AgentConfig,AgentInput,CorrectionMode,Entity,Relation,RelationGraph
import attnstage2 as T
from attnstage2_sme import Session
from attnsme_features import Observations
import attnsme
import v39
import ustruct
import smeshared as S


@pytest.fixture(autouse=True)
def retained_U_structure(separate):
    restore = ustruct.install_matching()
    yield
    restore()


def build():
    g = RelationGraph('old',(Entity('a'),),(
        Relation('anchor','fold',('a',)),Relation('seal','sig_n',('a',)),
        Relation('door','hold',('a',)),Relation('link','attach',('seal','door'))))
    visible = RelationGraph('now',(Entity('x'),),(
        Relation('an','fold',('x',)),Relation('s','sig_e',('x',)),
        Relation('l','attach',('s','hole'))))
    state = v39.reconcile(memory(g),1,'小例')
    config = AgentConfig(0,CorrectionMode.NONE,tau_acc=.67,local_lambda=1,
                         higher_order_predicates=frozenset({'attach'}))
    observation = Observations();observation.after(0,[r.to_dict() for r in g.relations],{'a'})
    observation.structure([r.to_dict() for r in visible.relations],{'x'})
    ai = AgentInput(g,visible)
    return state,config,observation,ai


def test_all_seats_single_step_small_world_and_state_rng_unchanged():
    state,config,obs,ai = build()
    rng = Random(1);pre = repr(state);rng_before=rng.getstate()
    before_log = dict(S.LOG);before_sme_rng = S.ENGINE.rng.getstate()
    session = Session(ai,state,config,rng_before,obs,{},mode='binary',position='k2',door_task=True)
    assert S.LOG==before_log and S.ENGINE.rng.getstate()==before_sme_rng
    native,_ = v39.predict(ai,state,config,rng)
    selected = session.choose(session.candidates,{})
    assert selected.answer == attnsme.answer_key(native.prediction)
    seats = [T.Seat('R',r.slot_index,'F',state.v39_seats['R',r.slot_index].gen)
             for r in state.definitions['R'].constituents]
    rows,work = T.compare_seats(session.candidates,{},seats,session.fixed,session.exact,
                               correct=('hold',('x',)),ell=3,mode='alpha',choose=session.choose)
    assert len(rows)==4 and work['rerankings']==9
    assert repr(state)==pre and rng_before==session.rng_state
    # 比較の不一致を望ましい方向へ補正しない。原因は対応の集合で診断する。
    for seat,row in zip(seats,rows):
        fixed = session.fixed(seat)
        exact = session.exact(seat)
        if fixed.q != exact[0].q:
            assert fixed.payload['ranked'][4].relation_mapping != exact[0].payload['ranked'][4].relation_mapping


def test_gate_rejudged_after_H_to_U_with_fixed_mapping():
    state,config,obs,ai = build()
    config = replace(config,tau_acc=.3)
    state,_ = v39._convert(state,'FH','R',1,1)
    session = Session(ai,state,config,Random(1).getstate(),obs,{},mode='binary',position='k2',door_task=True)
    seat = T.Seat('R',1,'H',state.v39_seats['R',1].gen)
    before = session.candidates[0]
    after = session.fixed(seat)
    assert before.n == 4 and after.n == 3
    assert after.payload['ranked'][1] == before.payload['ranked'][1]
    # H→Uの分母は再計算されたもの。元のnを固定する近似ではない。
    assert after.payload['ranked'][0] == after.payload['ranked'][1]/3
    assert before.payload['answer']['abstain_reason']=='below_tau'
    assert after.payload['answer']['abstain_reason']!='below_tau'


def test_one_step_H_U_exposes_U05j_answer_and_loss_difference():
    state,config,obs,ai = build()
    state,_ = v39._convert(state,'FH','R',1,1)
    session = Session(ai,state,config,Random(1).getstate(),obs,{},mode='binary',position='k2',door_task=True)
    seat = T.Seat('R',1,'H',state.v39_seats['R',1].gen)
    fixed = session.fixed(seat)
    exact = session.exact(seat)[0]
    assert 'seal' not in fixed.payload['ranked'][4].relation_mapping
    assert exact.payload['ranked'][4].relation_mapping['seal']=='s'
    assert exact.payload['ranked'][4].relation_mapping['link']=='l'
    rows,_ = T.compare_seats(session.candidates,{},[seat],session.fixed,session.exact,
                            correct=('hold',('x',)),ell=3,mode='alpha',choose=session.choose)
    assert rows[0]['loss_difference']==3


@pytest.mark.parametrize('mode',['binary','global','position'])
@pytest.mark.parametrize('position',['k1','k2'])
def test_rematching_affected_definition_matches_whole_memory_exact(mode,position,monkeypatch):
    from attnstage2_distribution import Readout
    state,config,obs,ai=build()
    # 本番の呼び出し別の抽選を用い、他の定義の探索順に依存させない。
    monkeypatch.setitem(S.CTX,'call_seed',True)
    monkeypatch.setitem(S.CTX,'tie_uniform',True)
    monkeypatch.setitem(S.CTX,'run_seed',1)
    monkeypatch.setitem(S.CTX,'trial',2)
    original=state.definitions['R']
    extra=memory(RelationGraph('extra',(Entity('a'),),tuple(
        replace(row.relation,predicate='sig_e' if row.slot_index==1 else
                'hold_b' if row.slot_index==2 else row.relation.predicate)
        for row in original.constituents)),'E')
    counts=Counter(state.p_hat.counts);counts.update(extra.p_hat.counts)
    state=replace(state,definitions={**state.definitions,**extra.definitions},
                  slot_history={**state.slot_history,**extra.slot_history},
                  p_hat=FrequencyTable(dict(counts),sum(counts.values()),.1,frozenset(counts)))
    state=v39.reconcile(state,2,'42prime小例')
    obs.after(1,[row.relation.to_dict() for row in extra.definitions['E'].constituents],{'a'})
    state,_=v39._convert(state,'FH','R',1,2)
    saved=repr(state);before_rng=S.ENGINE.rng.getstate()
    session=Session(ai,state,config,Random(1).getstate(),obs,{},mode=mode,position=position,door_task=True,
            readout_policy=Readout(lambda *a:{'hold':.25,'hold_b':.25}))
    seats=[T.Seat(d.name,row.slot_index,v39.seat_state(d,row,state.slot_history),
                  state.v39_seats[d.name,row.slot_index].gen)
           for d in state.definitions.values() for row in d.constituents
           if v39.seat_state(d,row,state.slot_history)!='U']
    for seat in seats:
        rematched=session.rematched(seat)
        exact=session.exact(seat)
        affected=next((c for c in exact if c.name==seat.definition),None)
        assert (rematched is None)==(affected is None)
        if rematched is not None:
            assert rematched.q==affected.q and rematched.answer==affected.answer
            assert rematched.payload['ranked'][1]==affected.payload['ranked'][1]
            assert rematched.payload['ranked'][4].entity_mapping==affected.payload['ranked'][4].entity_mapping
            assert rematched.payload['ranked'][4].relation_mapping==affected.payload['ranked'][4].relation_mapping
            assert rematched.payload['readout']==affected.payload['readout']
        for untouched in (c for c in exact if c.name!=seat.definition):
            before=next(c for c in session.candidates if c.name==untouched.name)
            assert before.q==untouched.q and before.answer==untouched.answer
        changed=tuple(rematched if c.name==seat.definition else c for c in session.candidates)
        changed=tuple(c for c in changed if c is not None)
        for attention in ({},{key:.5 for c in session.candidates for key,_ in c.mismatch}):
            for loss_mode in ('alpha','top1','mixture'):
                left=T.loss(changed,attention,('hold_b',('x',)),3,mode=loss_mode,
                            choose=session.choose,background=session.background)
                right=T.loss(exact,attention,('hold_b',('x',)),3,mode=loss_mode,
                            choose=session.choose,background=session.background)
                assert left.value==right.value and left.selected==right.selected
    assert repr(state)==saved and S.ENGINE.rng.getstate()==before_rng


def test_redundant_two_native_seats_counterfactuals_do_not_accumulate_shared_credit():
    state,config,obs,ai=build()
    # 二つの同じ形の手がかりのうち、片方だけを薄くする。
    g=RelationGraph('twins',(Entity('a'),),tuple(
        replace(r,predicate='sig_n' if r.relation_id=='seal' else r.predicate)
        for r in ai.base_graph.relations)+(Relation('anchor2','fold',('a',)),))
    visible=RelationGraph('twins_visible',(Entity('x'),),tuple(
        replace(r,predicate='sig_n' if r.relation_id=='s' else r.predicate)
        for r in ai.target_graph_partial.relations)+(Relation('an2','fold',('x',)),))
    state=v39.reconcile(memory(g),1,'二席')
    obs=Observations();obs.after(0,[r.to_dict() for r in g.relations],{'a'})
    obs.structure([r.to_dict() for r in visible.relations],{'x'})
    for slot in (0,4):state,_=v39._convert(state,'FH','R',slot,1)
    session=Session(AgentInput(g,visible),state,config,Random(1).getstate(),obs,{},
                    mode='binary',position='k2',door_task=True)
    baseline=session.choose(session.candidates,{})
    assert baseline.answer is not None
    seats=[T.Seat('R',slot,'H',state.v39_seats['R',slot].gen) for slot in (0,4)]
    before=repr(state)
    rows,_=T.compare_seats(session.candidates,{},seats,session.rematched,session.exact,
                      correct=baseline.answer,ell=3,mode='alpha',choose=session.choose)
    assert [r['delta_fixed'] for r in rows]==[0,0]
    assert [r['delta_exact'] for r in rows]==[0,0]
    assert repr(state)==before


def test_delta_uses_native_freed_bits_and_V_without_new_memory_cost(monkeypatch):
    import v310be as B
    monkeypatch.setattr(B,'STATS',{'zero_release':0,'retire_candidate_evals':0})
    monkeypatch.setattr(B,'CTX',{})
    monkeypatch.setitem(v39.CTX,'struct_cache',{})
    state,config,obs,ai=build()
    lengths=v39.code_lengths(state.p_hat)
    before_bits=v39.total_bits(state,lengths)
    rec=state.v39_seats['R',1]
    rows=[{'R':'R','slot':1,'state':'F','gen':rec.gen,'delta_fixed':3.}]
    seats,_=T.accumulate(state.v39_seats,rows,2)
    scored=replace(state,v39_seats=seats)
    assert v39.total_bits(scored,lengths)==before_bits
    fh=next(c for c in B.candidates(scored,scored.definitions['R'],2,lengths,1) if c[3]==1)
    assert fh[1]=='FH' and fh[0]==3/fh[4]
    thin,_=v39._convert(scored,'FH','R',1,2)
    assert before_bits-v39.total_bits(thin,lengths)==fh[4]
    # 旧Fの値では新Hを守らず、新H自身のΔrだけを次の比へ使う。
    row={'R':'R','slot':1,'state':'H','gen':thin.v39_seats['R',1].gen,'delta_fixed':2.}
    seats,_=T.accumulate(thin.v39_seats,[row],2)
    thin=replace(thin,v39_seats=seats)
    hu=next(c for c in B.candidates(thin,thin.definitions['R'],2,lengths,1) if c[3]==1)
    assert hu[1]=='HU' and hu[0]==2/hu[4]
    thinner,_=v39._convert(thin,'HU','R',1,2)
    assert v39.total_bits(thin,lengths)-v39.total_bits(thinner,lengths)==hu[4]


def test_epsilon_reaches_candidate_probability_and_ratio():
    state,config,obs,ai=build()
    for epsilon in (.2,.5,.8):
        session=Session(ai,state,config,Random(1).getstate(),obs,{},
                        mode='global',position='k2',door_task=True,epsilon=epsilon)
        # 場面と名前が合うF席に、同じεが混ぜと比の双方で使われる。
        item=next(d for d in session.candidates[0].payload['details']
                  if d.get('fixed_name')=='fold' and d.get('visible_name')=='fold')
        expected=(1-epsilon)+epsilon*item['b']
        assert item['P']==expected
        assert item['m']==-__import__('math').log(expected)+__import__('math').log(item['b'])


def test_seat_trial_table_with_two_competing_definitions():
    state,config,obs,ai = build()
    original = state.definitions['R']
    extra_graph = RelationGraph('old_exception',(Entity('a'),),tuple(
        replace(row.relation,predicate='sig_e' if row.slot_index==1 else
                'hold_b' if row.slot_index==2 else row.relation.predicate)
        for row in original.constituents))
    extra = memory(extra_graph,'E')
    counts = Counter(state.p_hat.counts);counts.update(extra.p_hat.counts)
    state = replace(state,definitions={**state.definitions,**extra.definitions},
                    slot_history={**state.slot_history,**extra.slot_history},
                    p_hat=FrequencyTable(dict(counts),sum(counts.values()),.1,frozenset(counts)))
    state = v39.reconcile(state,2,'比較の小例')
    obs.after(1,[r.to_dict() for r in extra_graph.relations],{'a'})
    correct = ('hold_b',('x',))
    result = []
    for trial,state_name in ((2,'F'),(3,'H')):
        before = state if state_name=='F' else v39._convert(state,'FH','R',1,trial)[0]
        for mode in ('binary','global','position'):
            for position in ('k1','k2'):
                session = Session(ai,before,config,Random(1).getstate(),obs,{},mode=mode,position=position,door_task=True)
                seats = [T.Seat(d.name,row.slot_index,v39.seat_state(d,row,before.slot_history),
                                before.v39_seats[d.name,row.slot_index].gen)
                         for d in before.definitions.values() for row in d.constituents
                         if v39.seat_state(d,row,before.slot_history)!='U']
                for loss_mode in ('alpha','beta'):
                    rows,_ = T.compare_seats(session.candidates,{},seats,session.fixed,session.exact,
                                    correct=correct,ell=3,mode=loss_mode,choose=session.choose)
                    for seat,row in zip(seats,rows):
                        fixed = session.fixed(seat);exact = next(c for c in session.exact(seat) if c.name==seat.definition)
                        fm = dict(fixed.payload['ranked'][4].relation_mapping)
                        em = dict(exact.payload['ranked'][4].relation_mapping)
                        # 同じ対応で点が違うなら、原因不明の近似差として止める。
                        if fm==em:
                            assert fixed.q == exact.q
                        cause = ('new_seal_and_link' if seat.definition=='R' and seat.slot==1 and
                                'seal' not in fm and em.get('seal')=='s' and em.get('link')=='l' else
                                'other_mapping_change' if fm!=em else 'same_mapping')
                        row.update(trial=trial,mode=mode,position=position,loss=loss_mode,
                                   exact_q=float(exact.q),fixed_mapping=json.dumps(fm,sort_keys=True),
                                   exact_mapping=json.dumps(em,sort_keys=True),cause=cause)
                        result.append(row)
    assert len(result)==192
    assert any(r['cause']=='new_seal_and_link' for r in result)
    target = os.environ.get('STAGE2_RECORD_DIR')
    if target:
        path = Path(target);path.mkdir(parents=True,exist_ok=True)
        with (path/'seat_trial_comparison.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
        (path/'seat_trial_comparison.json').write_text(json.dumps({
            'rows':len(result),'cases_by_cause':dict(Counter(r['cause'] for r in result)),
            'loss_different':sum(r['loss_difference']!=0 for r in result),
            'unknown_causes':0},ensure_ascii=False,indent=2)+'\n')
