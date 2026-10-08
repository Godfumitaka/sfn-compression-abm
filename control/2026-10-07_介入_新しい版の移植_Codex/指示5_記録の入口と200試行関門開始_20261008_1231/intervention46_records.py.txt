"""指示5の研究者側の記録。本人の入力・計算・記憶には値を戻さない。"""
from dataclasses import fields
import gzip
import json
from pathlib import Path

import smereplay

OBSERVATION_FIELDS = (
    "entities", "arguments", "parents", "shapes", "table", "names", "events", "last_trial",
)


def observation_data(observations):
    """実際の予測前の実体を、その時点で順序を保って値へ写す。"""
    return {name: smereplay.encode(getattr(observations, name)) for name in OBSERVATION_FIELDS}


def question_data(snapshot):
    return {field.name: smereplay.encode(getattr(snapshot, field.name)) for field in fields(snapshot)}


class Recorder:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = gzip.open(path, "xt", encoding="utf-8")
        self.prediction = None
        self.materials = None
        self.pre_count = self.birth_seats = 0
        self.restores = []

    def write(self, row):
        self.stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def install(self):
        import abm.loop as loop
        import attnsme
        import attnstage2_runtime as stage2
        from attnstage2_questions import Questions
        import v39

        original_predict = loop.predict
        original_present = Questions.present
        original_initial = v39._init_rec
        original_m1 = loop.m1
        self.restores = [(loop, "predict", original_predict),
                         (Questions, "present", original_present),
                         (v39, "_init_rec", original_initial), (loop, "m1", original_m1)]

        def predict(ai, state, config, rng):
            self.prediction = (ai, state, config, rng.getstate())
            result = original_predict(ai, state, config, rng)
            # 選択がaへ既存の0の鍵を作ることも含め、実際の控えをそのまま保存。
            pre = stage2.ST["pre"]
            self.write({"kind": "prediction_context", "agent_id": attnsme.ST["agent"],
                        "trial": attnsme.ST["trial"], "attention": smereplay.encode(pre[5]),
                        "door_task": pre[6], "output": smereplay.encode(result[0]),
                        "pending": smereplay.encode(result[1])})
            return result

        def present(questions, door_task):
            snapshot = original_present(questions, door_task)
            if self.prediction is None:
                raise RuntimeError("予測前の実体が無いので記録を補わない")
            ai, state, config, rng_state = self.prediction
            self.write({"kind": "pre", "agent_id": attnsme.ST["agent"],
                        "trial": attnsme.ST["trial"], "state": smereplay.encode(state),
                        "input": smereplay.encode(ai), "config": smereplay.encode(config),
                        "rng": smereplay.encode(rng_state),
                        "observations": observation_data(attnsme.ST["individual"]["observations"]),
                        "attention": smereplay.encode(attnsme.ST["individual"]["a"]),
                        "questions": question_data(snapshot)})
            self.pre_count += 1
            return snapshot

        def m1(state, base, target, alignment, trial, **kwargs):
            previous = self.materials
            self.materials = (base, target, dict(alignment.relation_mapping),
                              kwargs["base_written_at"], trial)
            try:
                return original_m1(state, base, target, alignment, trial, **kwargs)
            finally:
                self.materials = previous

        def initialize(definition, row, state, base, target, trial, base_age, config):
            if self.materials is None:
                raise RuntimeError("実際の二材料と経験時刻が無いので記録を補わない")
            actual_base, actual_target, mapping, first_trial, second_trial = self.materials
            if actual_base is not base or actual_target is not target or second_trial != trial:
                raise RuntimeError("誕生関数の実際の二材料が一致しない")
            first_by_id = {relation.relation_id: relation for relation in base.relations}
            second_by_id = {relation.relation_id: relation for relation in target.relations}
            source_id = row.relation.relation_id
            source = first_by_id[source_id]
            target_id = mapping[source_id]
            second = second_by_id[target_id]
            self.write({"kind": "birth_seat", "agent_id": attnsme.ST["agent"],
                        "trial": trial, "definition_name": definition.name,
                        "definition": smereplay.encode(definition), "row": smereplay.encode(row),
                        "first_material": smereplay.encode(base),
                        "second_material": smereplay.encode(target),
                        "second_visible": smereplay.encode(stage2.ST["current_pre"][0].target_graph_partial),
                        "first_experienced_trial": first_trial, "second_experienced_trial": second_trial,
                        "base_age": base_age, "slot_index": row.slot_index,
                        "source_relation_id": source_id, "source_material_name": source.predicate,
                        "target_relation_id": target_id, "target_material_name": second.predicate,
                        "registered_at": row.registered_at})
            self.birth_seats += 1
            return original_initial(definition, row, state, base, target, trial, base_age, config)

        loop.predict = predict
        Questions.present = present
        loop.m1 = m1
        v39._init_rec = initialize

    def close(self):
        for owner, name, original in reversed(self.restores):
            setattr(owner, name, original)
        self.stream.close()
