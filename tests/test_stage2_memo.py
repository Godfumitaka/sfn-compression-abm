"""P5・P7rの完全な鍵、控え・乱数・計数と実反実仮想の不変を検査する。"""
from collections import Counter
from dataclasses import replace
from pathlib import Path
from random import Random
import copy
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
               str(Path(__file__).resolve().parents[1])]
import pytest
from test_attncstar import cstar, build, retained_U_structure
from test_sme2017_connection import separate
from test_cstar_stage2_reuse import counters
from cstar_matcher import CstarMatcher, CstarEngine
from cstar_reuse import Store
from sme2017 import Graph, Node, Settings
import attncstar as N
import attnstage2 as T
from attnstage2_distribution import Readout
from attnstage2_sme import isolated
import cstar_runtime as C
import smeshared as S
import strictpc
import stage2memo as M
import v39


@pytest.fixture(autouse=True)
def memo_reset():
    M.configure(False)
    yield
    assert not M.AUDITS
    M.configure(False)


@pytest.mark.parametrize('uniform', [False, True])
def test_engine_complete_key_result_rng_and_logical_counts(uniform, monkeypatch):
    rng = Random(36)
    runs = []
    original = CstarEngine.run
    def counted(self):
        runs.append(self)
        return original(self)
    monkeypatch.setattr(CstarEngine, 'run', counted)
    M.configure(True)
    for case in range(25):
        nodes = [Node('e', 'entity')]
        for i in range(3):
            nodes.append(Node(f'r{i}', 'relation', frozenset({f'p{i % 2}'}),
                              tuple(rng.choice(nodes).key for _ in range(1 + i % 2))))
        left = Graph(tuple(nodes))
        right = Graph(tuple(replace(n, state='F') for n in nodes))
        matcher = CstarMatcher(Settings(), tie_uniform=uniform)
        ps = {n.key: {'p0': .5, 'p1': .5} for n in nodes if n.kind != 'entity'}
        stats = counters()
        monkeypatch.setitem(S.CTX, 'trial', case)
        before = len(runs)
        with matcher.stage2_scope(None, stats):
            first = matcher.match(left, right, probabilities=ps, use_cache=False, tie_seed=8)
            again = matcher.match(left, right, probabilities=ps, use_cache=False, tie_seed=8)
        assert first is again and len(runs) == before + 1
        assert stats['match_calls'] == stats['engine_calls'] == 2
        assert stats['result_cache_hits'] == 0
        assert matcher.cache == matcher.cache_rng == {}
        # 分布を変えると、同じ形・種でも新しい点・対応を作る。
        changed = {key: {'p0': 0., 'p1': 1.} for key in ps}
        with matcher.stage2_scope(None, stats):
            actual = matcher.match(left, right, probabilities=changed, use_cache=False, tie_seed=8)
        M.configure(False)
        baseline = CstarMatcher(matcher.settings, tie_uniform=uniform)
        expected = baseline.match(left, right, probabilities=changed, use_cache=False, tie_seed=8)
        assert actual == expected and matcher.snapshot() == baseline.snapshot()
        M.configure(True)
        monkeypatch.setitem(S.CTX, 'trial', case + 100)
        before = len(runs)
        with matcher.stage2_scope(None, stats):
            matcher.match(left, right, probabilities=ps, use_cache=False, tie_seed=8)
        assert len(runs) == before + 1


@pytest.mark.parametrize('kind', ['unseeded', 'foundation', 'outside_scope'])
def test_engine_never_shortcuts_ineligible_calls(kind, monkeypatch):
    g = Graph((Node('e', 'entity'), Node('r', 'relation', frozenset({'p'}), ('e',))))
    m = CstarMatcher(tie_seed=7, tie_uniform=True)
    ps = {'r': {'p': 1.}}
    runs = []
    real = CstarEngine.run
    def counted(self):
        runs.append(1)
        return real(self)
    monkeypatch.setattr(CstarEngine, 'run', counted)
    M.configure(True)
    for _ in range(2):
        if kind == 'outside_scope':
            m.match(g, g, probabilities=ps, tie_seed=1, use_cache=False)
        else:
            with m.stage2_scope(Store() if kind == 'foundation' else None, counters()):
                m.match(g, g, probabilities=ps, tie_seed=None if kind == 'unseeded' else 1, use_cache=False)
    assert len(runs) == 2 and M.STATS['p5_hits'] == 0


