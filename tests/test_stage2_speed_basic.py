"""指示25。分布・全席の値・同点・保存状態を元の部品と厳密に比べる。"""
from dataclasses import replace
from pathlib import Path
from random import Random
from types import SimpleNamespace as NS
import json
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
               str(Path(__file__).resolve().parents[1])]
import pytest
from abm.definition import Constituent, FrequencyTable
from abm.domains import Entity, Relation, RelationGraph
from abm.filling import _predicate_has_signature, slot_signature
from test_attncstar import cstar
from test_attnstage2_connection import build, retained_U_structure
from test_sme2017_connection import separate
import attncstar as N
import attnstage2 as T
import cstar_runtime as C
import cstar_probability as CP
import sme2017
import smereplay
import smeshared as S
import strictpc
import v310be as B
import v39
from smeprobpool import signature_index, signature_pool
from attnstage2_distribution import Readout


def enable(monkeypatch):
    monkeypatch.setitem(C.CFG, 'exact_speed', True)
    monkeypatch.setitem(v39.CFG, 'cstar_exact_speed', True)
    monkeypatch.setattr(CP, 'BACKGROUND_SOURCE', B.background_probabilities)
    monkeypatch.setattr(sme2017, 'FINGERPRINT_MEMO', True)
    monkeypatch.setattr(S, 'EXACT_SPEED', True)
    monkeypatch.setattr(S, 'TYPED_GRAPH_MEMO', {})
    monkeypatch.setattr(S, 'TYPED_GRAPH_TRIAL', None)


def test_signature_pool_matches_original_with_target_typed_definition_occurrences():
    rng = Random(25)
    names = tuple(f'p{i}' for i in range(7))
    for _ in range(100):
        def graph(label):
            rows = []
            for i in range(rng.randrange(1, 6)):
                available = ['a', 'b'] + [f'r{j}' for j in range(i)]
                rows.append(Relation(f'r{i}', rng.choice(names), tuple(
                    rng.choice(available) for _ in range(rng.randrange(3)))))
            return RelationGraph(label, (Entity('a'), Entity('b')), tuple(rows))
        scene, definition = graph('scene'), graph('definition')
        index = signature_index(scene, definition)
        vocabulary = frozenset((*names, 'unseen'))
        for row in definition.relations:
            sig = slot_signature(row, definition)
            old = frozenset(p for p in vocabulary
                           if _predicate_has_signature(p, sig, scene, definition))
            new = signature_pool(vocabulary, sig, index)
            assert old == new and tuple(old) == tuple(new)


@pytest.mark.parametrize('empty', [False, True])
def test_background_and_U_answer_keep_order_probabilities_and_ties(cstar, monkeypatch, empty):
    state, cfg, obs, ai = build()
    if empty:
        state = replace(state, p_hat=FrequencyTable({}, 0, .1, frozenset()))
    original = CP.BACKGROUND_SOURCE
    definition = state.definitions['R']
    old = [(original(definition, row, state, ai.target_graph_partial, cfg)['U'],
            v39.u_answer(definition, row, ai.target_graph_partial, state.p_hat,
                         cfg.higher_order_predicates)) for row in definition.constituents]
    enable(monkeypatch)
    new = [(B.background_probabilities(definition, row, state, ai.target_graph_partial, cfg)['U'],
            v39.u_answer(definition, row, ai.target_graph_partial, state.p_hat,
                         cfg.higher_order_predicates)) for row in definition.constituents]
    assert json.dumps(old) == json.dumps(new)


@pytest.mark.parametrize('match_eps', [0, 'shared'])
def test_Cstar_F_H_U_and_visible_trace_match_original(cstar, retained_U_structure, monkeypatch, match_eps):
    state, cfg, obs, ai = build()
    state, _ = v39._convert(state, 'FH', 'R', 1, 2)
    state, _ = v39._convert(state, 'FH', 'R', 2, 2)
    state, _ = v39._convert(state, 'HU', 'R', 2, 2)
    monkeypatch.setitem(C.CFG, 'match_eps', match_eps)
    raw = replace(ai.base_graph, graph_id='definition:R')
    typed = S.typed_graph(raw)
    def measure():
        with C.phase(state, cfg, ai.target_graph_partial, True):
            return [C.probabilities_for_graph(raw, typed, ai.target_graph_partial),
                    C.probabilities_for_graph(ai.base_graph, typed, ai.target_graph_partial),
                    N.common_bases(ai, state, cfg)]
    old = measure()
    enable(monkeypatch)
    assert json.dumps(measure()) == json.dumps(old)


def test_F_shortcut_never_skips_shared_probability(cstar, monkeypatch):
    state, cfg, obs, ai = build()
    enable(monkeypatch)
    real = C.distributions
    calls = []
    def counted(*args):
        calls.append(args[1].slot_index)
        return real(*args)
    monkeypatch.setattr(C, 'distributions', counted)
    with C.phase(state, cfg, ai.target_graph_partial, True):
        monkeypatch.setitem(C.CFG, 'match_eps', 0)
        C.probabilities_for_graph(ai.base_graph, S.typed_graph(ai.base_graph), ai.target_graph_partial)
        assert not calls
        monkeypatch.setitem(C.CFG, 'match_eps', 'shared')
        C.probabilities_for_graph(ai.base_graph, S.typed_graph(ai.base_graph), ai.target_graph_partial)
        assert len(calls) == len(ai.base_graph.relations)


