"""集合の表示順の非干渉と、状態・順序・乱数の変更を見落とさない検査。"""
import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT))
from v311c_fingerprint import canonical_text, fingerprint


def test_python_hash_seed_012_same_state_fingerprint():
    code = '''from abm.domains import AgentState
from abm.definition import FrequencyTable
from v311c_fingerprint import fingerprint
s=AgentState(p_hat=FrequencyTable({'fold':1,'wrap':1,'lock':1,'push':1},4,0.5,frozenset(('fold','wrap','lock','push'))))
print(fingerprint(s))'''
    env = dict(os.environ, PYTHONPATH=str(ROOT/'tools')+os.pathsep+str(ROOT))
    hashes = [subprocess.check_output([sys.executable, '-c', code], cwd=ROOT,
              env=dict(env, PYTHONHASHSEED=str(n)), text=True).strip() for n in (0,1,2)]
    assert len(set(hashes)) == 1


def test_nested_sets_same_without_mutating_state():
    @dataclass(frozen=True)
    class State:
        sets: object
        sequence: tuple

    a = State(frozenset((('fold', frozenset(('wrap','lock'))), ('push', frozenset()))), (3,None,1))
    b = State(frozenset((('push', frozenset()), ('fold', frozenset(('lock','wrap'))))), (3,None,1))
    before = repr(a)
    assert fingerprint(a) == fingerprint(b)
    assert repr(a) == before


@pytest.mark.parametrize('a,b', [
    ({'fold','wrap'}, {'fold','lock'}),
    ((1,2), (2,1)), ([1,2], [2,1]),
    ({'a':1,'b':2}, {'b':2,'a':1}),
    ((3,None,1), (3,1)), ((1,2), [1,2]),
    (1, True), (0.0, -0.0), (frozenset(('a',)), {'a'}),
])
def test_state_or_meaningful_order_change_changes_fingerprint(a,b):
    assert fingerprint(a) != fingerprint(b)


def test_rng_order_preserved():
    from random import Random
    rng = Random(1)
    before = rng.getstate()
    fingerprint(before)
    assert rng.getstate() == before
    rng.random()
    assert fingerprint(before) != fingerprint(rng.getstate())
    assert fingerprint(before) != fingerprint((before[0], tuple(reversed(before[1])), before[2]))


def test_unknown_type_rejected():
    with pytest.raises(TypeError, match='未対応の型'):
        canonical_text(object())