def test_mapping_replays_shallow_counter_leak_with_current_caller(cstar, monkeypatch):
    state, cfg, obs, ai = build()
    raw = replace(ai.base_graph, graph_id='definition:R')
    real = S.OLD_MAP
    calls = []
    monkeypatch.setattr(strictpc, 'STATS', dict(calls=0, dropped=0, reasons=Counter(),
                        use_calls=Counter(), use_dropped=Counter()))
    def old_map(*args, **kw):
        n, reasons = 3, Counter({'検査用の子': 2})
        label = strictpc._use()
        strictpc.STATS['calls'] += 1
        strictpc.STATS['dropped'] += n
        strictpc.STATS['reasons'].update(reasons)
        strictpc.STATS['use_calls'][label] += 1
        strictpc.STATS['use_dropped'][label] += n
        calls.append(label)
        return real(*args, **kw)
    monkeypatch.setattr(S, 'OLD_MAP', old_map)
    # 種は本来callerを含む。ここでは固定して同じ鍵の再生時の分類を別途点検。
    monkeypatch.setattr(S, '_match_seed', lambda *args: 77)
    def predict():
        return S.map_graphs(raw, ai.target_graph_partial)
    def counterfactuals():
        return S.map_graphs(raw, ai.target_graph_partial)
    M.configure(True)
    results = []
    for call in (predict, counterfactuals):
        with isolated(), C.phase(state, cfg, ai.target_graph_partial, True), C.ENGINE.stage2_scope(None, counters()):
            results.append(call())
    assert results[0] is results[1] and len(calls) == 1 and M.STATS['p7_hits'] == 1
    assert strictpc.STATS['calls'] == strictpc.STATS['dropped'] == 0
    assert strictpc.STATS['reasons'] == Counter({'検査用の子': 4})
    assert strictpc.STATS['use_calls'] == Counter({'予測の場面の照合（逐語の記憶と提示）': 1,
                                                '反実仮想の予測': 1})
    assert strictpc.STATS['use_dropped'] == Counter({'予測の場面の照合（逐語の記憶と提示）': 3,
                                                  '反実仮想の予測': 3})


@pytest.mark.parametrize('mode', ['alpha', 'top1', 'mixture'])
def test_all_seat_values_calls_and_main_state_identical(cstar, retained_U_structure, mode):
    state, cfg, obs, ai = build()
    state, _ = v39._convert(state, 'FH', 'R', 1, 1)
    before = repr(state), repr(obs.__dict__), C.snapshot(), S.ENGINE.rng.getstate(), dict(S.STATS)
    def measure():
        session = N.Session(ai, state, cfg, Random(1).getstate(), obs, {'k': .5}, mode='global',
                            position='k2', door_task=True, epsilon=.01,
                            readout_policy=Readout(), feature_policy=N.Features())
        seats = [T.Seat(d.name, row.slot_index, v39.seat_state(d, row, state.slot_history),
                        state.v39_seats[d.name, row.slot_index].gen)
                 for d in state.definitions.values() for row in d.constituents]
        rows, work = T.compare_seats(session.candidates, {}, seats, session.rematched, session.exact,
            correct=('hold', ('x',)), ell=4., mode=mode, choose=session.choose,
            background=session.background, method='rematched')
        return rows, {k: v for k, v in work.items() if k != 'seconds'}
    old = measure()
    M.configure(True)
    assert measure() == old
    assert (repr(state), repr(obs.__dict__), C.snapshot(), S.ENGINE.rng.getstate(), dict(S.STATS)) == before
    assert M.STATS['p5_hits'] and M.STATS['p7_hits']


def test_birth_FH_HU_same_columns_and_records(cstar, retained_U_structure):
    from attnstage2_initial import VirtualInitial
    from attnstage2_questions import Snapshot
    state, cfg, obs, ai = build()
    definition = replace(state.definitions['R'], name='fresh', registered_at=2)
    context = dict(definition=definition, row=definition.constituents[0], first_material=ai.base_graph,
        second_visible=ai.target_graph_partial, trial=2, base_age=1,
        pre=(ai, state, cfg, Random(1).getstate(), obs, {}, True, (), None),
        questions=Snapshot(1, 1, frozenset({'hold'}), frozenset(), True))
    before = repr(state), repr(obs.__dict__), C.snapshot()
    def measure():
        policy = VirtualInitial(loss_mode='top1', mode='global', position='k2', epsilon=.01,
            readout_policy=Readout(), feature_policy=N.Features(), measure_birth_hu=True,
            session_class=N.Session)
        value = policy(v39.SeatRec(0, 'F', 2, 2, v39.ZERO4, v39.ZERO4), 'birth', context)
        return value, [{k: v for k, v in r.items() if k != 'seconds'} for r in policy.records]
    old = measure()
    M.configure(True)
    assert measure() == old
    assert (repr(state), repr(obs.__dict__), C.snapshot()) == before


def test_mapping_memo_requires_closed_logs_scope_and_current_trial(cstar, monkeypatch):
    M.configure(True)
    with C.ENGINE.stage2_scope(None, counters()):
        assert M.active(True, 7)
        record = M.begin_audit(True, 7)
        calls = M.end_audit(record)
        M.mapping_store(True, 7, ('key',), 'out', calls)
        assert M.mapping_hit(True, 7, ('key',)) == ('out', [])
        monkeypatch.setitem(S.LOG, 'f', object())
        assert not M.active(True, 7)
        monkeypatch.setitem(S.LOG, 'f', None)
        monkeypatch.setitem(S.CTX, 'trial', 19)
        assert M.mapping_hit(True, 7, ('key',)) is None
        assert not M.active(False, 7) and not M.active(True, None)
    assert not M.active(True, 7)


def test_audit_exception_and_nested_frames_are_cleaned(cstar):
    M.configure(True)
    with C.ENGINE.stage2_scope(None, counters()):
        outer = M.begin_audit(True, 7)
        try:
            inner = M.begin_audit(True, 7)
            try:
                raise ValueError('検査用の例外')
            except ValueError:
                pass
            finally:
                assert M.end_audit(inner) == []
        finally:
            assert M.end_audit(outer) == []
    assert not M.AUDITS
