"""委任書46の新版診断の接続。正式な介入の走行はこの部品では始めない。

予測前の実記録を型へ戻す。材料名は実際の誕生の席の対応からだけ読む。
較正・世界の正解・後の観察から欠けた欄を補う入口は持たない。
"""
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, fields, replace
import gzip
import hashlib
import json
from pathlib import Path
from random import Random

import smereplay
from intervention46_records import OBSERVATION_FIELDS, observation_data, question_data


def fingerprint(value):
    return hashlib.sha256(json.dumps(smereplay.encode(value), ensure_ascii=False,
                                   separators=(",", ":")).encode()).hexdigest()


def read_records(path):
    """保存した順のまま読む。順の修復や不足分の生成はしない。"""
    with gzip.open(Path(path), "rt", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            if row.get("kind") not in ("pre", "prediction_context", "birth_seat"):
                raise ValueError((number, "診断の記録の種類が不明"))
            yield row


def restore_observations(raw):
    from attnsme_features import Observations
    if tuple(raw) != OBSERVATION_FIELDS:
        raise ValueError("予測前のObservationsの全欄が同じ順で必要")
    result = Observations()
    for name in OBSERVATION_FIELDS:
        setattr(result, name, smereplay.decode(raw[name]))
    # 記録の値を変えず、元の二つの容器の型も戻す。
    result.parents = defaultdict(list, result.parents)
    result.shapes = defaultdict(set, result.shapes)
    if observation_data(result) != raw:
        raise ValueError("Observationsの復元が元の記録と一致しない")
    return result


def restore_questions(raw):
    from attnstage2_questions import Snapshot
    if tuple(raw) != tuple(field.name for field in fields(Snapshot)):
        raise ValueError("問いのSnapshotの全欄が同じ順で必要")
    result = Snapshot(**{key: smereplay.decode(value) for key, value in raw.items()})
    if question_data(result) != raw:
        raise ValueError("問いのSnapshotの復元が元の記録と一致しない")
    return result


@dataclass(frozen=True)
class Frame:
    agent: str
    trial: int
    state: object
    agent_input: object
    config: object
    rng_state: tuple
    observations: object
    attention: dict
    prediction_attention: dict
    questions: object
    door_task: bool
    recorded_output: object
    recorded_pending: object

    @classmethod
    def restore(cls, pre, prediction):
        if pre["kind"] != "pre" or prediction["kind"] != "prediction_context":
            raise ValueError("同じ試行の予測前と予測時の実記録が必要")
        agent, trial = pre["agent_id"], pre["trial"]
        if (prediction["agent_id"], prediction["trial"]) != (agent, trial):
            raise ValueError("予測前と予測時の個体又は試行が違う")
        observations = restore_observations(pre["observations"])
        questions = restore_questions(pre["questions"])
        if observations.last_trial != trial - 1 or questions.door + questions.other != trial + 1:
            raise ValueError("観察又は問いの実経験の時刻が違う")
        if type(prediction["door_task"]) is not bool or prediction["door_task"] != questions.current_door:
            raise ValueError("実際の問いの指示が一致しない")
        decoded = {name: smereplay.decode(pre[name]) for name in ("state", "input", "config", "rng", "attention")}
        for name, value in decoded.items():
            if smereplay.encode(value) != pre[name]:
                raise ValueError((trial, name, "型への復元が実記録と一致しない"))
        rng = Random()
        rng.setstate(decoded["rng"])
        if rng.getstate() != decoded["rng"]:
            raise ValueError("予測前の乱数の控えが不正")
        return cls(agent, trial, decoded["state"], decoded["input"], decoded["config"],
                   decoded["rng"], observations, decoded["attention"],
                   smereplay.decode(prediction["attention"]), questions, prediction["door_task"],
                   smereplay.decode(prediction["output"]), smereplay.decode(prediction["pending"]))

    def digest(self):
        values = (self.state, self.agent_input, self.config, self.rng_state, self.attention,
                  self.prediction_attention, self.recorded_output, self.recorded_pending)
        raw = (smereplay.encode(values), observation_data(self.observations), question_data(self.questions))
        return hashlib.sha256(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def session(self, flags, *, state=None):
        """同じ版のC*・注意・答えの読み手を使う。問いを数え直さない。"""
        import attncstar
        import attnsme
        import cstar_runtime as C
        import smeshared as S
        from attnstage2_distribution import Readout
        if not flags["attn_allin"] or flags["stage2"] != "on":
            raise ValueError("この接続は全部入りの第二段用。D＋注意は別の版の確認待ち")
        if flags["stage2_reuse"] != "off":
            raise ValueError("この診断の接続では承認済みの使い回しoffを固定する")
        if S.CTX.get("trial") != self.trial or not C.CFG or attnsme.ST.get("active"):
            raise ValueError("同じ旗で導入した診断用の予測前の文脈が必要")
        return attncstar.Session(self.agent_input, self.state if state is None else state,
            self.config, self.rng_state, deepcopy(self.observations), dict(self.prediction_attention),
            mode=flags["attn_sme"], position=flags["attn_position"], door_task=self.door_task,
            epsilon=flags["logp_eps"], readout_policy=Readout(),
            feature_policy=attncstar.Features(flags["logp_eps"]), reuse_structure=False)

    def prediction(self, flags, *, state=None, forced_definition=None):
        """予測だけを読み直す。選びと研究者指定の席を同じ候補から読む。"""
        import attnsme
        import v39
        with self.isolated():
            state = self.state if state is None else state
            session = self.session(flags, state=state)
            if forced_definition is None:
                selected = session.choose(session.candidates, self.prediction_attention)
            else:
                selected = next((candidate for candidate in session.candidates
                                 if candidate.name == forced_definition), None)
                if selected is None:
                    raise ValueError((forced_definition, "研究者指定の定義を同じ候補の中で読めない"))
            if selected is None:
                clone = Random()
                clone.setstate(self.rng_state)
                with session.context(state):
                    output, _ = v39.predict(self.agent_input, state, self.config, clone)
                value = attnsme.prediction_data(output)
            else:
                value = {key: selected.payload["answer"][key] for key in
                         ("prediction_kind", "predicted_edge", "abstain_reason", "R_used")}
            return dict(prediction=value, selected=None if selected is None else selected.name,
                        candidate_names=[candidate.name for candidate in session.candidates])

    @contextmanager
    def isolated(self):
        """診断用に導入済みの版で、照合の控えと元の実記録を保存する。"""
        import attnsme
        import attnstage2_runtime as stage2
        import cstar_runtime as C
        import smeshared as S
        import v31
        import v39
        from attnstage2_sme import isolated
        before = self.digest()
        # 既存の隔離窓口はC*のエンジン・乱数・控えもsnapshot/restoreする。
        # CFGと注意・第二段の外側の容器も、この入口の変更を残さない。
        extra = [(value, dict(value)) for value in
                 (v31.CFG, v39.CFG, C.CFG, attnsme.ST, stage2.ST)]
        try:
            with isolated():
                S.CTX["trial"] = self.trial
                attnsme.ST["active"] = False
                v39.CTX["config"] = self.config
                yield
        finally:
            for value, saved in extra:
                value.clear()
                value.update(saved)
            if self.digest() != before:
                raise RuntimeError("診断が元の記憶・観測・注意・問い・乱数を変えた")


class BirthIndex:
    """個体と席の出生を同定し、材料の実名を一意に控える。"""
    def __init__(self):
        self.seats = {}

    def add(self, record):
        if record["kind"] != "birth_seat":
            raise ValueError("実際の誕生の席の記録だけを受け取る")
        definition, row, first, second = (smereplay.decode(record[key]) for key in
                                         ("definition", "row", "first_material", "second_material"))
        left = {r.relation_id: r for r in first.relations}
        right = {r.relation_id: r for r in second.relations}
        source = left[record["source_relation_id"]]
        target = right[record["target_relation_id"]]
        key = (record["agent_id"], definition.name, definition.registered_at,
               row.slot_index, row.registered_at)
        if (definition.name != record["definition_name"] or row.slot_index != record["slot_index"]
                or row.registered_at != record["registered_at"] or row not in definition.constituents
                or row.relation.relation_id != source.relation_id
                or source.predicate != record["source_material_name"]
                or target.predicate != record["target_material_name"]
                or row.relation.predicate != source.predicate):
            raise ValueError((key, "材料の実名と誕生の席の対応が一致しない"))
        first_t, second_t, trial = (record[key] for key in
                                   ("first_experienced_trial", "second_experienced_trial", "trial"))
        if not first_t < second_t == trial or record["base_age"] != trial - first_t:
            raise ValueError((key, "誕生の二材料の実経験の時刻が不正"))
        if key in self.seats:
            raise ValueError((key, "同じ席の誕生記録が二件あるので補わない"))
        self.seats[key] = dict(predicate=source.predicate, source_relation_id=source.relation_id,
            target_relation_id=target.relation_id, birth_trial=trial,
            first_experienced_trial=first_t, second_experienced_trial=second_t)

    def restore_u_seals(self, frame, seal_ids):
        """全定義のUシールだけをFへ。F/H・履歴・成績は元のまま。"""
        import v39
        before = frame.digest()
        definitions = dict(frame.state.definitions)
        changed = []
        for definition in frame.state.definitions.values():
            rows = []
            for row in definition.constituents:
                if row.relation.relation_id in seal_ids and v39.seat_state(definition, row, frame.state.slot_history) == "U":
                    key = (frame.agent, definition.name, definition.registered_at, row.slot_index, row.registered_at)
                    if key not in self.seats or self.seats[key]["birth_trial"] >= frame.trial:
                        raise ValueError((key, "試行前の誕生材料名が無いので補わない"))
                    entry = self.seats[key]
                    if entry["source_relation_id"] != row.relation.relation_id:
                        raise ValueError((key, "誕生の材料と現在の席が違う"))
                    row = replace(row, alive=True, relation=replace(row.relation, predicate=entry["predicate"]))
                    changed.append(dict(seat=key, **entry))
                rows.append(row)
            if tuple(rows) != definition.constituents:
                definitions[definition.name] = replace(definition, constituents=tuple(rows))
        result = replace(frame.state, definitions=definitions)
        if frame.digest() != before:
            raise RuntimeError("3bの材料の取り出しが元の実記録を変えた")
        return result, changed
