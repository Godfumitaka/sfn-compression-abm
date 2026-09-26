"""台帳の記録を速くする書き直し（2026-09-26 の試し。旗 --fast、既定オフ）。★ 台帳は一字一句同じにする。★ abm/ は変えない。
lowmem.py の控えの持ち方（前の試行で触った物とその子孫だけを残す）をそのまま含み、その上で次の四つを変える。
出力（正準形・差分・指紋・台帳）の作り方の規則は変えない。同じ値を、少ない手間で作るだけ。

 1 _key（loop.py:552-553）
   数値・文字列・真偽・None は、json.dumps と同じ文字列を直接作る（encoder を毎回作らない）。
   dict・list は id で結果を控える（物そのものも一緒に持つので、id の使い回しは起きない）。
   → 毎試行、変わらない要素（public_history の要素など）を json.dumps し直さない。
 2 _diff（loop.py:556-603）
   中身は同じ。同一物の短絡を呼び出しの前に行い、要素がすべて同一物の list は鍵を作らずに「変わらない」とする
   （同一物なら鍵は同じなので、元の「鍵の並びが同じなら None」と同じ結果になる）。
 3 指紋（loop.py:468・:681-682）
   状態の JSON を、部分木ごとの JSON の断片から組み立てる。断片は id で控える。
   規則は json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False) と同じ
   （dict は鍵の順、文字列は encode_basestring、浮動小数は float.__repr__ と NaN/Infinity）。
 4 _canonical（loop.py:640-677 と lowmem.py:38-82）
   数値・文字列を先に返す。dataclass の判定と欄名を型ごとに控える。要素が数値・文字列だけの並びは、
   sorted(value, key=repr) で直接作る（元の並べ替えの鍵もこの場合 repr なので同じ）。
 5 浮動小数だけの並び（merit・exceptions の 16 本の基底など）（2026-09-26 二回目）
   正準形を作るとき、並べ替えに使う repr をそのまま「差分の鍵」として控える（LKEYS）。
   浮動小数では repr と json.dumps の文字列は、等しいかどうかの関係が同じ（有限なら同じ文字列、nan/inf は一対一）。
   鍵は比べるためだけに使い、台帳には出ないので、差分の結果は同じになる。両方の並びに控えがあるときだけ使う。
   有限の値だけなら、指紋の断片も "[" + ",".join(repr) + "]" で作る（json.dumps の浮動小数は float.__repr__）。
   差分で、元の鍵と新しい鍵に共通が一つも無いときは、Counter を使わずに結果を直接作る
   （loop._diff の手順をたどると、d は元の全位置、i は新の全位置と値になる）。
使い方  ドライバの作業プロセスの中で install() を一度呼ぶ（sweep.run_one の前）。lowmem.install() の代わりに使う。
        nohist.install() と組み合わせるときは、nohist を先に呼ぶ。
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import fields, is_dataclass as _is_dataclass
from json.encoder import encode_basestring as _esc, encode_basestring_ascii as _esc_ascii
from math import isfinite as _isfinite
from operator import is_ as _is
from types import MappingProxyType
from typing import Any, Mapping

CACHE: dict[int, Any] = {}
KEEP: dict[int, Any] = {}
DESC: dict[int, list[int]] = {}
REPR: dict[int, str] = {}
TOUCHED: set[int] = set()
STACK: list[list[int]] = []
KEYM: dict[int, tuple[Any, str]] = {}
KEYT: set[int] = set()
FRAGM: dict[int, tuple[Any, str]] = {}
FRAGT: set[int] = set()
LKEYS: dict[int, tuple[list, list[str], bool]] = {}   # id(浮動小数だけの正準形の並び) -> (並び, 各要素の repr, すべて有限か)
LKEYT: set[int] = set()
STATE = {"trial": None, "evictions": 0, "max_cache": 0}

_PRIMS = frozenset({str, int, float, bool, type(None)})
_INF = float("inf")
_float_repr = float.__repr__
_int_repr = int.__repr__
# ★ loop._key と同じ設定（json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))）の encoder を一つだけ作る
_KEY_ENC = json.JSONEncoder(sort_keys=True, default=str, separators=(",", ":"))
# ★ loop._json_bytes と同じ設定（json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)）
_HASH_ENC = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
_DC: dict[type, bool] = {}
_FIELD_NAMES: dict[type, tuple[str, ...]] = {}


def _floatstr(value: float) -> str:
    # ★ json の allow_nan=True と同じ（json/encoder.py floatstr・C の encoder_encode_float）
    if value != value:
        return "NaN"
    if value == _INF:
        return "Infinity"
    if value == -_INF:
        return "-Infinity"
    return _float_repr(value)


def _isdc(value: Any) -> bool:
    # ★ dataclasses.is_dataclass と同じ（インスタンスは型の __dataclass_fields__ の有無）。型ごとに控える。
    if isinstance(value, type):
        return _is_dataclass(value)
    t = type(value)
    r = _DC.get(t)
    if r is None:
        r = _DC[t] = _is_dataclass(value)
    return r


def _cacheable(value: Any) -> bool:
    t = type(value)
    if t is tuple or t is frozenset:
        return True
    return _isdc(value) or isinstance(value, (tuple, frozenset))


def install() -> None:
    import abm.loop as loop

    omit = loop._SNAPSHOT_OMIT_IF_EMPTY
    deleted = loop._DELETED
    for d in (CACHE, KEEP, DESC, REPR, KEYM, FRAGM, LKEYS):
        d.clear()
    for s in (TOUCHED, KEYT, FRAGT, LKEYT):
        s.clear()
    STACK.clear()
    STATE.update(trial=None, evictions=0, max_cache=0)

    # ---- 4 正準形（lowmem.py:38-82 と同じ控え方。数値・文字列の近道だけを足す）
    def _canonical(value: Any) -> Any:
        if type(value) in _PRIMS:
            return value
        if _cacheable(value):
            key = id(value)
            if key in CACHE:
                d = DESC[key]
                TOUCHED.add(key); TOUCHED.update(d)
                if STACK:
                    top = STACK[-1]; top.append(key); top.extend(d)
                return CACHE[key]
            STACK.append([])
            result = _canonical_build(value)
            d = STACK.pop()
            CACHE[key] = result; KEEP[key] = value; DESC[key] = d
            TOUCHED.add(key)
            if STACK:
                top = STACK[-1]; top.append(key); top.extend(d)
            return result
        return _canonical_build(value)

    def _pair_key(pair):
        return str(pair[0])

    def _canonical_build(value: Any) -> Any:
        t = type(value)
        if t in _PRIMS:
            return value
        if _isdc(value):
            names = _FIELD_NAMES.get(t)
            if names is None:
                names = _FIELD_NAMES[t] = tuple(field.name for field in fields(value))
            return {name: _canonical(getattr(value, name)) for name in names
                    if not (name in omit and not getattr(value, name))}
        if t is dict or t is MappingProxyType or isinstance(value, Mapping):
            return {str(key): _canonical(item) for key, item in sorted(value.items(), key=_pair_key)}
        if isinstance(value, (tuple, list, frozenset, set)):
            all_float = True
            for item in value:
                t_item = type(item)
                if t_item is not float:
                    all_float = False
                    if t_item not in _PRIMS:
                        break
            else:
                if all_float:
                    # ★ 5 浮動小数だけ：repr で並べ替え（元の鍵と同じ・安定）、その repr を差分の鍵として控える
                    vals = list(value)
                    reps = [_float_repr(x) for x in vals]
                    order = sorted(range(len(vals)), key=reps.__getitem__)
                    result = [vals[i] for i in order]
                    LKEYS[id(result)] = (result, [reps[i] for i in order], all(map(_isfinite, vals)))
                    LKEYT.add(id(result))
                    return result
                # ★ 要素が数値・文字列だけ：元の並べ替えの鍵（_canonical_sort_key）は repr、_canonical は値そのもの
                return [item for item in sorted(value, key=repr) if item is not None]
            return [_canonical(item) for item in sorted(value, key=_canonical_sort_key) if item is not None]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    def _canonical_sort_key(value: Any) -> str:
        if type(value) in _PRIMS:
            return repr(value)
        if _cacheable(value):
            key = id(value)
            cached = REPR.get(key)
            if cached is not None:
                return cached
            rendered = repr(value)
            REPR[key] = rendered
            return rendered
        return repr(value)

    # ---- 1 差分の鍵（loop._key と同じ文字列）
    def _key(value: object) -> str:
        t = type(value)
        if t is float:
            return _floatstr(value)
        if t is str:
            return _esc_ascii(value)
        if t is int:
            return _int_repr(value)
        if t is bool:
            return "true" if value else "false"
        if value is None:
            return "null"
        if t is dict or t is list:
            k = id(value)
            e = KEYM.get(k)
            if e is not None and e[0] is value:
                KEYT.add(k)
                return e[1]
            s = _KEY_ENC.encode(value)
            KEYM[k] = (value, s); KEYT.add(k)
            return s
        return _KEY_ENC.encode(value)

    # ---- 2 差分（loop.py:556-603 と同じ。短絡を前に出しただけ）
    def _diff(old: object, new: object) -> object | None:
        if old is new and isinstance(old, (dict, list)):
            return None
        if isinstance(old, dict) and isinstance(new, dict):
            out = {}
            for key in new:
                if key not in old:
                    out[key] = {"set": new[key]}
                else:
                    o = old[key]; n = new[key]
                    if o is n and isinstance(o, (dict, list)):
                        continue
                    difference = _diff(o, n)
                    if difference is not None:
                        out[key] = difference
            for key in old:
                if key not in new:
                    out[key] = deleted
            return out or None
        if isinstance(old, list) and isinstance(new, list):
            if len(old) == len(new) and all(map(_is, old, new)):
                return None
            lo = LKEYS.get(id(old)); ln = LKEYS.get(id(new))
            if lo is not None and lo[0] is old and ln is not None and ln[0] is new:
                LKEYT.add(id(old)); LKEYT.add(id(new))
                old_keys, new_keys = lo[1], ln[1]
            else:
                old_keys, new_keys = [_key(x) for x in old], [_key(x) for x in new]
            if old_keys == new_keys:
                return None
            if set(old_keys).isdisjoint(new_keys):
                # ★ 5 共通の鍵が無い：下の手順の結果は d＝元の全位置、i＝新の全位置と値（current_keys は new_keys に一致）
                return {"ld": {"d": list(range(len(old))), "i": [[index, value] for index, value in enumerate(new)]}}
            old_counts, new_counts = Counter(old_keys), Counter(new_keys)
            needed = new_counts - old_counts
            insertions = []
            insertion_keys = []
            for index, key in enumerate(new_keys):
                if needed[key] > 0:
                    insertions.append([index, new[index]]); insertion_keys.append(key); needed[key] -= 1
            needed = old_counts - new_counts
            deletions = []
            for index, key in enumerate(old_keys):
                if needed[key] > 0:
                    deletions.append(index); needed[key] -= 1
            current_keys = list(old_keys)
            for index in sorted(deletions, reverse=True): current_keys.pop(index)
            for (index, _value), key in zip(insertions, insertion_keys): current_keys.insert(index, key)
            if current_keys != new_keys:
                return {"set": new}
            return {"ld": {"d": deletions, "i": insertions}}
        if old == new:
            return None
        return {"set": new}

    # ---- 3 指紋の JSON（json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) と同じ文字列）
    def _frag(value: Any) -> str:
        t = type(value)
        if t is str:
            return _esc(value)
        if t is float:
            return _floatstr(value)
        if t is bool:
            return "true" if value else "false"
        if t is int:
            return _int_repr(value)
        if value is None:
            return "null"
        if t is dict or t is list:
            k = id(value)
            e = FRAGM.get(k)
            if e is not None and e[0] is value:
                FRAGT.add(k)
                return e[1]
            lk = LKEYS.get(k) if t is list else None
            if lk is not None and lk[0] is value and lk[2]:
                LKEYT.add(k)
                s = "[" + ",".join(lk[1]) + "]"   # ★ 5 有限の浮動小数だけ：json.dumps と同じ（float.__repr__）
            elif t is list:
                for item in value:
                    if type(item) is dict or type(item) is list:
                        s = "[" + ",".join([_frag(x) for x in value]) + "]"
                        break
                else:
                    s = _HASH_ENC.encode(value)   # 要素が数値・文字列だけの並びは C の encoder に任せる
            else:
                if all(type(key) is str for key in value):
                    s = "{" + ",".join([_esc(key) + ":" + _frag(value[key]) for key in sorted(value)]) + "}"
                else:
                    s = _HASH_ENC.encode(value)
            FRAGM[k] = (value, s); FRAGT.add(k)
            return s
        return _HASH_ENC.encode(value)

    def _json_bytes(value: Any) -> bytes:
        return _frag(value).encode()

    # ---- 控えの整理（lowmem.py:84-93 と同じ規則。差分の鍵と指紋の断片も同じ時に絞る）
    def _evict() -> None:
        keep = TOUCHED
        for d in (CACHE, KEEP, DESC):
            for k in [k for k in d if k not in keep]:
                del d[k]
        for k in [k for k in REPR if k not in keep]:
            del REPR[k]
        for memo, touched in ((KEYM, KEYT), (FRAGM, FRAGT), (LKEYS, LKEYT)):
            for k in [k for k in memo if k not in touched]:
                del memo[k]
            touched.clear()
        STATE["evictions"] += 1
        STATE["max_cache"] = max(STATE["max_cache"], len(CACHE))
        TOUCHED.clear()

    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **kw):
        t = trial.trial
        if STATE["trial"] is not None and t != STATE["trial"]:
            _evict()
        STATE["trial"] = t
        return real_record(agent_id, trial, *a, **kw)

    loop._canonical = _canonical
    loop._canonical_build = _canonical_build
    loop._canonical_sort_key = _canonical_sort_key
    loop._key = _key
    loop._diff = _diff
    loop._json_bytes = _json_bytes
    loop._ledger_record = _ledger_record
