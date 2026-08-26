"""SPEC B0+B2 §B.2 の種読み込みと起動時検算。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import log2
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "U-011_seed_v1.json"


class SeedValidationError(ValueError):
    """種のハッシュまたは内部整合が仕様と異なる。"""


@dataclass(frozen=True, slots=True)
class Seed:
    """検算済みの読み取り専用種。"""

    data: Mapping[str, Any]
    sha256: str


def canonical_seed_bytes(data: Mapping[str, Any]) -> bytes:
    """``sha256`` 欄を除いた種の正準 UTF-8 表現を返す。"""

    payload = dict(data)
    payload.pop("sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seed_hash(data: Mapping[str, Any]) -> str:
    return sha256(canonical_seed_bytes(data)).hexdigest()


def load_seed(path: str | Path = DEFAULT_SEED_PATH) -> Seed:
    """種を読み、ハッシュと内部整合を検査してから固定する。"""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SeedValidationError("種のルートは object である必要がある")
    expected_hash = raw.get("sha256")
    actual_hash = seed_hash(raw)
    if expected_hash != actual_hash:
        raise SeedValidationError(f"種の sha256 が不一致: expected={expected_hash}, actual={actual_hash}")
    validate_seed(raw)
    return Seed(data=_freeze(raw), sha256=actual_hash)


def validate_seed(data: Mapping[str, Any]) -> None:
    """§B.2.2 の5検算を行い、不一致をまとめて報告する。"""

    errors: list[str] = []
    assumptions = data["assumptions"]
    z = float(assumptions["Z"])
    constituents = data["constituents"]
    if len(constituents) != 24:
        errors.append(f"constituents は24件ではない: {len(constituents)}")

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
