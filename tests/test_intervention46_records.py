"""記録が本人の計算へ戻らないことと、比較の除外の狭さを検査する。"""
from dataclasses import dataclass
from contextlib import contextmanager
import gzip
import json
from pathlib import Path
from random import Random
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import abm.loop as loop
from abm.domains import AgentOutput, Abstain, Relation, RelationGraph
import attnsme
from attnsme_features import Observations
from attnstage2_questions import Questions
import attnstage2_runtime as stage2
from intervention46_records import Recorder, observation_data
from intervention46_record_gate import compare_files
import smereplay
import v39


@contextmanager
def retained_directory():
    """診断の作業資料はテストの終了時にも消さない。"""
    path = ROOT.parent / "instruction5/unit_checks" / str(time.time_ns())
    path.mkdir(parents=True, exist_ok=False)
    yield str(path)


@dataclass(frozen=True)
class Row:
    relation: object
    slot_index: int = 0
    registered_at: int = 3


@dataclass(frozen=True)
class Definition:
    name: str
    constituents: tuple


class RecordTests(unittest.TestCase):
    def test_pre_is_saved_before_prediction_and_does_not_mutate_observer_or_rng(self):
        with retained_directory() as directory:
            obs = Observations()
            obs.structure([{"relation_id": "r", "predicate": "F", "arguments": ["x"]}], {"x"})
            frozen = observation_data(obs)
            questions = Questions()
            rng = Random(7)
            rng_before = rng.getstate()
            state, ai, config = {"state": 1}, {"visible": 2}, {"lambda": .1}
            output, pending = AgentOutput(prediction=Abstain(reason="no_definition"), trace={}), {"pending": 1}
            path = Path(directory) / "records.gz"

            def native_predict(given_ai, given_state, given_config, given_rng):
                self.assertIs(given_ai, ai); self.assertIs(given_state, state)
                self.assertIs(given_config, config); self.assertIs(given_rng, rng)
                questions.present(True)
                # 実際の予測側が観測を進めても、先に保存した控えは変わらない。
                obs.names.add("seen_during_prediction")
                stage2.ST["pre"] = (ai, state, config, rng.getstate(), obs, {"new_zero": 0.}, True)
                return output, pending

            with patch.object(loop, "predict", native_predict), patch.dict(attnsme.ST,
                 {"agent": "agent", "trial": 0, "individual": {"observations": obs, "a": {}}}, clear=True), \
                 patch.dict(stage2.ST, {}, clear=True):
                recorder = Recorder(path)
                recorder.install()
                try:
                    returned = loop.predict(ai, state, config, rng)
                    self.assertIs(returned[0], output); self.assertIs(returned[1], pending)
                    self.assertEqual(rng.getstate(), rng_before)
                    self.assertEqual(questions.door, 1)
                    self.assertEqual(questions.door_names, set())
                    self.assertIs(questions.pending, stage2.ST.get("question", questions.pending))
                finally:
                    recorder.close()
            with gzip.open(path, "rt") as stream:
                saved = [json.loads(line) for line in stream]
            self.assertEqual(saved[0]["observations"], frozen)
            self.assertEqual(smereplay.decode(saved[0]["rng"]), rng_before)
            self.assertEqual(smereplay.decode(saved[0]["questions"]["door_names"]), frozenset())
            self.assertEqual(smereplay.decode(saved[1]["attention"]), {"new_zero": 0.})

    def test_birth_uses_exact_material_objects_times_and_slot_mapping(self):
        with retained_directory() as directory:
            source = Relation("s", "F", ("x",))
            target_relation = Relation("t", "F", ("y",))
            base = RelationGraph("base", (), (source,))
            target = RelationGraph("target", (), (target_relation,))
            row = Row(source)
            definition = Definition("R", (row,))
            result = object()
            calls = []
            @dataclass
            class Alignment:
                relation_mapping: dict
            def native_initial(*arguments):
                calls.append(arguments)
                return result
            def native_m1(state, b, t, alignment, trial, **kwargs):
                return v39._init_rec(definition, row, state, b, t, trial, 2, {})
            path = Path(directory) / "records.gz"
            @dataclass
            class Input:
                target_graph_partial: object
            with patch.object(loop, "m1", native_m1), patch.object(v39, "_init_rec", native_initial), \
                 patch.dict(attnsme.ST, {"agent": "agent"}, clear=True), \
                 patch.dict(stage2.ST, {"current_pre": (Input(target),)}, clear=True):
                recorder = Recorder(path); recorder.install()
                try:
                    actual = loop.m1({}, base, target, Alignment({"s": "t"}), 3, base_written_at=1)
                    self.assertIs(actual, result)
                    self.assertIs(calls[0][3], base); self.assertIs(calls[0][4], target)
                finally:
                    recorder.close()
            with gzip.open(path, "rt") as stream: saved = json.loads(next(stream))
            self.assertEqual((saved["first_experienced_trial"], saved["second_experienced_trial"]), (1, 3))
            self.assertEqual((saved["source_relation_id"], saved["source_material_name"], saved["slot_index"]), ("s", "F", 0))
            self.assertEqual(saved["target_relation_id"], "t")

    def test_byte_gate_only_ignores_declared_time_values(self):
        with retained_directory() as directory:
            left, right = (Path(directory) / name for name in ("a.jsonl", "b.jsonl"))
            left.write_bytes(b'{"seconds": 1.0, "answer": "F", "n": 2}\n')
            right.write_bytes(b'{"seconds": 9.0, "answer": "F", "n": 2}\n')
            self.assertTrue(compare_files(left, right)["match"])
            right.write_bytes(b'{"seconds": 9.0, "answer": "F", "n": 3}\n')
            self.assertFalse(compare_files(left, right)["match"])
            right.write_bytes(b'{"seconds": 9.0,"answer": "F", "n": 2}\n')
            self.assertFalse(compare_files(left, right)["match"])


if __name__ == "__main__":
    unittest.main()
