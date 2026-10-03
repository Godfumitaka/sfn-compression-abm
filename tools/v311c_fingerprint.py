"""研究者用の状態指紋。集合だけ整列し、模型が読める列と辞書の順序は保存する。"""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from hashlib import sha256
import json

VERSION = "sets-sorted-v1"


def _text(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def canonical(value):
    """型と全フィールドを残す。未知の型をreprへ落として通さない。"""
    if value is None:
        return ["none"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is float:
        return ["float", value.hex()]
    if type(value) is str:
        return ["str", value]
    if is_dataclass(value) and not isinstance(value, type):
        cls = type(value)
        return ["dataclass", cls.__module__, cls.__qualname__,
                [[f.name, canonical(getattr(value, f.name))] for f in fields(value)]]
    if isinstance(value, Mapping):
        return ["mapping", [[canonical(k), canonical(v)] for k, v in value.items()]]
    if type(value) in (set, frozenset):
        return [type(value).__name__, sorted((canonical(v) for v in value), key=_text)]
    if type(value) in (tuple, list):
        return [type(value).__name__, [canonical(v) for v in value]]
    raise TypeError(f"状態指紋に未対応の型: {type(value).__module__}.{type(value).__qualname__}")


def canonical_text(value):
    return _text([VERSION, canonical(value)])


def fingerprint(value):
    return sha256(canonical_text(value).encode("utf-8")).hexdigest()
