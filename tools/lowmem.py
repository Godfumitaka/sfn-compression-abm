"""メモリを減らす書き直し（2026-09-25、アストラさん了承の案。旗 --lowmem、既定オフ）。
★ abm/loop.py の状態の正準形の控え（loop.py:31-33・:640-677）の持ち方だけを変える。正準形・repr・差分・指紋の作り方は変えない。
★ 今のコード：控え（_CANONICAL_CACHE・_CANONICAL_KEEP・_REPR_CACHE）は走行の始めに一度空にするだけで、1,740 試行のあいだ捨てない。
★ 書き直し：
   1 一試行のあいだに「触った」物（正準形を作った物・控えから返した物とその子孫すべて）を記録する。
     控えに入れるとき、その物の子孫（控えの対象になる物）の id を平らな並びで一緒に控える。
     控えから返すときは、その並びで子孫もまとめて「触った」にする（正準形は作り直さない）。
   2 次の試行の台帳を書き始める前に、三つの控えを「前の試行で触った物だけ」に絞る。
     物そのもの（KEEP）も同じく絞るので、控えにある物の id が別の物に使い回されることはない。
★ 台帳が一字一句同じになる理由は analysis_v3_2026-09-25/案_メモリを減らす書き直し_2026-09-25.md。
使い方  ドライバの作業プロセスの中で install() を一度呼ぶ（sweep.run_one の前）。"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Mapping

CACHE: dict[int, Any] = {}
KEEP: dict[int, Any] = {}
DESC: dict[int, list[int]] = {}
REPR: dict[int, str] = {}
TOUCHED: set[int] = set()
STACK: list[list[int]] = []
STATE = {"trial": None, "evictions": 0, "max_cache": 0}


def install() -> None:
    import abm.loop as loop

    omit = loop._SNAPSHOT_OMIT_IF_EMPTY
    for d in (CACHE, KEEP, DESC, REPR):
        d.clear()
    TOUCHED.clear(); STACK.clear()
    STATE.update(trial=None, evictions=0, max_cache=0)

    def _cacheable(value):
        return is_dataclass(value) or isinstance(value, (tuple, frozenset))

    def _canonical(value: Any) -> Any:
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

    # ★ loop.py:651-664 の写し。呼ぶ _canonical・_canonical_sort_key だけがこちらの関数になる。
    def _canonical_build(value: Any) -> Any:
        if is_dataclass(value):
            return {
                field.name: _canonical(getattr(value, field.name)) for field in fields(value)
                if not (field.name in omit and not getattr(value, field.name))
            }
        if isinstance(value, Mapping):
            return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
        if isinstance(value, (tuple, list, frozenset, set)):
            return [_canonical(item) for item in sorted(value, key=_canonical_sort_key) if item is not None]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)

    # ★ loop.py:667-677 の写し（控えの置き場所だけが違う）。
    def _canonical_sort_key(value: Any) -> str:
        if _cacheable(value):
            key = id(value)
            cached = REPR.get(key)
            if cached is not None:
                return cached
            rendered = repr(value)
            REPR[key] = rendered
            return rendered
        return repr(value)

    def _evict() -> None:
        keep = TOUCHED
        for d in (CACHE, KEEP, DESC):
            for k in [k for k in d if k not in keep]:
                del d[k]
        for k in [k for k in REPR if k not in keep]:
            del REPR[k]
        STATE["evictions"] += 1
        STATE["max_cache"] = max(STATE["max_cache"], len(CACHE))
        TOUCHED.clear()

    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **kw):
        # ★ 試行が変わった最初の台帳の前に、前の試行で触った物だけに絞る（エージェントが複数でも試行単位）。
        t = trial.trial
        if STATE["trial"] is not None and t != STATE["trial"]:
            _evict()
        STATE["trial"] = t
        return real_record(agent_id, trial, *a, **kw)

    loop._canonical = _canonical
    loop._canonical_build = _canonical_build
    loop._canonical_sort_key = _canonical_sort_key
    loop._ledger_record = _ledger_record