def test_fingerprint_memo_preserves_hash_encoding_and_equal_graphs(monkeypatch):
    graph = sme2017.Graph((sme2017.Node('a', 'entity'),
                          sme2017.Node('r', 'relation', frozenset({'p'}), ('a',))))
    before = graph.fingerprint(), hash(graph), smereplay.encode(graph)
    monkeypatch.setattr(sme2017, 'FINGERPRINT_MEMO', True)
    for _ in range(3):
        assert (graph.fingerprint(), hash(graph), smereplay.encode(graph)) == before
    assert graph == replace(graph)
    assert '_fingerprint_memo' in graph.__dict__
    assert '_fingerprint_memo' not in replace(graph).__dict__


def test_typed_graph_memo_respects_registration_trial_and_object_identity(separate, monkeypatch):
    graph = RelationGraph('visible', (Entity('a'),), (Relation('r', 'p', ('a',)),))
    old = S.typed_graph(graph)
    monkeypatch.setattr(S, 'EXACT_SPEED', True)
    monkeypatch.setattr(S, 'TYPED_GRAPH_MEMO', {})
    monkeypatch.setattr(S, 'TYPED_GRAPH_TRIAL', None)
    first = S.typed_graph(graph)
    assert first == old and S.typed_graph(graph) is first
    monkeypatch.setitem(v39.REG, id(graph), (graph, {'r': frozenset({'q'})}))
    changed = S.typed_graph(graph)
    assert changed.by_id['r'].state == 'H' and changed.by_id['r'].names == frozenset({'q'})
    monkeypatch.delitem(v39.REG, id(graph))
    monkeypatch.setitem(strictpc.RELPOS, id(graph), frozenset())
    assert S.typed_graph(graph) is not first
    monkeypatch.delitem(strictpc.RELPOS, id(graph))
    monkeypatch.setitem(S.CTX, 'trial', 4)
    second = S.typed_graph(graph)
    assert second == first and second is not first
    assert S.TYPED_GRAPH_MEMO[id(graph)][0] is graph


@pytest.mark.parametrize('mode', ['alpha', 'top1', 'mixture'])
@pytest.mark.parametrize('match_eps', [0, 'shared'])
def test_all_seat_rematch_and_Cstar_state_are_identical(cstar, retained_U_structure, monkeypatch, mode, match_eps):
    state, cfg, obs, ai = build()
    state, _ = v39._convert(state, 'FH', 'R', 1, 2)
    monkeypatch.setitem(C.CFG, 'match_eps', match_eps)
    before = repr(state), repr(obs.__dict__), S.ENGINE.rng.getstate(), C.snapshot(), dict(S.STATS)
    def measure():
        session = N.Session(ai, state, cfg, Random(1).getstate(), obs, {}, mode='global',
                            position='k2', door_task=True, epsilon=.01,
                            readout_policy=Readout(), feature_policy=N.Features())
        seats = [T.Seat(d.name, row.slot_index, v39.seat_state(d, row, state.slot_history),
                        state.v39_seats[d.name, row.slot_index].gen)
                 for d in state.definitions.values() for row in d.constituents]
        rows, work = T.compare_seats(session.candidates, {}, seats, session.rematched,
            session.exact, correct=('hold', ('x',)), ell=4., mode=mode, choose=session.choose,
            background=session.background, method='rematched')
        work.pop('seconds')
        return rows, work
    old = measure()
    enable(monkeypatch)
    assert measure() == old
    assert (repr(state), repr(obs.__dict__), S.ENGINE.rng.getstate(), C.snapshot(), dict(S.STATS)) == before


def test_real_two_step_birth_uses_same_questions_and_values(cstar, retained_U_structure, monkeypatch):
    from attnstage2_initial import VirtualInitial
    from attnstage2_questions import Snapshot
    state, cfg, obs, ai = build()
    definition = replace(state.definitions['R'], name='fresh', registered_at=2)
    context = dict(definition=definition, row=definition.constituents[0], first_material=ai.base_graph,
        second_visible=ai.target_graph_partial, trial=2, base_age=1,
        pre=(ai, state, cfg, Random(1).getstate(), obs, {}, True, (), None),
        questions=Snapshot(1, 1, frozenset({'hold'}), frozenset(), True))
    def measure():
        policy = VirtualInitial(loss_mode='top1', mode='global', position='k2', epsilon=.01,
            readout_policy=Readout(), feature_policy=N.Features(), measure_birth_hu=True,
            session_class=N.Session)
        return policy(v39.SeatRec(0, 'F', 2, 2, v39.ZERO4, v39.ZERO4), 'birth', context)
    saved = repr(state), repr(obs.__dict__), C.snapshot()
    old = measure()
    enable(monkeypatch)
    assert measure() == old
    assert (repr(state), repr(obs.__dict__), C.snapshot()) == saved
