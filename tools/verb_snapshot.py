"""指示20：INFO・IDSの長さだけ控え、同じ控えを繰り返し戻す。"""
from dataclasses import dataclass


class AppendOnlyViolation(RuntimeError):
    """控えの窓で追加以外の変更が試みられた。"""


def _scalar(value):
    # 現行INFOの値は文字列とbool、IDSの値は文字列。可変な子を素通ししない。
    if type(value) not in (str, bool, int, float, type(None)):
        raise AppendOnlyViolation("INFO・IDSの値に未対応の可変な構造がある")
    return value


class _InfoEntry(dict):
    """verb_trialが一度記したINFOの値を、後から書き換えない。"""
    def __init__(self, owner, values):
        self._owner = owner
        super().__init__((key, _scalar(value)) for key, value in values.items())

    def _guard(self):
        raise AppendOnlyViolation("INFOの既存値を書き換えた")

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
    """既存項目の変更を入口で止め、控えには所有者と長さだけ持つ。"""
    def __init__(self, values=(), *, info=False):
        self._info = info
        super().__init__()
        self.update(values)

    def __setitem__(self, key, value):
        if key in self:
            raise AppendOnlyViolation("INFO・IDSの既存キーを書き換えた")
        value = _InfoEntry(self, value) if self._info else _scalar(value)
        super().__setitem__(key, value)

    def _guard_delete(self):
        raise AppendOnlyViolation("INFO・IDSのキーを消した")

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
        if any(key in self for key in values):
            raise AppendOnlyViolation("INFO・IDSの既存キーを書き換えた")
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
        return AppendOnlyMark(self, len(self))

    def restore(self, mark):
        if mark.owner is not self:
            raise AppendOnlyViolation("INFO・IDSの控えの所有者が不一致")
        if len(self) < mark.length:
            raise AppendOnlyViolation("INFO・IDSが控えの長さより短い")
        # 印を消費しない。同じ控えへ二度・三度戻しても、既存の順と値は触らない。
        while len(self) > mark.length:
            dict.popitem(self)


def append_trial(info_table, ids_table, graph_id, info):
    """唯一の書き込み入口verb_trialで、三つのキーを変更前に確認する。"""
    keys = (info["name_id"], info["link_id"])
    if graph_id in info_table or any(key in ids_table for key in keys) or keys[0] == keys[1]:
        raise AppendOnlyViolation("verb_trialでINFO・IDSの既存キーを上書きする")
    info_table[graph_id] = info
    ids_table[keys[0]] = "name"
    ids_table[keys[1]] = "link"


def install(world):
    """旗onのとき、世界の接続後・場面生成前に二つの辞書だけを包む。"""
    if isinstance(world.INFO, AppendOnlyDict) or isinstance(world.IDS, AppendOnlyDict):
        raise AppendOnlyViolation("INFO・IDSの追加専用の入口を二重に接続した")
    world.INFO = AppendOnlyDict(world.INFO, info=True)
    world.IDS = AppendOnlyDict(world.IDS)
