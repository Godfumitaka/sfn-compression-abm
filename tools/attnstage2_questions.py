"""第二段の誕生の問いを、承認済みのドア／非ドアだけで重みづけする。

構造の鍵・生成器の名札は受け取らない。仮の問いの区分には、予測前
までにドアの実際の問いで開示された名前と、今見える名前だけを使う。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    door: int
    other: int
    door_names: frozenset[str]
    other_names: frozenset[str]
    current_door: bool

    def virtual_weights(self, visible_names):
        """種類の実際の頻度を、その種類の仮の問いの数で等分する。"""
        names = tuple(visible_names)
        classes = tuple('door' if name in self.door_names else 'other' for name in names)
        n = len(names)
        total = self.door + self.other
        if not n:
            return (), {'door':0, 'other':0, 'overlap':0, 'unassigned_mass':1. if total else 0.}
        counts = {kind:classes.count(kind) for kind in ('door','other')}
        if total == 0:
            weights = (1/n,)*n
            unused = 0.
        else:
            frequency = {'door':self.door/total, 'other':self.other/total}
            weights = tuple(frequency[kind]/counts[kind] for kind in classes)
            # 仮の問いがない種類の頻度を、別の種類へ付け替えない。
            unused = sum(frequency[kind] for kind in counts if counts[kind] == 0)
        rows = tuple({'class':kind, 'weight':weight} for kind,weight in zip(classes,weights))
        return rows, {**counts, 'overlap':sum(name in self.door_names & self.other_names for name in names),
                      'unassigned_mass':unused}


class Questions:
    def __init__(self):
        self.door = self.other = 0
        self.door_names, self.other_names = set(), set()
        self.pending = None

    def present(self, door_task):
        if type(door_task) is not bool or self.pending is not None:
            raise ValueError('実際の問いは二種類の指示で一度だけ数える')
        if door_task:self.door += 1
        else:self.other += 1
        # 今の問いは受け取ったので頻度へ含める。今の開示はまだ含めない。
        snapshot = Snapshot(self.door,self.other,frozenset(self.door_names),
                            frozenset(self.other_names),door_task)
        self.pending = snapshot
        return snapshot

    def finish(self, snapshot, *, fired, feedback=None):
        if snapshot is not self.pending or type(fired) is not bool:
            raise ValueError('問いの控え又は実際の開示の欄が不正')
        if fired:
            # 非開示ではfeedbackへ到達しない。仮の問いはこの入口を使わない。
            name = feedback.predicate
            (self.door_names if snapshot.current_door else self.other_names).add(name)
        self.pending = None

    def record(self):
        return {'door':self.door,'other':self.other,'door_names':sorted(self.door_names),
                'other_names':sorted(self.other_names)}
