"""模型を起動せず、forkの問いの順・研究者の数え・書出し口を確かめる。"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace as NS
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import attnstage2_birth as B
import attnstage2_birth_parallel as P
import attnstage2_runtime as RT
import strictpc
import v39


@dataclass(frozen=True)
class Relation:
    relation_id: int
    predicate: str
    arguments: tuple = ()


@dataclass(frozen=True)
class Material:
    relations: tuple
    entities: tuple = ()


@dataclass(frozen=True)
class SeatRec:
    state: str
    init: tuple = ()
    post: tuple = ()


class Questions:
    door = 3
    other = 9

    def __init__(self, n, zero=False):
        self.n, self.zero = n, zero

    def virtual_weights(self, values):
        assert len(list(values)) == self.n
        return [dict(**{'class': 'door' if i % 2 else 'other'}, weight=0. if self.zero else 1.)
                for i in range(self.n)], {'door': 3, 'other': 9}


def setup_mock(monkeypatch, count):
    fresh = NS(name='R', constituents=(NS(slot_index=2), NS(slot_index=0)))
    hypo = NS(definitions={'R': fresh}, slot_history={},
              v39_seats={('R', 2): SeatRec('F'), ('R', 0): SeatRec('H')})
    monkeypatch.setattr(B, 'first_only_state', lambda *args: hypo)
    monkeypatch.setattr(v39, 'seat_state', lambda definition, row, history: 'F' if row.slot_index == 2 else 'H')
    full = Material(tuple(Relation(i, str(i)) for i in range(count)))

    def factory(state, visible, door):
        index = next(i for i in range(count) if all(r.relation_id != i for r in visible.relations))
        assert door == (index % 2 == 1)
        return NS(candidates=index, attention=None, rematched=None, choose=None,
                  background=None, thin=lambda seat: state)

    def length_of(name):
        v39.STATS['L_unseen_name'] += 1
        return 1.

    def compare(candidates, attention, seats, *args, correct, ell, **kwargs):
        index = candidates
        # 後ろの問いが先に終わっても、親の加算は元の順である必要がある。
        time.sleep((count - index) * .0002)
        label = strictpc._use()
        strictpc.STATS['use_calls'][label] += 1
        strictpc.STATS['use_dropped'][label] += index
        strictpc.STATS['reasons'][str(index)] += 1
        strictpc.STATS['struct_bits_diff'] -= index
        strictpc.STATS['new_zero'][str(index)] += 0
        rows = [dict(slot=seat.slot, delta=(1e16, 1., -1e16)[index % 3]) for seat in seats]
        row = dict(origin='birth', question=index, **{key: index for key in P._KEYS})
        if RT.ST.get('rematch_stream') is not None:
            P._replay([json.dumps(row, ensure_ascii=False) + '\n'])
        return rows, dict(thinned_seats=len(seats), rerankings=1)

    monkeypatch.setattr(P.T, 'compare_seats', compare)
    return hypo, fresh, Material(()), full, Questions(count), factory, length_of


def m1(fn, args, hu):
    hypo, fresh, first, full, questions, factory, length = args
    return fn(hypo, fresh, first, full, questions, 17, session_factory=factory,
              loss_mode='arm', length_of=length, measure_birth_hu=hu)


def reset(stream):
    strictpc.STATS.clear()
    strictpc.STATS.update(use_calls=Counter(), use_dropped=Counter(), reasons=Counter(),
                          struct_bits_diff=0, new_zero=Counter())
    v39.STATS.clear()
    v39.STATS.update(L_unseen_name=0)
    RT.ST.clear()
    RT.ST.update(rematch_stream=stream, rematch_totals={})


@pytest.mark.parametrize('workers', [1, 4])
@pytest.mark.parametrize('hu', [False, True])
def test_parallel_matches_original_order_counts_and_gzip(monkeypatch, tmp_path, workers, hu):
    args = setup_mock(monkeypatch, 20)
    random_before = random.getstate()
    path = tmp_path / 'native.gz'
    with gzip.open(path, 'wt') as stream:
        reset(stream)
        initial, record = m1(P._ORIGINAL, args, hu)
    expected_bytes = gzip.open(path, 'rb').read()
    expected_counts = deepcopy((strictpc.STATS, v39.STATS))
    expected_totals = deepcopy(RT.ST['rematch_totals'])
    path2 = tmp_path / 'parallel.gz'
    with gzip.open(path2, 'wt') as stream:
        reset(stream)
        monkeypatch.setattr(P, '_WORKERS', workers)
        other_initial, other_record = m1(P.birth_values, args, hu)
        assert not stream.closed
        stream.write('parent-tail\n')
    actual_bytes = gzip.open(path2, 'rb').read()
    assert actual_bytes == expected_bytes + b'parent-tail\n'
    record.pop('seconds'); other_record.pop('seconds')
    assert other_initial == initial
    assert json.dumps(other_record, ensure_ascii=False) == json.dumps(record, ensure_ascii=False)
    assert json.dumps((strictpc.STATS, v39.STATS), ensure_ascii=False) == json.dumps(expected_counts, ensure_ascii=False)
    assert RT.ST['rematch_totals'] == expected_totals
    assert isinstance(strictpc.STATS['new_zero'], Counter)
    assert v39.STATS['L_unseen_name'] == 20 * (2 if hu else 1)
    assert random.getstate() == random_before
    assert not P._JOB


def test_zero_weight_does_not_fork(monkeypatch):
    args = list(setup_mock(monkeypatch, 3)); args[4] = Questions(3, zero=True)
    monkeypatch.setattr(P.mp, 'get_context', lambda *args: pytest.fail('重み0でforkしない'))
    reset(None)
    initial, record = m1(P.birth_values, args, False)
    assert record['evaluated_questions'] == 0
    assert all(row['reason'] == 'unexperienced_kind' for row in record['records'])
    assert v39.STATS['L_unseen_name'] == 0


def test_child_exception_propagates_and_clears_job(monkeypatch):
    args = setup_mock(monkeypatch, 3)
    monkeypatch.setattr(P.T, 'compare_seats', lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('問いの例外')))
    monkeypatch.setattr(P, '_WORKERS', 2)
    reset(None)
    with pytest.raises(ValueError, match='問いの例外'):
        m1(P.birth_values, args, False)
    assert not P._JOB


@pytest.mark.parametrize('after', [{}, {'n': True}, {'n': '2'}])
def test_stats_reject_deletion_or_non_numeric_change(after):
    with pytest.raises(ValueError):
        P._count_changes({'n': 1}, after)


def test_new_counter_keys_merge_in_original_order_with_zero():
    target = {'counts': Counter(old=3)}
    left = P._count_changes({'counts': Counter(old=3)}, {'counts': Counter(old=5, a=0)})
    right = P._count_changes({'counts': Counter(old=3)}, {'counts': Counter(old=7, b=1)})
    P._add_counts(target, left); P._add_counts(target, right)
    assert list(target['counts'].items()) == [('old', 9), ('a', 0), ('b', 1)]
    assert isinstance(target['counts'], Counter)


@pytest.mark.parametrize('value', [-1, 8, 1.5, True])
def test_workers_limit(value):
    with pytest.raises(ValueError):
        P.install(value)


def test_off_keeps_original_entry(monkeypatch):
    monkeypatch.setattr(B, 'birth_values', P._ORIGINAL)
    P.install(0)
    assert B.birth_values is P._ORIGINAL


def test_on_install_uses_one_entry(monkeypatch):
    monkeypatch.setattr(B, 'birth_values', P._ORIGINAL)
    monkeypatch.setattr(P, '_WORKERS', 0)
    P.install(4)
    assert B.birth_values is P.birth_values and P._WORKERS == 4
