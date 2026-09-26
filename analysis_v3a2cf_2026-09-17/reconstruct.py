"""既存 v2a 台帳の解析用部分状態を、引数順序を保って再構成する。

模型の走行・更新・予測は呼ばない。AgentState の definitions / p_hat /
slot_history だけを復元するので、返り値を predict に渡してはならない。
スナップショットはシーケンスをソートしているため、登録イベントの順序情報を
必ず結合する。元の台帳・模型コードには書き込まない。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Iterator

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from abm.definition import Constituent, FrozenPrice, FrequencyTable, NamedDefinition
from abm.domains import AgentState, Relation
from abm.loop import _apply
from abm.seed import Seed, load_seed
from abm.world import WorldTrial, generate_trial
from api_current import seed_for_header, history_value


class ReconstructionError(ValueError):
    """台帳との一致を保証できないときは近似せず報告する。"""


@dataclass(frozen=True)
class ReconstructedTrial:
    header: dict[str, Any]
    row: dict[str, Any]
    before_state: AgentState
    after_state: AgentState
    world_trial: WorldTrial | None


def verify_world_trial(header: dict[str, Any], row: dict[str, Any], seed: Seed) -> WorldTrial:
    """同じ seed / 試行番号の入力だけを復元し、保存された正情報と照合する。"""
    trial = generate_trial(header["run_seed"], row["prediction_order"],
                           header["agent_ids"], seed=seed,
                           holdout_include_second_order=header.get("arm_holdout_second_order",False))
    checks = {
        "instance_id": (row["instance_id"], trial.G_star.graph_id),
        "scene_G_star_ref": (row["scene_G_star_ref"], trial.G_star.graph_id),
        "observable_mask_edges": (row["observable_mask_edges"],
                                  [r.relation_id for r in trial.target_graph_partial.relations]),
        "held_out_content": (row["held_out_content"], trial.held_out_edge.to_dict()),
    }
    if row.get("f_fired"):
        checks["feedback_content"] = (row.get("feedback_content"), trial.held_out_edge.to_dict())
    for field, (actual, expected) in checks.items():
        if actual != expected:
            raise ReconstructionError(f"trial={trial.trial}: {field} mismatch: {actual!r} != {expected!r}")
    return trial


class LedgerReconstructor:
    """一エージェント台帳を先頭から消費する。部分スナップショットは非対応。"""
    _fields = ("definitions", "p_hat", "slot_history")

    def __init__(self, header: dict[str, Any], *, seed: Seed | None = None):
        self.header = dict(header)
        self.seed = seed or seed_for_header(header)
        if header["seed_file_sha256"] != self.seed.file_sha256:
            raise ReconstructionError("ledger header と現行種の file_sha256 が一致しない")
        if len(header["agent_ids"]) != 1:
            raise ReconstructionError("この解析 API は一エージェント台帳専用")
        self.raw: dict[str, Any] = {}
        self.state = AgentState()
        self.last_trial = -1
        self.last_snapshot_hash: str | None = None
        self.definition_order: list[str] = []
        self.registration_rows: dict[str, list[dict[str, Any]]] = {}
        self.statistics = {"rows": 0, "world_rows_verified": 0,
                           "ordered_argument_repairs": 0, "registration_events": 0}

    def consume(self, row: dict[str, Any], *, verify_world: bool = True) -> ReconstructedTrial:
        t = row["prediction_order"]
        if t != self.last_trial + 1:
            raise ReconstructionError(f"非連続の試行番号: {self.last_trial} -> {t}")
        if row["agent_id"] != self.header["agent_ids"][0]:
            raise ReconstructionError("agent_id mismatch")
        if row["run_id"] != self.header["world_hash"]:
            raise ReconstructionError("run_id / world_hash mismatch")
        before = self.state
        for event in row.get("reg_del_events") or []:
            if event.get("kind") != "registration":
                continue
            name = event["R"]
            if name not in self.registration_rows:
                self.definition_order.append(name)
            self.registration_rows[name] = event["constituents"]
            self.statistics["registration_events"] += 1

        snap = row.get("state_snapshot")
        if not snap or snap.get("kind") not in {"full", "delta"}:
            raise ReconstructionError(f"trial={t}: full / delta snapshot が必要")
        if snap["kind"] == "full":
            self.raw = {key: snap["value"][key] for key in self._fields}
        else:
            if not self.raw or snap.get("base_hash") != self.last_snapshot_hash:
                raise ReconstructionError(f"trial={t}: snapshot base_hash mismatch")
            for key in self._fields:
                if key in snap["changes"]:
                    self.raw[key] = _apply(self.raw.get(key), snap["changes"][key])
        self.state = self._materialize(t)
        self.last_trial = t
        self.last_snapshot_hash = row["agent_state_snapshot_hash"]
        trial = verify_world_trial(self.header, row, self.seed) if verify_world else None
        self.statistics["rows"] += 1
        self.statistics["world_rows_verified"] += int(verify_world)
        return ReconstructedTrial(self.header, row, before, self.state, trial)

    def _materialize(self, t: int) -> AgentState:
        raw_defs = self.raw["definitions"]
        if set(raw_defs) != set(self.definition_order):
            raise ReconstructionError(f"trial={t}: definition の登録メタデータが不足")
        definitions = {}
        for name in self.definition_order:
            raw_def = raw_defs[name]
            by_key = {(r["slot_index"], r["registered_at"]): r for r in raw_def["constituents"]}
            events = self.registration_rows[name]
            if len(by_key) != len(raw_def["constituents"]):
                raise ReconstructionError(f"trial={t}: constituent key が重複")
            if set(by_key) != {(r["slot_index"], r["registered_at"]) for r in events}:
                raise ReconstructionError(f"trial={t}: registration / snapshot constituent key mismatch")
            rows = []
            for event in events:
                raw = by_key[(event["slot_index"], event["registered_at"])]
                relation = raw["relation"]
                if relation["predicate"] != event["predicate"]:
                    raise ReconstructionError(f"trial={t}: constituent predicate mismatch")
                if sorted(relation["arguments"]) != sorted(event["arguments"]):
                    raise ReconstructionError(f"trial={t}: constituent argument multiset mismatch")
                self.statistics["ordered_argument_repairs"] += int(relation["arguments"] != event["arguments"])
                rel = Relation(relation["relation_id"], event["predicate"],
                               tuple(event["arguments"]), relation.get("attributes", {}))
                rows.append(Constituent(event["slot_index"], event["registered_at"], rel,
                                        FrozenPrice(**raw["frozen_price"]), raw["alive"]))
            definitions[name] = NamedDefinition(raw_def["name"], tuple(rows), raw_def["m_alloc"],
                                                raw_def["registered_at"], raw_def["assimilation_count"])
        freq = self.raw["p_hat"]
        p_hat = FrequencyTable(dict(freq["counts"]), freq["total"], freq["lambda_mix"],
                               frozenset(freq["alive_vocab"]))
        history = {}
        for key, value in self.raw["slot_history"].items():
            parsed = ast.literal_eval(key)
            if not isinstance(parsed, tuple) or len(parsed) != 2:
                raise ReconstructionError(f"invalid slot_history key: {key!r}")
            history[parsed] = history_value(value)
        return AgentState(definitions=definitions, p_hat=p_hat, slot_history=history)


def iter_ledger(path: str | Path, *, verify_world: bool = True,
                seed: Seed | None = None) -> Iterator[ReconstructedTrial]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        header = json.loads(next(stream))
        if header.get("record_type") != "run_header":
            raise ReconstructionError("先頭行が run_header ではない")
        reader = LedgerReconstructor(header, seed=seed)
        for line in stream:
            row = json.loads(line)
            if row.get("record_type") != "trial":
                raise ReconstructionError("試行行でないレコードがある")
            yield reader.consume(row, verify_world=verify_world)
