"""固定した対応のC*の期待点。候補の選び直しと世界の正解は使わない。

速い計算は、各局所点の寄与に成立に必要な席の集合を付ける。
検査用の全列挙は別の手続きで対応を取り除いてから点を渡す。
本番への接続前の部品。既存のSMEの入口にはまだ差し込まない。
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math

from sme2017 import Graph, Settings

VERSION = "cstar-fixed-mapping-1"


@dataclass(frozen=True)
class ExpectedScore:
    total: float
    # 左・右の番号、期待局所点、期待伝達点。
    breakdown: tuple[tuple[str, str, float, float], ...]
    # 空集合は物か未知の名前。Noneは引数の対応が足りない。
    dependencies: tuple[tuple[str, frozenset[str] | None], ...]
    # 各位置の局所点の寄与と、その成立に必要な異なる席。
    contributions: tuple[tuple[str, tuple[tuple[float, frozenset[str]], ...]], ...]


def _checked_mapping(left, right, pairs):
    """独立の一対一・順つき引数の検査。隠れた引数は作らない。"""
    pairs = tuple(pairs)
    mapping = dict(pairs)
    if len(mapping) != len(pairs) or len(set(mapping.values())) != len(mapping):
        raise ValueError("固定した対応が一対一でない")
    lb, rb = left.by_id, right.by_id
    for a, b in pairs:
        x, y = lb[a], rb[b]
        if x.kind == "entity" or y.kind == "entity":
            if x.kind != y.kind:
                raise ValueError("物と関係の対応")
            continue
        if "unknown" in {x.kind, y.kind}:
            continue
        if x.kind != y.kind or len(x.args) != len(y.args):
            raise ValueError("関係の種類・引数の数の不一致")
        for u, v in zip(x.args, y.args, strict=True):
            if u in mapping and mapping[u] != v:
                raise ValueError("引数の順の不一致")
    return mapping


def _checked_q(left, right, mapping, probabilities):
    lb, rb = left.by_id, right.by_id
    q = {}
    for a, b in mapping.items():
        x, y = lb[a], rb[b]
        if x.kind == "entity" or "unknown" in {x.kind, y.kind}:
            continue
        value = float(probabilities[a])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError((a, "名前の一致の確率が範囲外", value))
        q[a] = value
    return q


def expected_score(left: Graph, right: Graph, pairs, probabilities, settings=Settings()):
    """固定Mでの線形の期待点。共有された子の確率は集合の和で一度だけ掛ける。"""
    if settings.max_local_score is not None:
        raise ValueError("C*の速い計算は上限なしの点の伝達だけ")
    mapping = _checked_mapping(left, right, pairs)
    q = _checked_q(left, right, mapping, probabilities)
    lb, rb = left.by_id, right.by_id
    dependencies = {}
    children = {}

    def needs(a):
        if a in dependencies:
            return dependencies[a]
        x, y = lb[a], rb[mapping[a]]
        if x.kind == "entity" or "unknown" in {x.kind, y.kind}:
            dependencies[a] = frozenset()
            children[a] = ()
            return dependencies[a]
        actual = []
        required = {a}
        for u, v in zip(x.args, y.args, strict=True):
            if mapping.get(u) != v:
                dependencies[a] = None
                children[a] = ()
                return None
            child_needs = needs(u)
            if child_needs is None:
                dependencies[a] = None
                children[a] = ()
                return None
            actual.append(u)
            required.update(child_needs)
        children[a] = tuple(actual)
        dependencies[a] = frozenset(required)
        return dependencies[a]

    for a in mapping:
        needs(a)
    terms = {a: [] for a in mapping}
    local = {}

    def weight(required):
        # 同じ確率の並びを使い、番号の付け替えで積の丸め順を変えない。
        return math.prod(sorted(q[i] for i in required))

    for a in mapping:
        required = dependencies[a]
        coefficient = settings.same_functor if required else 0.0
        if required is not None and coefficient:
            terms[a].append((coefficient, required))
        local[a] = 0.0 if required is None else coefficient * weight(required)
    heights = left.heights()
    # 親から子へだけ渡す。同じ高さの位置は互いに点を渡さない。
    for a in sorted(mapping, key=lambda k: -heights[k]):
        for child in children[a]:
            needed = dependencies[child]
            if needed is not None:
                terms[child].extend((coefficient * settings.trickle_down, required | needed)
                                    for coefficient, required in terms[a])
    scores = {a: math.fsum(c * weight(required) for c, required in terms[a]) for a in mapping}
    return ExpectedScore(math.fsum(scores.values()),
                         tuple(sorted((a, b, local[a], scores[a] - local[a]) for a, b in mapping.items())),
                         tuple(sorted(dependencies.items())),
                         tuple(sorted((a, tuple(terms[a])) for a in mapping)))


def exhaustive_score(left: Graph, right: Graph, pairs, probabilities, settings=Settings()):
    """検査用。名前の一致・不一致を全列挙し、対応の除去と伝達を毎回行う。

    期待点の依存集合・寄与を使わない。各席の名前は一回だけ引き、
    現在の固定Mの相手の名前に合うかを二場合にまとめる。
    """
    if settings.max_local_score is not None:
        raise ValueError("検査の範囲は上限なしの点の伝達")
    mapping = _checked_mapping(left, right, pairs)
    q = _checked_q(left, right, mapping, probabilities)
    lb, rb = left.by_id, right.by_id
    seats = tuple(q)
    heights = left.heights()
    outcomes = []
    for flags in product((False, True), repeat=len(seats)):
        allowed = dict(zip(seats, flags, strict=True))
        mass = math.prod(q[a] if allowed[a] else 1 - q[a] for a in seats)
        if not mass:
            continue
        remaining = {a for a in mapping if a not in allowed or allowed[a]}
        while True:
            remove = set()
            for a in remaining:
                x, y = lb[a], rb[mapping[a]]
                if x.kind == "entity" or "unknown" in {x.kind, y.kind}:
                    continue
                if any(u not in remaining or mapping.get(u) != v for u, v in zip(x.args, y.args, strict=True)):
                    remove.add(a)
            if not remove:
                break
            remaining.difference_update(remove)
        values = {a: settings.same_functor if a in allowed else 0.0 for a in remaining}
        parents = {a: [] for a in remaining}
        for a in remaining:
            x, y = lb[a], rb[mapping[a]]
            if "unknown" in {x.kind, y.kind}:
                continue
            for child in x.args or ():
                if child in remaining:
                    parents[child].append(a)
        for child in sorted(remaining, key=lambda k: -heights[k]):
            values[child] += settings.trickle_down * math.fsum(values[p] for p in parents[child])
        outcomes.append(mass * math.fsum(values.values()))
    return math.fsum(outcomes)


def structural_self_score(graph: Graph, settings=Settings()):
    """名前が全部合う完全な自己対応を明示的に採点する。F/H/Uは点を変えない。"""
    q = {n.key: 1.0 for n in graph.nodes if n.kind not in {"entity", "unknown"}}
    return expected_score(graph, graph, ((n.key, n.key) for n in graph.nodes), q, settings)
