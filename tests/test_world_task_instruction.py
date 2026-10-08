"""指示6の一つのboolと、回答後の研究者記録の境界を検査する。"""
from pathlib import Path
from types import SimpleNamespace
from io import StringIO
import sys
import pytest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'), str(Path(__file__).resolve().parents[1])]
import abm.loop as loop
from abm.domains import AgentInput, RelationGraph
import attnsme
import shopworld
import verbworld
import smeshared


class OneField:
    def __init__(self, key, value):
        self.key, self.value, self.reads = key, value, []
    def __getitem__(self, key):
        self.reads.append(key)
        assert key == self.key, '指示以外の研究者欄を読んだ'
        return self.value


@pytest.mark.parametrize('module,key', [(shopworld,'held_out_is_door'),(verbworld,'held_out_is_past')])
@pytest.mark.parametrize('value',[False,True])
def test_world_provider_returns_only_existing_bool(monkeypatch,module,key,value):
    info = OneField(key,value)
    monkeypatch.setattr(module,'INFO',{'scene':info})
    tr = SimpleNamespace(G_star=SimpleNamespace(graph_id='scene'))
    assert module.task_instruction(tr) is value
    assert info.reads == [key]


@pytest.mark.parametrize('value',[False,True])
def test_agent_entry_accepts_bool_without_trial_oracle_access(monkeypatch,tmp_path,value):
    for key in ('_agent_input','predict','_ledger_record'):
        monkeypatch.setattr(loop,key,getattr(loop,key))
    monkeypatch.setattr(attnsme,'ST',{})
    monkeypatch.setattr(smeshared,'_definition_choice',smeshared._definition_choice)
    monkeypatch.setattr(smeshared,'_text_gzip',lambda _:StringIO())
    ai = AgentInput(RelationGraph('visible',(),()),RelationGraph('visible',(),()))
    monkeypatch.setattr(loop,'_agent_input',lambda trial,before:ai)
    class Trial:
        trial = 0
        @property
        def G_star(self):raise AssertionError('予測側が完全グラフを読んだ')
        @property
        def held_out_edge(self):raise AssertionError('予測側が真値を読んだ')
    def research(*args):raise AssertionError('予測前に研究者記録を読んだ')
    attnsme.install(tmp_path/'attention',mode='global',position='k2',eta=.1,
                    task_instruction=lambda _:value,research_record=research)
    assert loop._agent_input(Trial(),None) is ai
    assert attnsme.ST['door_task'] is value
    assert set(attnsme.ST['individual']) == {'observations','a'}


def test_entry_rejects_non_bool_instead_of_coercing_researcher_payload(monkeypatch,tmp_path):
    for key in ('_agent_input','predict','_ledger_record'):
        monkeypatch.setattr(loop,key,getattr(loop,key))
    monkeypatch.setattr(attnsme,'ST',{})
    monkeypatch.setattr(smeshared,'_definition_choice',smeshared._definition_choice)
    monkeypatch.setattr(smeshared,'_text_gzip',lambda _:StringIO())
    monkeypatch.setattr(loop,'_agent_input',lambda *args:object())
    attnsme.install(tmp_path/'attention',mode='global',position='k2',eta=.1,
                    task_instruction=lambda _:{'truth':'REG'},research_record=lambda *args:{})
    with pytest.raises(TypeError,match='bool一つ'):
        loop._agent_input(SimpleNamespace(trial=0),None)
