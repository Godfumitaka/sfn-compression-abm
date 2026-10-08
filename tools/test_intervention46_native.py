"""指示3の材料の境界：全定義のUシールだけ・不足を補わない。"""
from dataclasses import fields, replace
from random import Random
import pytest

from abm.definition import Constituent, NamedDefinition
from abm.domains import AgentState, Relation
from attnsme_features import Observations
from attnstage2_questions import Snapshot
from intervention46_native import BirthIndex, Frame, restore_observations
from intervention46_records import observation_data
import v39


@pytest.fixture
def frame_and_index():
    rows = tuple(Constituent(i, 1, Relation(name, name + "_old", ("entity",)),
                            None, alive=(i == 1))
                 for i, name in enumerate(("u_sig", "f_sig", "h_sig", "u_other")))
    definitions = {name: NamedDefinition(name, rows, len(rows), 1) for name in ("one", "two")}
    state = replace(v39.ensure(AgentState()), definitions=definitions,
                    slot_history={(name, 2): {"h_seen": 1} for name in definitions})
    frame = Frame("agent", 3, state, None, None, Random(0).getstate(), Observations(),
                  {}, {}, Snapshot(0, 0, frozenset(), frozenset(), False), False, None, None)
    index = BirthIndex()
    for name in definitions:
        index.seats[(frame.agent, name, 1, 0, 1)] = dict(predicate=name + "_birth",
            source_relation_id="u_sig", target_relation_id="seen_sig", birth_trial=1,
            first_experienced_trial=0, second_experienced_trial=1)
    return frame, index


def test_all_definitions_only_u_seals(frame_and_index):
    frame, index = frame_and_index
    before = frame.digest()
    result, changes = index.restore_u_seals(frame, {"u_sig", "f_sig", "h_sig"})
    assert len(changes) == 2
    for name, definition in result.definitions.items():
        assert definition.constituents[0].alive
        assert definition.constituents[0].relation.predicate == name + "_birth"
        assert definition.constituents[1:] == frame.state.definitions[name].constituents[1:]
    for field in fields(result):
        if field.name != "definitions":
            assert getattr(result, field.name) is getattr(frame.state, field.name)
    assert frame.digest() == before


def test_missing_record_is_not_filled(frame_and_index):
    frame, _ = frame_and_index
    with pytest.raises(ValueError, match="誕生材料名が無い"):
        BirthIndex().restore_u_seals(frame, {"u_sig"})


def test_birth_at_current_trial_is_not_past(frame_and_index):
    frame, index = frame_and_index
    with pytest.raises(ValueError, match="誕生材料名が無い"):
        index.restore_u_seals(replace(frame, trial=1), {"u_sig"})


def test_other_agent_material_is_not_used(frame_and_index):
    frame, index = frame_and_index
    with pytest.raises(ValueError, match="誕生材料名が無い"):
        index.restore_u_seals(replace(frame, agent="someone_else"), {"u_sig"})


def test_missing_observation_field_is_not_filled():
    raw = observation_data(Observations())
    missing = {key: value for key, value in raw.items() if key != "parents"}
    with pytest.raises(ValueError, match="全欄"):
        restore_observations(missing)
