"""研究者用の状態指紋。集合だけ整列し、模型が読める列と辞書の順序は保存する。"""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from hashlib import sha256
import json
from fractions import Fraction

VERSION = "sets-sorted-sme-dag-v3"


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
    if type(value) is Fraction:
        return ["fraction", str(value.numerator), str(value.denominator)]
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


def _digest(value, memo, active):
    """共有された控えを一度だけ読む。実体の番号を指紋の材料へ入れない。"""
    composite = (is_dataclass(value) and not isinstance(value, type)) or isinstance(value, Mapping) or type(value) in (set, frozenset, tuple, list)
    if not composite:
        return sha256(_text(canonical(value)).encode("utf-8")).digest()
    key = id(value)
    if key in memo:
        return memo[key]
    if key in active:
        raise ValueError("状態指紋に循環がある")
    active.add(key)
    h = sha256()
    if is_dataclass(value) and not isinstance(value, type):
        cls = type(value)
        fs = fields(value)
        h.update(_text(["dataclass", cls.__module__, cls.__qualname__, len(fs)]).encode("utf-8"))
        for f in fs:
            h.update(_digest(f.name, memo, active))
            h.update(_digest(getattr(value, f.name), memo, active))
    elif isinstance(value, Mapping):
        h.update(_text(["mapping", len(value)]).encode("utf-8"))
        for k, v in value.items():
            h.update(_digest(k, memo, active))
            h.update(_digest(v, memo, active))
    else:
        h.update(_text([type(value).__name__, len(value)]).encode("utf-8"))
        children = (_digest(v, memo, active) for v in value)
        if type(value) in (set, frozenset):
            children = sorted(children)
        for child in children:
            h.update(child)
    result = h.digest()
    active.remove(key)
    memo[key] = result
    return result


def fingerprint(value):
    # 型・値・順序はすべて下位の指紋へ入る。共有の有無が違っても同じ内容なら同じ指紋になる。
    root = _digest(value, {}, set())
    return sha256(_text(VERSION).encode("utf-8") + root).hexdigest()
