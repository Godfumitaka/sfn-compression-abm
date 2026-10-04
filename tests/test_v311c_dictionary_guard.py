"""辞書外の名前の計算を修正せず、個体・試行・名前を残して必ず停止する。"""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
               str(Path(__file__).resolve().parents[1])]
import v311c
import v39


@pytest.fixture
def guard(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(v311c, 'CFG', {'run': 1, 'agent': 6})
    monkeypatch.setattr(v311c, 'CTX', {'t': 17, 'fo': stream})
    monkeypatch.setattr(v311c, 'STATS', {})
    monkeypatch.setattr(v39, 'CFG', {'dict_index': {'fold': 0, 'wrap': 1}})
    monkeypatch.setattr(v39, 'STATS', {})
    monkeypatch.setattr(v39, 'dict_order', v39.dict_order)
    v311c._install_dictionary_guard()
    return stream


def test_known_name_passes_without_changing_cost_or_model_counter(guard):
    assert v39.dict_order('fold') == 0
    assert v39.dict_order('wrap') == 1
    v311c._check_dictionary_guard(17, 'world')
    assert v39.STATS == {}
    assert v311c.STATS['dictionary_checks'] == 1
    assert not guard.getvalue()


@pytest.mark.parametrize('phase', ['world', 'received', 'probe'])
def test_unknown_collision_keeps_cost_and_counter_then_stops_with_names(guard, phase):
    # 状態に残らない一時的な候補も、呼出しを控えれば名前を記録できる。
    assert v39.dict_order('abc') == v39.dict_order('acb') == 296
    assert v39.STATS['not_in_dictionary'] == 2
    with pytest.raises(v311c.NotInDictionary) as error:
        v311c._check_dictionary_guard(17, phase)
    expected = {'kind': 'v311c_not_in_dictionary', 'run': 1, 'agent': 6,
                'trial': 17, 'phase': phase, 'count': 2, 'names': ['abc', 'acb']}
    assert json.loads(guard.getvalue()) == expected
    assert error.value.diagnostic == expected
    assert v39.STATS['not_in_dictionary'] == 2


def test_probe_stops_before_module_restore_erases_counter(guard):
    def predict(*args):
        v39.dict_order('abc')
        return SimpleNamespace(prediction=None), None

    v311c.CFG.update(inner_predict=predict)
    with pytest.raises(v311c.NotInDictionary, match='abc'):
        v311c.probe(None, [{'scene': SimpleNamespace(relations=())}], None)
    assert json.loads(guard.getvalue())['phase'] == 'probe'
    assert 'not_in_dictionary' not in v39.STATS  # 旧い試験と同じ復元。


def test_agent_error_contains_diagnostic_and_releases_serial_lock(monkeypatch, guard):
    import v3_run
    messages = []
    class Lock:
        releases = 0
        def acquire(self): pass
        def release(self): self.releases += 1
    lock = Lock()
    def worker(task):
        v39.dict_order('abc')
        v311c._check_dictionary_guard(17, 'received')
    monkeypatch.setattr(v3_run, 'worker', worker)
    v311c._agent_main(SimpleNamespace(send=messages.append),
                     {'v311c': {'serial_lock': lock}})
    assert lock.releases == 1
    assert messages[0]['type'] == 'error'
    assert messages[0]['diagnostic'] == json.loads(guard.getvalue())


@pytest.mark.parametrize('phase', ['world', 'received', 'probe'])
def test_coordinator_keeps_diagnostic_in_each_phase(monkeypatch, tmp_path, phase):
    diagnostic = {'kind': 'v311c_not_in_dictionary', 'agent': 0, 'trial': 0,
                  'run': 1, 'names': ['abc'], 'count': 1, 'phase': phase}

    def agent(conn, task):
        i = task['v311c']['agent']
        def fail(where):
            if i == 0 and phase == where:
                conn.send({'type': 'error', 'diagnostic': diagnostic})
                return True
            return False
        if fail('world'): return
        conn.send({'type': 'trial', 'bundle': None, 'research': None, 'tags': []})
        conn.recv()
        if fail('received'): return
        conn.send({'type': 'received', 'records': [], 'tags': []})
        conn.recv()
        if fail('probe'): return
        conn.send({'type': 'probe', 'answers': []})
        conn.recv()
        conn.send({'type': 'done', 'rec': {}})

    monkeypatch.setattr(v311c, '_agent_main', agent)
    monkeypatch.setattr(v311c, 'probe_items', lambda *args: [])
    task = {'cfg': {'trial_count': 1, 'seed_file': 'unused', 'fixed': {}},
            'v311c': {'run': 1, 'agent': 0}}
    tasks = [dict(task, v311c=dict(task['v311c'], agent=i)) for i in range(2)]
    procs = []
    summary = v311c._coordinate(tasks, tmp_path / 'comm.jsonl', 1, procs)
    assert summary['errors'][0]['msg']['diagnostic'] == diagnostic
    assert all(not p.is_alive() for p in procs)
    saved = [json.loads(line) for line in (tmp_path / 'comm.jsonl').read_text().splitlines()]
    assert saved[-1]['errors'][0]['msg']['diagnostic'] == diagnostic
