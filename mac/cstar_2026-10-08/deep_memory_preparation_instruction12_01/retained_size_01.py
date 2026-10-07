"""模型のデータから届く実体のsys.getsizeofの合計。模型へはまだ未接続。

順に挙げた根の間で同じ実体を一度だけ数える。これはPythonのデータの
大きさであり、割り当て器の余白・常駐・過去の常駐の最大とは別である。
型・関数・moduleへの参照をたどって、実行環境全体を数えることはしない。
"""
from collections import Counter
import gc
import sys
import types


class IdentityBitmap:
    """実体の番地の正確な控え。確率的な重複の判定は使わない。"""

    region_shift = 20
    quantum_shift = 3
    region_bytes = 1 << (region_shift - quantum_shift - 3)

    def __init__(self, limit_bytes=256 * 1024 * 1024):
        self.regions = {}
        self.limit_bytes = limit_bytes

    @property
    def allocated_bytes(self):
        return len(self.regions) * self.region_bytes

    def add(self, obj):
        address = id(obj)
        if address & ((1 << self.quantum_shift) - 1):
            raise ValueError('実体の番地が8バイト境界にない')
        region = address >> self.region_shift
        offset = (address & ((1 << self.region_shift) - 1)) >> self.quantum_shift
        bits = self.regions.get(region)
        if bits is None:
            if self.allocated_bytes + self.region_bytes > self.limit_bytes:
                raise MemoryError('観測の番地の控えが前もって決めた上限に達した')
            bits = bytearray(self.region_bytes)
            self.regions[region] = bits
        byte, bit = divmod(offset, 8)
        mask = 1 << bit
        if bits[byte] & mask:
            return False
        bits[byte] |= mask
        return True


EXCLUDED = (type, types.ModuleType, types.FunctionType, types.MethodType,
            types.BuiltinFunctionType, types.BuiltinMethodType, types.CodeType,
            types.FrameType, types.TracebackType)
ATOMIC = (str, bytes, bytearray, int, float, complex, bool, type(None))


def children(obj):
    # Unicodeの鍵はgcの参照一覧に出ない場合があるため、辞書を明示する。
    # CacheTable等の観測外の管理者の属性は、このデータの根には含めない。
    if isinstance(obj, dict):
        for key, value in dict.items(obj):
            yield key
            yield value
    elif isinstance(obj, (tuple, list, set, frozenset)):
        yield from obj
    elif not isinstance(obj, ATOMIC):
        # __dict__を新しく実体化せず、CPythonが保持する参照だけを読む。
        yield from gc.get_referents(obj)


def measure(roots, *, bitmap_limit_bytes=256 * 1024 * 1024):
    """根は(label, obj)の列。共通実体の大きさは先の根に一度だけ入る。"""
    seen = IdentityBitmap(bitmap_limit_bytes)
    groups = []
    total_bytes = total_objects = 0
    complete = True
    reason = None
    exhausted = object()
    for label, root in roots:
        counts, sizes = Counter(), Counter()
        excluded = Counter()
        stack = [iter((root,))]
        try:
            while stack:
                obj = next(stack[-1], exhausted)
                if obj is exhausted:
                    stack.pop()
                    continue
                if isinstance(obj, EXCLUDED):
                    excluded[type(obj).__name__] += 1
                    continue
                if not seen.add(obj):
                    continue
                name = type(obj).__module__ + '.' + type(obj).__qualname__
                size = sys.getsizeof(obj)
                counts[name] += 1
                sizes[name] += size
                total_bytes += size
                total_objects += 1
                stack.append(iter(children(obj)))
        except (MemoryError, ValueError) as exc:
            complete, reason = False, str(exc)
        groups.append(dict(label=label, newly_reached_objects=sum(counts.values()),
                           newly_reached_bytes=sum(sizes.values()),
                           types=[dict(type=k, objects=counts[k], bytes=sizes[k])
                                  for k in sorted(counts)],
                           excluded_environment_references=dict(excluded)))
        if not complete:
            break
    return dict(complete=complete, reason=reason, unique_objects=total_objects,
                unique_sys_getsizeof_bytes=total_bytes, groups=groups,
                observer_bitmap_bytes=seen.allocated_bytes,
                observer_bitmap_limit_bytes=bitmap_limit_bytes,
                interpretation='根の順で初めて届く実体だけを数える。共通実体の大きさは先の根に入る。'
                  '型と関数とmodule等の実行環境、割り当て器の余白、未使用ページ、Cの内部で'
                  'sys.getsizeofとgcの参照から読めない領域は含まない。常駐との差を候補の大きさとはしない。')
