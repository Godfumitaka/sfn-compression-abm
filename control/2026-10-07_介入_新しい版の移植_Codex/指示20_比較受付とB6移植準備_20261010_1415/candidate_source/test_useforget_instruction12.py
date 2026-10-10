"""指示12：D-最小の本物の予測の境界と、試験前後の全控え不変。"""
from types import SimpleNamespace as NS
import pytest
import abm.loop as loop
import probeworld as P
import useforget as D
import useforget_cstar as N
import v39
from abm.domains import EdgePrediction, Relation
from test_useforget_instruction9 import case


@pytest.mark.parametrize('attention', [False, True])
def test_saved_probe_predict_does_not_record_D_use(case, monkeypatch, attention):
    state, scene, config, res, root = case
    for module, names in [(loop, ('predict', '_agent_input', 'm1')),
                           (v39, ('select_definition', '_candidates', 'reconcile')),
                           (P, ('ST', '_probe'))]:
        for name in names:
            monkeypatch.setattr(module, name, {} if isinstance(getattr(module, name), dict)
                                else getattr(module, name))
    monkeypatch.setattr(N, 'PROBE_CHECKS', [])
    monkeypatch.setattr(v39, 'select_definition', lambda *args: res)

    def prediction(ai, current, cfg, rng):
        v39.select_definition(current, ai, cfg)
        return NS(prediction=EdgePrediction(Relation('sme_projection__s', 'a', ('u',))),
                  trace={'R_used': 'D'}), None

    monkeypatch.setattr(loop, 'predict', prediction)
    # probeworld.installと同じ順で、Dを入れる前の予測口を控える。
    P.ST['predict'] = loop.predict
    D.install(root/'legacy.jsonl', tau=.4, horizon=200)
    D.ST['t'] = 2
    N.install(root/'audit.jsonl', expected_usage=True, attention_usage=attention)
    monkeypatch.setattr(P, '_probe', lambda *args: P.ST['predict'](scene, state, config, None))
    N.install_probe_guard()
    before = N.probe_snapshot()
    P._probe(state, config, 100)
    assert N.probe_snapshot() == before
    assert D.ST['stats']['uses'] == 0 and not D.ST['S']
    assert N.PROBE_CHECKS == [dict(trial=100, unchanged=True,
        before_sha256=__import__('hashlib').sha256(before).hexdigest(),
        after_sha256=__import__('hashlib').sha256(before).hexdigest())]
    # 同じ選択を本物の予測口に通すと、照合と答えのmax一回が数えられる。
    loop.predict(scene, state, config, None)
    assert D.ST['stats']['uses'] == 1 and D.ST['S']['D', 0, 0] == (2, [1.] * 16)
    D.close()


@pytest.mark.parametrize('change', ['state', 'audit', 'file'])
def test_probe_guard_stops_without_restoring_changed_material(case, monkeypatch, change):
    root = case[-1]
    monkeypatch.setattr(N, 'PROBE_CHECKS', [])
    monkeypatch.setattr(P, '_probe', P._probe)
    N.install(root/'audit.jsonl', expected_usage=True)

    def bad_probe(*args):
        if change == 'state':
            D.ST['S']['unexpected', 0, 0] = (2, [1.] * 16)
        elif change == 'audit':
            N.AUDIT['matching'].append({'unexpected': True})
        else:
            N.AUDIT['f'].write('unexpected\n')

    monkeypatch.setattr(P, '_probe', bad_probe)
    N.install_probe_guard()
    before = N.probe_snapshot()
    with pytest.raises(RuntimeError, match='試験がDの状態又は記録を変えた'):
        P._probe(None, None, 100)
    assert N.probe_snapshot() != before
    assert N.PROBE_CHECKS[-1]['unchanged'] is False
