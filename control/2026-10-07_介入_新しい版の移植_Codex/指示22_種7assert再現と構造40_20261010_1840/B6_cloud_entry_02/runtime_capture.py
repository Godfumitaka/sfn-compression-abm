"""c4の追加状態の読み取り関数を同一で写す。計算は変えない。"""
from collections.abc import Mapping
from dataclasses import fields,is_dataclass
from enum import Enum
from fractions import Fraction
import sys

def runtime_values(value, memo=None):
    """既知の追加状態を型・順付きで読む。未知の型をreprへ落とさない。"""
    memo = {} if memo is None else memo
    if isinstance(value, Enum):
        return ["enum", type(value).__module__, type(value).__name__, value.value]
    if value is None or type(value) in (str, int, float, bool, Fraction):
        return value
    key = id(value)
    if key in memo:
        return memo[key]
    if is_dataclass(value):
        out = ["dataclass", type(value).__module__, type(value).__name__, []]
        memo[key] = out
        out[3].extend((f.name, runtime_values(getattr(value, f.name), memo)) for f in fields(value))
        return out
    if isinstance(value, Mapping):
        out = ["mapping", []]; memo[key] = out
        out[1].extend((runtime_values(k, memo), runtime_values(v, memo)) for k, v in value.items())
        return out
    if type(value) in (set, frozenset):
        from v311c_fingerprint import canonical_text
        out = [type(value).__name__, sorted((runtime_values(v, memo) for v in value), key=canonical_text)]
        memo[key] = out
        return out
    if type(value) in (list, tuple):
        out = type(value)(runtime_values(v, memo) for v in value)
        memo[key] = out
        return out
    if (type(value).__module__, type(value).__name__) in (
            ("attnsme_features", "Observations"), ("attnstage2_questions", "Questions")):
        out = ["object", type(value).__module__, type(value).__name__, None]
        memo[key] = out
        out[3] = runtime_values(vars(value), memo)
        return out
    raise TypeError((type(value), "集団化の追加状態の検査で扱わない型"))

def runtime_record():
    """次の実課題が読む観察・注意・問い回数・実開示の名前を全量で残す。"""
    out = {}
    attention = sys.modules.get("attnsme")
    if attention is not None and attention.ST:
        out["attention"] = runtime_values(attention.ST["individuals"])
    stage2 = sys.modules.get("attnstage2_runtime")
    if stage2 is not None and stage2.ST:
        out["questions"] = runtime_values(stage2.ST["questions"])
    return out
