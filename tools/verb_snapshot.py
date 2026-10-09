"""指示17：INFO・IDSだけの追加専用の控え。模型の状態と乱数は扱わない。"""
from dataclasses import dataclass


class AppendOnlyViolation(RuntimeError):
    """控えの窓で追加以外の変更が試みられた。"""


def _scalar(value):
    # 現行INFOの値は文字列とbool、IDSの値は文字列。可変な子を素通ししない。
    if type(value) not in (str, bool, int, float, type(None)):
        raise AppendOnlyViolation("INFO・IDSの値に未対応の可変な構造がある")
    return value


class _InfoEntry(dict):
    """INFOの既存値の中身も、窓の中では書き換えられない。"""
    def __init__(self, owner, values):
        self._owner = owner
        super().__init__((key, _scalar(value)) for key, value in values.items())

    def _guard(self):
        if self._owner._marks:
            raise AppendOnlyViolation("控えの窓でINFOの既存値を書き換えた")

    def __setitem__(self, key, value):
        self._guard()
        super().__setitem__(key, _scalar(value))

    def __delitem__(self, key):
        self._guard()
        super().__delitem__(key)

    def clear(self):
        self._guard()
        super().clear()

    def pop(self, key, *default):
        self._guard()
        return super().pop(key, *default)

    def popitem(self):
        self._guard()
        return super().popitem()

    def update(self, *args, **kwargs):
        self._guard()
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self


@dataclass(frozen=True, eq=False)
class AppendOnlyMark:
    owner: object
    length: int


class AppendOnlyDict(dict):
    """写しを作らず、通常の辞書操作を入口で監視し長さだけを控える。"""
    def __init__(self, values=(), *, info=False):
        self._marks = []
        self._info = info
        super().__init__()
        self.update(values)

    def __setitem__(self, key, value):
        if self._marks and key in self:
            raise AppendOnlyViolation("控えの窓でINFO・IDSの既存キーを書き換えた")
        value = _InfoEntry(self, value) if self._info else _scalar(value)
        super().__setitem__(key, value)

    def _guard_delete(self):
        if self._marks:
            raise AppendOnlyViolation("控えの窓でINFO・IDSのキーを消した")

    def __delitem__(self, key):
        self._guard_delete()
        super().__delitem__(key)

    def clear(self):
        self._guard_delete()
        super().clear()

    def pop(self, key, *default):
        self._guard_delete()
        return super().pop(key, *default)

    def popitem(self):
        self._guard_delete()
        return super().popitem()

    def update(self, *args, **kwargs):
        values = dict(*args, **kwargs)
        if self._marks and any(key in self for key in values):
            raise AppendOnlyViolation("控えの窓でINFO・IDSの既存キーを書き換えた")
        for key, value in values.items():
            self[key] = value

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def __ior__(self, other):
        self.update(other)
        return self

    def snapshot(self):
        mark = AppendOnlyMark(self, len(self))
        self._marks.append(mark)
        return mark

    def restore(self, mark):
        if mark.owner is not self or not self._marks or self._marks[-1] is not mark:
            raise AppendOnlyViolation("INFO・IDSの控えの戻し順が不一致")
        if len(self) < mark.length:
            raise AppendOnlyViolation("INFO・IDSが控えの長さより短い")
        # この入口だけが、窓の後で足された末尾を戻せる。既存の順と値は触らない。
        while len(self) > mark.length:
            dict.popitem(self)
        self._marks.pop()


def install(world):
    """旗onのとき、世界の接続後・場面生成前に二つの辞書だけを包む。"""
    if isinstance(world.INFO, AppendOnlyDict) or isinstance(world.IDS, AppendOnlyDict):
        raise AppendOnlyViolation("INFO・IDSの追加専用の入口を二重に接続した")
    world.INFO = AppendOnlyDict(world.INFO, info=True)
    world.IDS = AppendOnlyDict(world.IDS)
