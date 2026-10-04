"""同点の抽選と構造制約を、点の式・構造の鍵から独立に確かめる。"""
from pathlib import Path
from dataclasses import asdict
from fractions import Fraction
from types import SimpleNamespace as NS
from collections import Counter
import random
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'source/tools'), str(ROOT / 'source')]
import pytest
import sme2017 as sme
import smeshared as shared


def fail_key(*args):
    raise AssertionError('旗付きの順位に構造の鍵を使った')


def graph(prefix, branch=False):
    return sme.Graph(tuple(sme.Node(prefix + x, 'entity') for x in ('a', 'b', 'c')) + (
        sme.Node(prefix + 'p', 'relation', frozenset({'fold'}), (prefix + 'a', prefix + 'b')),
        sme.Node(prefix + 'q', 'relation', frozenset({'fold'}),
                 (prefix + ('a' if branch else 'b'), prefix + 'c'))))


@pytest.mark.parametrize('seed', [0, 1, 2, 7, 31, 991])
def test_ordered_whole_group_and_unequal_order(seed, monkeypatch):
    engine = sme._Engine(sme.Graph(()), sme.Graph(()), sme.Settings(), random.Random(seed), tie_uniform=True)
    monkeypatch.setattr(engine, '_key', fail_key)
    values = [frozenset({i}) for i in range(5)]
    score = {0: 1, 1: 3, 2: 3, 3: 3, 4: 2}
    expected_rng = random.Random(seed)
    groups = {}
    for v in set(values):
        groups.setdefault(-score[next(iter(v))], []).append(v)
    expected = []
    for k in sorted(groups):
        expected_rng.shuffle(groups[k]) if len(groups[k]) > 1 else None
        expected.extend(groups[k])
    actual = engine._ordered(values, lambda v: score[next(iter(v))], 'fixture')
    assert actual == expected
    assert [score[next(iter(v))] for v in actual] == [3, 3, 3, 2, 1]
    assert len(engine.choices) == 1
    assert set(engine.choices[0][1]) == {(1,), (2,), (3,)}
    assert engine.rng.getstate() == expected_rng.getstate()


@pytest.mark.parametrize('seed', range(12))
def test_no_key_any_internal_phase_and_one_to_one(seed, monkeypatch):
    left, right = graph('d', True), graph('s', True)
    engine = sme._Engine(left, right, sme.Settings(), random.Random(seed), tie_uniform=True)
    monkeypatch.setattr(engine, '_key', fail_key)
    result = engine.run()
    assert sme.validate(left, right, result)
    for candidate in result.candidates:
        # 選びを作る関数を使わず、全引数の写しを直接比べる。
        mapping = dict(candidate.entity_mapping) | dict(candidate.relation_mapping)
        assert len(set(mapping.values())) == len(mapping)
        for a, b in candidate.relation_mapping:
            assert tuple(mapping[x] for x in left.by_id[a].args) == right.by_id[b].args
    assert result.tied == tuple(i for i, c in enumerate(result.candidates) if c.score == result.best.score)
    assert any(p == 'score-height' for p, _ in result.choices)


def test_repeated_call_noise_and_snapshot():
    left, right = graph('d', True), graph('s', True)
    matcher = sme.Matcher(tie_uniform=True)
    rng_before = matcher.rng.getstate()
    first = matcher.match(left, right, tie_seed=42)
    matcher.match(right, left, tie_seed=789)
    assert matcher.match(left, right, tie_seed=42, use_cache=False) == first
    snap = matcher.snapshot()
    matcher.match(left, left, tie_seed=12)
    matcher.restore(snap)
    assert matcher.snapshot() == snap
    assert matcher.rng.getstate() == rng_before
    assert 'tie-uniform-v1' in matcher.match_key(left, right, 42)
    plain = sme.Matcher()
    assert not hasattr(plain, 'tie_uniform')
    assert 'tie-uniform-v1' not in plain.match_key(left, right, 42)


@pytest.fixture
def shared_uniform(monkeypatch):
    for name in ('CTX', 'CHOICES', 'GRAPHS', 'RESULTS', 'STATS'):
        monkeypatch.setattr(shared, name, {})
    monkeypatch.setattr(shared, 'ENGINE', sme.Matcher(tie_uniform=True))
    monkeypatch.setattr(shared, 'structural_key', fail_key)
    records = []
    monkeypatch.setattr(shared, '_log', records.append)
    shared.CTX.update(call_seed=True, tie_uniform=True, run_seed=1, trial=0)
    return records


def test_definition_all_remaining_ties(shared_uniform):
    graphs = [graph('d', False), graph('e', True)]
    assert shared.canonical_identity(graphs[0]) != shared.canonical_identity(graphs[1])
    scene = graph('s')
    rows = []
    for i, g in enumerate(graphs):
        shared.GRAPHS[g.fingerprint()] = g
        rows.append((1., 2, NS(name='D' + str(i), registered_at=4), None,
                     NS(sme_audit={'left': g.fingerprint()}), 2, Fraction(1)))
    # N3で下位の候補は抽選の集合に入れない。
    lower = (*rows[0][:2], NS(name='lower', registered_at=100), *rows[0][3:6], Fraction(1, 2))
    counts = Counter()
    for trial in range(64):
        shared.CTX['trial'] = trial
        chosen, tied = shared._definition_choice([*rows, lower], scene)
        record = shared_uniform[-1]
        expected = random.Random(record['tie_seed']).randrange(2)
        assert chosen is rows[expected]
        assert tied and len(record['set']) == 2 and record['selected'][0] == chosen[2].name
        snap = shared.snapshot()
        assert shared._definition_choice([*rows, lower], scene)[0] is chosen
        shared.restore(snap)
        counts[chosen[2].name] += 1
    assert set(counts) == {'D0', 'D1'}


def test_trace_all_remaining_ties(shared_uniform, monkeypatch):
    monkeypatch.setattr(shared, 'typed_graph', lambda x: x)
    scene = graph('s')
    ranked = []
    for i, g in enumerate([graph('d', False), graph('e', True)]):
        shared.GRAPHS[g.fingerprint()] = g
        ranked.append((NS(alignment=NS(total_score=3., sme_audit={'left': g.fingerprint()})),
                       NS(written_at=4, scene=NS(graph_id='trace' + str(i)))))
    counts = Counter()
    for trial in range(64):
        shared.CTX['trial'] = trial
        chosen = shared.choose_trace(ranked, scene)
        record = shared_uniform[-1]
        expected = random.Random(record['tie_seed']).randrange(2)
        assert chosen[0] is ranked[expected][0] and chosen[1] is ranked[expected][1]
        assert len(record['set']) == 2
        assert record['selected'][1] == chosen[1].scene.graph_id
        counts[chosen[1].scene.graph_id] += 1
    assert set(counts) == {'trace0', 'trace1'}


def test_same_point_formula_fixed_mapping():
    left, right = graph('d'), graph('s')
    old = sme.Matcher().match(left, right, tie_seed=42)
    new = sme.Matcher(tie_uniform=True).match(left, right, tie_seed=42)
    assert old.best.score == new.best.score
    assert old.best.breakdown == new.best.breakdown
    assert old.best.relation_mapping == new.best.relation_mapping
