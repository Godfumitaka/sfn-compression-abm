"""計算後の不変の部分だけを共有し、全ての論理的な控えと記録を残す。

照合も乱数の呼び出しも省かない。式・対応・順・型・浮動小数のビットを
変更しない。共有を決める表は模型に渡さない、512組までの作業用の表。
"""
from collections import OrderedDict
from dataclasses import fields, replace
import struct

import sme2017

POOL = OrderedDict()
STATS = {}
LIMIT = 512
CLASSES = frozenset({sme2017.Hypothesis, sme2017.Candidate, sme2017.Settings})


def exact(a, b):
    """内容が同じでも、型の差と±0とNaNのビットの差を同一視しない。"""
    if type(a) is not type(b):
        return False
    if type(a) is float:
        return struct.pack('>d', a) == struct.pack('>d', b)
    if type(a) in (str, int, bool, type(None)):
        return a == b
    if type(a) is tuple:
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if type(a) is frozenset:
        # Candidate.membersは整数だけ。その他の集合は共有しない。
        return all(type(x) is int for x in a) and all(type(x) is int for x in b) and a == b
    if type(a) in CLASSES:
        return all(exact(getattr(a, f.name), getattr(b, f.name)) for f in fields(a))
    return False


def share(result):
    key = result.version, result.settings, result.left_fingerprint, result.right_fingerprint
    previous = POOL.pop(key, None)
    changed = {}
    if previous is not None:
        for name in ('hypotheses', 'candidates'):
            before, now = previous[name], getattr(result, name)
            if exact(before, now):
                changed[name] = before
                STATS[name] = STATS.get(name, 0) + 1
    if changed:
        result = replace(result, **changed)
    POOL[key] = {name: getattr(result, name) for name in ('hypotheses', 'candidates')}
    if len(POOL) > LIMIT:
        POOL.popitem(last=False)
    STATS['calls'] = STATS.get('calls', 0) + 1
    STATS['pool_peak'] = max(STATS.get('pool_peak', 0), len(POOL))
    return result


def install():
    POOL.clear()
    STATS.clear()
    real = sme2017._Engine.run

    def run(self):
        # 本来の乱数と照合を全て実行した後に、同一の内容だけ共有する。
        return share(real(self))

    sme2017._Engine.run = run
