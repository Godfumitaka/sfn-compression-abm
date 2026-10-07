"""観測部品の共有・循環・文字の鍵・属性・上限を模型なしで一度調べる。"""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import random
import sys
import types

from retained_size_01 import measure, IdentityBitmap


def independent_size(root):
    # 小例専用の通常の集合。模型の大きい控えをこの方法で数えない。
    seen, stack, total = set(), [root], 0
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        total += sys.getsizeof(obj)
        if isinstance(obj, dict):
            stack.extend(dict.keys(obj)); stack.extend(dict.values(obj))
        elif isinstance(obj, (tuple, list, set, frozenset)):
            stack.extend(obj)
    return total, len(seen)


def main():
    root = Path(__file__).resolve().parent
    destination = root / 'checks_01.json'
    assert not destination.exists(), '終わった部品検査を繰り返さない'
    checks = []
    leaf = ('同じ文字の実体を共有する', 100000000000000003)
    data = {'文字の鍵も数える': [leaf, leaf], '別の鍵': leaf}
    data['循環'] = data
    before = repr(data)
    got = measure([('one', data)])
    expected, objects = independent_size(data)
    assert got['complete'] and got['unique_sys_getsizeof_bytes'] == expected
    assert got['unique_objects'] == objects and repr(data) == before
    checks.append(dict(name='循環・共有・文字の鍵', passed=True, bytes=expected, objects=objects))
    other = [data, leaf]
    got = measure([('first', data), ('second', other)])
    expected, objects = independent_size([data, other])
    # 参照を並べる外側の小例のlistだけは観測の根にない。
    expected -= sys.getsizeof([data, other]); objects -= 1
    assert got['unique_sys_getsizeof_bytes'] == expected and got['unique_objects'] == objects
    assert got['groups'][1]['newly_reached_bytes'] == sys.getsizeof(other)
    checks.append(dict(name='根の間の共通実体を二度足さない', passed=True))
    @dataclass(frozen=True, slots=True)
    class Row:
        left: object
        right: object
    row = Row(leaf, leaf)
    got = measure([('slotted', row)])
    expected, objects = independent_size(leaf)
    assert got['unique_sys_getsizeof_bytes'] == sys.getsizeof(row) + expected
    assert got['unique_objects'] == objects + 1
    checks.append(dict(name='slotsの属性と型の除外', passed=True))
    public = types.MappingProxyType(data)
    got = measure([('readonly', public)])
    expected, objects = independent_size(data)
    assert got['unique_sys_getsizeof_bytes'] == sys.getsizeof(public) + expected
    assert got['unique_objects'] == objects + 1 and repr(data) == before
    checks.append(dict(name='読み取り専用の窓口の下の辞書', passed=True))
    private_rng = random.Random(47)
    state_before = private_rng.getstate()
    rng_data = dict(policy='call-seed-uniform-v1', seed=177777777777777)
    got = measure([('rng_record', rng_data)])
    expected, objects = independent_size(rng_data)
    assert got['unique_sys_getsizeof_bytes'] == expected and got['unique_objects'] == objects
    assert private_rng.getstate() == state_before
    checks.append(dict(name='呼び出し種の記録と乱数の不変', passed=True))
    got = measure([('limited', data)], bitmap_limit_bytes=0)
    assert not got['complete'] and got['unique_objects'] == 0 and repr(data) == before
    checks.append(dict(name='観測の上限で模型を操作せず不完全と記す', passed=True))
    marker = IdentityBitmap()
    assert marker.add(data) and not marker.add(data) and marker.add(other)
    checks.append(dict(name='番地の完全な控え', passed=True))
    destination.write_text(json.dumps(dict(at=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
        passed=True, checks=checks, model_not_run=True, source_not_changed=True,
        script_sha256=hashlib.sha256((root/'retained_size_01.py').read_bytes()).hexdigest(),
        python=sys.version), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(passed=True, checks=len(checks), path=str(destination)), ensure_ascii=False))


if __name__ == '__main__':
    main()
