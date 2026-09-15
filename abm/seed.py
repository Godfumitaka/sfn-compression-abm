"""SPEC B0+B2 §B.2 の種読み込みと起動時検算。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from math import log2
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "U-011 seed v2a.json"


class SeedValidationError(ValueError):
    """種のハッシュまたは内部整合が仕様と異なる。"""


@dataclass(frozen=True, slots=True)
class Seed:
    """検算済みの読み取り専用種。"""

    data: Mapping[str, Any]
    sha256: str
    file_sha256: str


def canonical_seed_bytes(data: Mapping[str, Any]) -> bytes:
    """``sha256`` 欄を除いた種の正準 UTF-8 表現を返す。"""

    payload = dict(data)
    payload.pop("sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seed_hash(data: Mapping[str, Any]) -> str:
    return sha256(canonical_seed_bytes(data)).hexdigest()


def load_seed(path: str | Path = DEFAULT_SEED_PATH) -> Seed:
    """種を読み、ハッシュと内部整合を検査してから固定する。"""

    raw_bytes = Path(path).read_bytes()
    raw = json.loads(raw_bytes)
    if not isinstance(raw, dict):
        raise SeedValidationError("種のルートは object である必要がある")
    expected_hash = raw.get("sha256")
    actual_hash = seed_hash(raw)
    if expected_hash is not None and expected_hash != actual_hash:
        raise SeedValidationError(f"種の sha256 が不一致: expected={expected_hash}, actual={actual_hash}")
    validate_seed(raw)
    return Seed(data=_freeze(raw), sha256=actual_hash, file_sha256=sha256(raw_bytes).hexdigest())


def higher_order_predicates(seed: Seed) -> frozenset[str]:
    """その種で高階に現れる述語を作る。

    高階＝他の関係を引数に取る位置の述語。種では次の 2 欄がそれにあたる。
      motif_structure[*].third   塔の頂（abm/world.py:110 が higher_1/higher_2 を引数に取る）
      subtrees[*].higher         部分木の頂（abm/world.py:108-109 が fo_* を引数に取る）
    ★ 走行のたびに、読み込んだ種から作る。値をコードに凍結しない（C-33）。
    """

    data = seed.data
    return frozenset(
        {str(row["third"]) for row in data["motif_structure"].values()}
        | {str(sub["higher"]) for sub in data["subtrees"].values()}
    )


def _node_depth(subtrees: Mapping[str, Any], name: str, chain: tuple[str, ...], errors: list[str]) -> int | None:
    """subtrees の 1 ノードを検査し、その階数を返す。壊れていれば None を返す。"""

    if name in chain:
        errors.append(f"subtrees に循環がある: {' -> '.join(chain + (name,))}")
        return None
    if name not in subtrees:
        errors.append(f"subtrees[{name}] が存在しない（未知ノードを暗黙補完しない）")
        return None
    node = subtrees[name]
    if not isinstance(node, Mapping):
        errors.append(f"subtrees[{name}] が object ではない")
        return None
    if "higher" not in node:
        errors.append(f"subtrees[{name}] に higher が無い")
    has_first_order = "first_order" in node
    has_children = "subtrees" in node
    if has_first_order == has_children:
        errors.append(f"subtrees[{name}] は first_order と subtrees のちょうど一方を持つ必要がある")
        return None
    if has_first_order:
        if not node["first_order"]:
            errors.append(f"subtrees[{name}].first_order が空である")
            return None
        return 2
    children = node["subtrees"]
    if not children:
        errors.append(f"subtrees[{name}].subtrees が空である")
        return None
    depths = [_node_depth(subtrees, str(child), chain + (name,), errors) for child in children]
    if any(depth is None for depth in depths):
        return None
    if len(set(depths)) != 1:
        errors.append(f"subtrees[{name}] の子の階数が揃っていない: {depths}")
    return 1 + max(depths)


def validate_structure(data: Mapping[str, Any], errors: list[str]) -> None:
    """参照・循環・順序・ちょうど一方の契約を検査する。★ v1 の種（motif_structure 無し）は対象外。"""

    if "motif_structure" not in data or "subtrees" not in data:
        return
    subtrees = data["subtrees"]
    depths: dict[str, int] = {}
    for motif, row in data["motif_structure"].items():
        if "third" not in row:
            errors.append(f"motif_structure[{motif}] に third（根の述語）が無い")
        children = row.get("subtrees")
        if not children:
            errors.append(f"motif_structure[{motif}].subtrees が空である")
            continue
        child_depths = [_node_depth(subtrees, str(child), (), errors) for child in children]
        if any(depth is None for depth in child_depths):
            continue
        if len(set(child_depths)) != 1:
            errors.append(f"motif_structure[{motif}] の子の階数が揃っていない: {child_depths}")
        depths[motif] = 1 + max(child_depths)
    if data.get("holdout_rate_model") == "structural_first_order_v1" and depths:
        if len(set(depths.values())) != 1:
            errors.append(f"モチーフごとの階数が揃っていない: {dict(sorted(depths.items()))}")


def validate_seed(data: Mapping[str, Any]) -> None:
    """§B.2.2 の5検算を行い、不一致をまとめて報告する。"""

    errors: list[str] = []
    assumptions = data["assumptions"]
    z = float(assumptions["Z"])
    constituents = data["constituents"]
    # 件数は「モチーフ数 × 1 モチーフあたりの層数」であること。
    # ★ 24（v1 の 4×6）と 36（v2 系の 4×9）を決め打ちすると、層の数やモチーフの数が
    #   違う種が落ちる（v2f は 8 モチーフ × 9 層 = 72 件）。
    # ★ constituents の motif 欄だけで確かめる。motif_structure には依存しない
    #   （v1 の種には motif_structure 欄が無い）。
    per_motif = Counter(item.get("motif") for item in constituents)
    if not per_motif:
        errors.append("constituents が空である")
    elif None in per_motif:
        errors.append("constituents に motif 欄が無い行がある")
    elif len(set(per_motif.values())) != 1:
        errors.append(
            "モチーフごとの constituents の件数が揃っていない: "
            f"{dict(sorted(per_motif.items()))}"
        )

    for index, item in enumerate(constituents):
        ell = float(item["ell"])
        arity = int(item["arity"])
        new_slots = int(item["new_slots"])
        c = int(item["c"])
        expected_c = 1 + 3 * arity - 3 * new_slots
        if c != expected_c:
            errors.append(f"constituents[{index}].c: {c} != {expected_c}")
        expected_a = (ell + c) / ell
        if abs(float(item["a"]) - expected_a) > 5e-4:
            errors.append(f"constituents[{index}].a: {item['a']} != {expected_a}")
        expected_ell = -log2(float(item["rate"]) / z)
        if abs(ell - expected_ell) > 5e-4:
            errors.append(f"constituents[{index}].ell: {ell} != {expected_ell}")
        if item["layer"] in ("媒介", "周縁A") and (arity != 2 or new_slots != 1 or c != 4):
            errors.append(f"constituents[{index}] は (a,e) 型の c=4 ではない")

    validate_structure(data, errors)

    marginal_sum = sum(float(value) for value in data["marginal"].values())
    if abs(marginal_sum - 1.0) > 5e-7:
        errors.append(f"marginal の総和が1ではない: {marginal_sum}")
    if errors:
        raise SeedValidationError("; ".join(errors))


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
