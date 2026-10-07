"""一つの反実仮想Sessionだけで使う、点を持たないC*照合の土台。"""
from dataclasses import dataclass


def shape(graph):
    # 名前・F/H/U・確率を控えの鍵に入れない。順序と未知の引数は保持する。
    return tuple((n.key, n.kind, n.args, n.ubiquitous) for n in graph.nodes)


@dataclass(frozen=True)
class Plan:
    kind: str
    children: tuple
    pairs: frozenset
    consistent: bool


@dataclass(frozen=True)
class StructureNode:
    kind: str
    args: tuple | None
    ubiquitous: bool


class Foundation:
    def __init__(self, left, right):
        self.left, self.right = (
            {n.key: StructureNode(n.kind, n.args, n.ubiquitous) for n in graph.nodes}
            for graph in (left, right))
        self.plans = {}

    def plan(self, lk, rk, parent=False):
        key = lk, rk, parent
        if key in self.plans:
            return self.plans[key]
        l, r = self.left[lk], self.right[rk]
        if 'entity' in (l.kind, r.kind):
            kind = 'entity' if l.kind == r.kind else 'invalid'
        elif 'unknown' in (l.kind, r.kind):
            kind = 'hidden'
        elif l.kind != r.kind or len(l.args) != len(r.args):
            kind = 'invalid'
        elif not parent and (l.ubiquitous or r.ubiquitous):
            kind = 'invalid'
        else:
            kind = 'probability'
        children = tuple(zip(l.args, r.args, strict=True)) if kind == 'probability' else ()
        pairs = frozenset({(lk, rk)}).union(
            *(self.plan(a, b, True).pairs for a, b in children))
        lm, rm = {}, {}
        consistent = True
        for a, b in pairs:
            if a in lm and lm[a] != b or b in rm and rm[b] != a:
                consistent = False
            lm[a], rm[b] = b, a
        value = Plan(kind, children, pairs, consistent)
        self.plans[key] = value
        return value


class Store:
    """試行・履歴をまたがず、構造が違えば別の土台を作る。"""
    def __init__(self):
        self.foundations = {}

    def get(self, left, right):
        key = shape(left), shape(right)
        built = key not in self.foundations
        if built:
            self.foundations[key] = Foundation(left, right)
        return self.foundations[key], built
