"""(iii)の権限の境界・一本だけの追加・全記憶の初期評価を検査。"""
from dataclasses import fields, replace
from random import Random

import pytest

from test_sme2017_connection import separate
from test_attncstar import cstar, retained_U_structure, build
from abm.domains import Entity, RelationGraph
from attnstage2_questions import Snapshot
from intervention46_native import Frame
from intervention46_variants_instruction8 import (ExperienceLog, add_content, add_past,
                                                content_prediction, fixed_prediction, past_prediction)
import attncstar as N
import attnsme
import cstar_runtime as C
import smeshared as S
import v310be as B


@pytest.fixture
def context(cstar, retained_U_structure, monkeypatch):
    state, config, observations, ai = build()
    # 競合する元の一本を初期評価の入力から落とせないようにする。
    rival = replace(state.definitions['R'], name='competitor')
    state = replace(state, definitions={**state.definitions, rival.name:rival},
        slot_history={**state.slot_history, **{('competitor', key[1]):value
                      for key, value in state.slot_history.items() if key[0]=='R'}},
        v39_seats={**state.v39_seats, **{('competitor', key[1]):value
                   for key, value in state.v39_seats.items() if key[0]=='R'}})
    frame = Frame('agent', 2, state, ai, config, Random(1).getstate(), observations,
        {'fixed':0.3}, {'fixed':0.3}, Snapshot(1, 1, frozenset({'hold'}), frozenset(), True),
        True, None, None)
    flags = dict(attn_allin=True, stage2='on', stage2_init='virtual', stage2_loss='top1',
                 stage2_birth_hu=True, stage2_reuse='off', match_cstar_e=True,
                 logp_eps=.01, attn_sme='global', attn_position='k2')
    monkeypatch.setitem(C.CFG, 'match_cstar_e', True)
    monkeypatch.setitem(B.CFG, 'nohash', True)
    monkeypatch.setitem(attnsme.ST, 'active', False)
    base = ai.base_graph
    ids = {r.relation_id:'seen_'+r.relation_id for r in base.relations}
    target = RelationGraph('actual_second', (Entity('y'),), tuple(replace(r,
        relation_id=ids[r.relation_id], arguments=tuple(ids.get(x, 'y' if x=='a' else x)
                                                      for x in r.arguments)) for r in base.relations))
    log = ExperienceLog()
    log.append('agent', 0, 'shop', exception_scene=base, source='synthetic_seen_0')
    log.append('agent', 1, 'shop', exception_scene=target, source='synthetic_seen_1')
    return frame, flags, log, target


def test_complete_one_all_f_with_original_state_containers(context):
    frame, _, _, full = context
    frozen = frame.digest()
    augmented, definition = add_content(frame, full, 'DIAG')
    assert list(augmented.definitions) == [*frame.state.definitions, 'DIAG']
    assert len(definition.constituents) == len(full.relations)
    ids = {r.relation_id:row.relation.relation_id for r, row in zip(full.relations, definition.constituents)}
    for actual, row in zip(full.relations, definition.constituents):
        assert row.alive and row.relation.predicate == actual.predicate
        assert row.relation.arguments == tuple(ids.get(x,x) for x in actual.arguments)
        assert row.relation.attributes == actual.attributes
    for field in fields(augmented):
        if field.name != 'definitions':
            assert getattr(augmented, field.name) is getattr(frame.state, field.name)
    assert frame.digest() == frozen


def test_latest_two_same_shop_and_agent_without_sorting_or_gaps(context):
    frame, _, _, scene = context
    log = ExperienceLog()
    for t, shop in enumerate(('same','other','same','same')):
        log.append('agent',t,shop,exception_scene=scene,source=f'actual_{t}')
    later = replace(frame, trial=4)
    assert [e.trial for e in log.latest(later,'same')]==[2,3]
    assert [e.trial for e in log.latest(later,'other')]==[1]
    with pytest.raises(ValueError, match='全経験記録'):
        log.latest(replace(later,agent='different'), 'same')
    with pytest.raises(ValueError, match='全経験記録'):
        log.latest(replace(later,trial=5), 'same')
    with pytest.raises(ValueError, match='連続'):
        ExperienceLog().append('agent',1,'same',exception_scene=scene,source='skipped')


def test_complete_log_with_less_than_two_exceptions_is_material_absent(context):
    frame, flags, _, scene = context
    log = ExperienceLog()
    log.append('agent',0,'same',exception_scene=scene,source='actual_0')
    log.append('agent',1,'same',exception_scene=None,source='actual_1_normal')
    unchanged, definition, proof = add_past(frame,log,'same',flags,horizon=1740,name_suffix='test')
    assert unchanged is frame.state and definition is None and proof['status']=='材料なし'


def test_native_birth_initialization_retains_all_competing_memory(context, monkeypatch):
    frame, flags, log, _ = context
    frozen, runtime = frame.digest(), repr(S.snapshot())
    initial_states = []
    original = N.Session
    class CaptureSession(original):
        def __init__(self, ai, state, *args, **kwargs):
            assert all(name in state.definitions for name in frame.state.definitions)
            assert all(state.definitions[name] is definition for name, definition in frame.state.definitions.items())
            assert state.p_hat is frame.state.p_hat
            initial_states.append(tuple(state.definitions))
            super().__init__(ai, state, *args, **kwargs)
    monkeypatch.setattr(N, 'Session', CaptureSession)
    augmented, definition, proof = add_past(frame,log,'shop',flags,horizon=1740,name_suffix='test')
    assert definition is not None and initial_states
    assert list(augmented.definitions)==[*frame.state.definitions,definition.name]
    assert all(augmented.definitions[name] is d for name,d in frame.state.definitions.items())
    for field in ('slot_history','merit','embed','exceptions','v39_seats'):
        assert all(getattr(augmented,field)[key] is value for key,value in getattr(frame.state,field).items())
    for field in ('prototype','p_hat','rng_state'):
        assert getattr(augmented,field) is getattr(frame.state,field)
    assert proof['material_trials']==[0,1]
    assert proof['initial_records'][0]['measure_birth_hu'] is True
    assert frame.digest()==frozen and repr(S.snapshot())==runtime


