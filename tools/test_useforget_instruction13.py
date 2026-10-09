"""指示13：試験内の入力・誕生・変換とD全控えの不変。復元せず途中で検査。"""
from types import SimpleNamespace as NS
import sys
import pytest
import abm.loop as loop
import useforget as D
import useforget_cstar as N
import useforget_evaluation as E
import v39
import probeworld as P
import cfvalue
import cflearn
from abm.domains import EdgePrediction, Relation
from test_useforget_instruction9 import case


@pytest.fixture
def installed(case, monkeypatch, request):
    state, scene, config, res, root = case
    mode = request.param
    for module, names in [(loop, ('predict', '_agent_input', 'm1')),
                          (v39, ('select_definition', '_candidates', 'reconcile'))]:
        for name in names:
            monkeypatch.setattr(module, name, getattr(module, name))
    monkeypatch.setattr(v39, 'select_definition', lambda *a: res)
    monkeypatch.setattr(loop, '_agent_input', lambda trial, state: scene)
    monkeypatch.setattr(loop, 'm1', lambda *a, **k: (state, {'was_extension':False,'R':'D'}))
    monkeypatch.setattr(v39, 'reconcile', lambda *a: state)
    monkeypatch.setattr(v39, '_candidates', lambda *a: ['native'])
    monkeypatch.setattr(E, 'CHECKS', [])
    monkeypatch.setattr(E, '_DEPTH', 0)
    prediction = NS(prediction=EdgePrediction(Relation('sme_projection__s','a',('u',))),
                    trace={'R_used':'D'})
    def predict(ai, current, cfg, rng):
        v39.select_definition(current, ai, cfg)
        return prediction, None
    monkeypatch.setattr(loop, 'predict', predict)
    D.install(root/'legacy.jsonl', tau=.4, horizon=200)
    D.ST['t'] = 2
    if mode != 'legacy':
        N.install(root/'audit.jsonl', expected_usage=True, attention_usage=mode=='q_attention')
    yield state, scene, config, res, prediction, root, mode
    D.close()


@pytest.mark.parametrize('installed', ['legacy','q','q_attention'], indirect=True)
def test_all_D_callbacks_are_inert_during_evaluation(installed):
    state, scene, config, res, output, root, mode = installed
    before = N.probe_snapshot()
    with E.evaluation():
        # 試験の途中でも照合。後で元に戻して通す余地を残さない。
        assert loop._agent_input(NS(trial=900),state) is scene
        assert N.probe_snapshot() == before
        assert loop.predict(scene,state,config,None)[0] is output
        assert N.probe_snapshot() == before
        loop.m1(state,scene,scene,None,900)
        assert N.probe_snapshot() == before
        v39.reconcile(state,900,'synthetic')
        assert N.probe_snapshot() == before
        assert v39._candidates(state,res[2],900,None,1) == ['native']
        v39.run_conversions(state,900)
        assert N.probe_snapshot() == before
        D._birth(('new',0,900),900)
        D._use(('new',0,900),900)
        D._record_matching(state,scene,res)
        D._record_answer(state,output)
        if mode != 'legacy':
            N.use_amount(('new',0,900),900,1.)
        assert N.probe_snapshot() == before
    assert N.probe_snapshot() == before
    # 本物の入口では同じ使用と誕生を数える。
    loop._agent_input(NS(trial=2),state)
    loop.predict(scene,state,config,None)
    assert D.ST['stats']['uses'] == 1 and D.ST['S']['D',0,0] == (2,[1.]*16)
    loop.m1(state,scene,scene,None,3)
    assert D.ST['born']['D',0,0] == 3


@pytest.mark.parametrize('installed', ['legacy','q','q_attention'], indirect=True)
@pytest.mark.parametrize('entry', ['probe','value','learn'])
def test_installed_probe_and_counterfactual_entries_suppress_D(installed, monkeypatch, entry):
    state, scene, config, res, output, root, mode = installed
    target = {'probe':(P,'_probe'), 'value':(cfvalue,'_measure'),
              'learn':(cflearn,'variants_correct')}
    for module, name in target.values():
        monkeypatch.setattr(module, name, getattr(module, name))
    def replay(*args, **kwargs):
        assert E.active()
        before = N.probe_snapshot()
        loop._agent_input(NS(trial=900),state)
        loop.predict(scene,state,config,None)
        loop.m1(state,scene,scene,None,900)
        v39.run_conversions(state,900)
        assert N.probe_snapshot() == before
        return 'native result'
    module, name = target[entry]
    monkeypatch.setattr(module, name, replay)
    E.install(root/'checks.json')
    before = N.probe_snapshot()
    assert getattr(module,name)(None,None,100) == 'native result'
    assert N.probe_snapshot() == before and not E.active()
    assert len(E.CHECKS)==1 and E.CHECKS[0]['unchanged']


def test_nested_evaluation_exception_does_not_touch_D(case, monkeypatch):
    monkeypatch.setattr(E, '_DEPTH', 0)
    before = N.probe_snapshot()
    with E.evaluation():
        with pytest.raises(ValueError):
            with E.evaluation():
                assert E.active()
                raise ValueError('synthetic')
        assert E.active() and N.probe_snapshot() == before
    assert not E.active() and N.probe_snapshot() == before