def test_missing_or_current_experience_stops_before_birth(context):
    frame, flags, log, _ = context
    with pytest.raises(ValueError, match='全経験記録'):
        add_past(replace(frame,trial=1),log,'shop',flags,horizon=1740,name_suffix='test')
    with pytest.raises(ValueError, match='全経験記録'):
        add_past(frame,ExperienceLog(),'shop',flags,horizon=1740,name_suffix='test')


def test_different_flag_stops_before_birth(context):
    frame, flags, log, _ = context
    with pytest.raises(ValueError, match='同じ旗'):
        add_past(frame,log,'shop',{**flags,'stage2_reuse':'on'},horizon=1740,name_suffix='test')


def test_researcher_full_scene_bypasses_attention_and_retains_all_memory(context, monkeypatch):
    frame, flags, _, full = context
    frozen, runtime = frame.digest(), repr(S.snapshot())
    choice, select = S._definition_choice, __import__('v39').select_definition
    augmented, definition = add_content(frame, full, 'DIAG')
    assert not {r.relation.relation_id for r in definition.constituents} & set(frame.observations.arguments)
    def forbidden(*args, **kwargs):
        raise AssertionError('固定選択が注意の候補を呼んだ')
    monkeypatch.setattr(attnsme, 'public_candidates', forbidden)
    monkeypatch.setattr(N.Session, '__init__', forbidden)
    import v39
    original_predict = v39.predict
    calls = []
    def capture(ai, state, config, rng):
        assert ai is frame.agent_input and config is frame.config
        assert rng.getstate() == frame.rng_state
        assert list(state.definitions) == [*frame.state.definitions, 'DIAG']
        assert all(state.definitions[name] is d for name, d in frame.state.definitions.items())
        for field in fields(state):
            if field.name != 'definitions':
                assert getattr(state, field.name) is getattr(frame.state, field.name)
        calls.append(state)
        return original_predict(ai, state, config, rng)
    monkeypatch.setattr(v39, 'predict', capture)
    result = content_prediction(frame, full, flags, 'DIAG')
    assert len(calls) == 1 and result['iii_a']['selected'] == 'DIAG'
    assert result['evidence_scope'] == 'iii_a_upper_reference_only'
    assert 'iii_b' not in result
    assert frame.digest() == frozen and repr(S.snapshot()) == runtime
    assert S._definition_choice is choice and v39.select_definition is select
    evidence('iii_a', dict(result=result, observations_unchanged=True,
                           original_competing_definitions=list(frame.state.definitions)))


@pytest.mark.parametrize('tau_acc', [.3, .67, 1.])
def test_fixed_selection_answer_matches_native_Session_answer(context, tau_acc):
    frame, flags, _, _ = context
    frame = replace(frame, config=replace(frame.config, tau_acc=tau_acc))
    frozen, runtime = frame.digest(), repr(S.snapshot())
    with frame.isolated():
        session = frame.session(flags)
        row = next(r for r in session.ranked if r[2].name == 'R')
        _, payload = session.answer(row, frame.state)
        expected = {k:payload[k] for k in ('prediction_kind','predicted_edge','abstain_reason','R_used')}
    result = fixed_prediction(frame, flags, 'R')
    assert result['prediction'] == expected
    assert frame.digest() == frozen and repr(S.snapshot()) == runtime
    evidence(f'fixed_native_tau_{tau_acc}', dict(result=result, native_answer=expected,
                                                native_answer_equal=True))


def test_fixed_selection_restores_temporary_functions_after_failure(context, monkeypatch):
    frame, flags, _, _ = context
    import v39
    choice, select = S._definition_choice, v39.select_definition
    frozen, runtime = frame.digest(), repr(S.snapshot())
    def stopped(*args, **kwargs):
        raise RuntimeError('合成例の予測前の停止')
    monkeypatch.setattr(v39, 'predict', stopped)
    with pytest.raises(RuntimeError, match='合成例の予測前'):
        fixed_prediction(frame, flags, 'R')
    assert S._definition_choice is choice and v39.select_definition is select
    assert frame.digest() == frozen and repr(S.snapshot()) == runtime


def test_past_prediction_uses_same_birth_and_native_own_choice(context):
    frame, flags, log, _ = context
    frozen, runtime = frame.digest(), repr(S.snapshot())
    augmented, definition, proof = add_past(frame,log,'shop',flags,horizon=1740,name_suffix='test')
    assert definition is not None
    assert all(r.relation.relation_id in frame.observations.arguments for r in definition.constituents)
    expected = frame.prediction(flags, state=augmented)
    result = past_prediction(frame,log,'shop',flags,horizon=1740,name_suffix='test')
    assert result['prediction'] == expected
    assert result['material_trials'] == [0,1]
    assert result['birth'] == 'native_hypo_m1'
    assert result['initialization'] == 'native_VirtualInitial'
    assert result['competing_definitions'] == list(frame.state.definitions)
    assert frame.digest() == frozen and repr(S.snapshot()) == runtime
    evidence('iii_c', dict(result=result, native_prediction_equal=True,
                           observations_unchanged=True, material_source='synthetic_structure_only'))


def evidence(name, value):
    import json, os
    from pathlib import Path
    folder = os.environ.get('INTERVENTION46_INSTRUCTION8_EVIDENCE')
    if folder:
        (Path(folder)/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
