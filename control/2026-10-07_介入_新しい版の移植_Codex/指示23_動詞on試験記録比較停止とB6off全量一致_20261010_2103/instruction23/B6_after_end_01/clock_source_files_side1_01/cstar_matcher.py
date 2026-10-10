"""SMEの候補生成・結合・順位の各段をC*の期待点で計算する部品。

最終的な固定Mの点は独立の全列挙と照合する。候補探索は原典と同じ
貪欲な近似であり、全てのMを列挙した最適解とはしない。
"""
from __future__ import annotations

from dataclasses import replace
from contextlib import contextmanager
from itertools import product
import math
import random
import time

from sme2017 import Hypothesis, Matcher, _Engine
from cstar_probability import checked_distribution
from cstar_score import _checked_mapping, structural_self_score

VERSION = "sme-cstar-expectation-1"


def probability_key(probabilities):
    return tuple(sorted((seat, tuple(sorted(((name, float(p)) for name, p in dist.items()),
                                           key=lambda x: (x[0] is None, x[0] or ""))))
                        for seat, dist in probabilities.items()))


class CstarMatcher(Matcher):
    @contextmanager
    def stage2_scope(self, store, stats):
        old = getattr(self, '_stage2_scope', None)
        self._stage2_scope = store, stats
        try:
            yield
        finally:
            if old is None:
                del self._stage2_scope
            else:
                self._stage2_scope = old

    def match_key(self, left, right, tie_seed=None, *, probabilities):
        # b・履歴を反映したqを鍵に含める。更新後の値を古い控えで返さない。
        return (VERSION, probability_key(probabilities), *super().match_key(left, right, tie_seed))

    def match(self, left, right, *, probabilities, use_cache=True, tie_seed=None):
        if self.settings.max_local_score is not None:
            raise ValueError("C*は上限なしの点の伝達")
        key = self.match_key(left, right, tie_seed, probabilities=probabilities)
        scope = getattr(self, '_stage2_scope', None)
        foundation = None
        if scope is not None:
            store, stats = scope
            stats['match_calls'] += 1
            if store is not None:
                # 元の照合が結果の控えにあっても、その入力の構造だけを残す。
                foundation, built = store.get(left, right)
                stats['foundation_builds' if built else 'foundation_hits'] += 1
        if use_cache and key in self.cache:
            if scope is not None:
                stats['result_cache_hits'] += 1
            return self.cache[key]
        rng = self.rng if tie_seed is None else random.Random(tie_seed)
        before = self._capture_rng_state() if tie_seed is None else {
            "policy": "call-seed-uniform-v1" if getattr(self, "tie_uniform", False) else "call-seed-v1", "seed": tie_seed}
        started = time.perf_counter()
        result = CstarEngine(left, right, self.settings, rng, probabilities,
                             tie_uniform=getattr(self, "tie_uniform", False), foundation=foundation).run()
        if scope is not None:
            stats['engine_calls'] += 1
            stats['engine_seconds'] += time.perf_counter() - started
        if use_cache:
            self.cache[key], self.cache_rng[key] = result, before
        return result

    def self_score(self, graph, *, tie_seed=None):
        # 自己の点は貪欲な照合で作らず、完全な自己対応を明示的に採点する。
        key = (VERSION, "structural-self", self.settings, graph.fingerprint())
        if key not in self.self_cache:
            self.self_cache[key] = structural_self_score(graph, self.settings).total
        return self.self_cache[key]


class CstarEngine(_Engine):
    def __init__(self, left, right, settings, rng, probabilities, *, tie_uniform=False, foundation=None):
        super().__init__(left, right, settings, rng, tie_uniform=tie_uniform)
        self.probabilities = {a: checked_distribution(dist) for a, dist in probabilities.items()}
        self.events = {}
        self.event_cache = {}
        self.foundation = foundation
        # 提示の見えている名は一つ。記憶のHと観察の未知を同一視しない。
        for n in right.nodes:
            if n.kind not in {"entity", "unknown"} and (n.state != "F" or len(n.names) != 1):
                raise ValueError("C*の提示に、観察名が一意でない行がある")

    def _grow(self, lk, rk, parent=False):
        key = (lk, rk, parent)
        if key in self.memo:
            return self.memo[key]
        if self.foundation is not None:
            return self._grow_from_foundation(lk, rk, parent)
        l, r = self.lb[lk], self.rb[rk]
        if l.kind == "entity" or r.kind == "entity":
            out = (self._add(Hypothesis(lk, rk, None, (), "entity", 0.0)),) if l.kind == r.kind else ()
            self.memo[key] = out
            return out
        unknown = "unknown" in {l.kind, r.kind}
        if not unknown and (l.kind != r.kind or len(l.args) != len(r.args)):
            self.memo[key] = ()
            return ()
        if unknown:
            event, local, kind = frozenset(), 0.0, "hidden"
        else:
            name = next(iter(r.names))
            if self.probabilities[lk].get(name, 0.0) <= 0:
                self.memo[key] = ()
                return ()
            if not parent and (l.ubiquitous or r.ubiquitous):
                self.memo[key] = ()
                return ()
            event, local, kind = frozenset({(lk, name)}), self.s.same_functor, "probability"
        children = [] if unknown else [self._grow(a, b, True) for a, b in zip(l.args, r.args, strict=True)]
        out = []
        for group in product(*children):
            j = self._add(Hypothesis(lk, rk, None, tuple(group), kind, local))
            self.events[j] = event.union(*(self.events[c] for c in group))
            if self._consistent(self.closures[j]):
                out.append(j)
        self.memo[key] = tuple(out)
        return tuple(out)

    def _grow_from_foundation(self, lk, rk, parent):
        # 仮説の番号・生成順は元の再帰と同じ。確率0による不採用は毎回判定する。
        plan = self.foundation.plan(lk, rk, parent)
        key = lk, rk, parent
        if plan.kind == 'invalid':
            self.memo[key] = ()
            return ()
        if plan.kind == 'entity':
            out = (self._add(Hypothesis(lk, rk, None, (), 'entity', 0.0)),)
            self.memo[key] = out
            return out
        if plan.kind == 'hidden':
            event, local = frozenset(), 0.0
        else:
            name = next(iter(self.rb[rk].names))
            if self.probabilities[lk].get(name, 0.0) <= 0:
                self.memo[key] = ()
                return ()
            event, local = frozenset({(lk, name)}), self.s.same_functor
        children = [self._grow(a, b, True) for a, b in plan.children]
        out = []
        for group in product(*children):
            j = self._add(Hypothesis(lk, rk, None, tuple(group), plan.kind, local))
            self.events[j] = event.union(*(self.events[c] for c in group))
            if plan.consistent:
                out.append(j)
        self.memo[key] = tuple(out)
        return tuple(out)

    def _add(self, h):
        i = super()._add(h)
        if h.kind == "entity":
            self.events[i] = frozenset()
        return i

    def _probability(self, events):
        if events not in self.event_cache:
            names = {}
            for seat, name in events:
                if seat in names and names[seat] != name:
                    self.event_cache[events] = 0.0
                    return 0.0
                names[seat] = name
            # 同じ席は一回。番号の付け替えで積の丸め順を変えない。
            self.event_cache[events] = math.prod(sorted(self.probabilities[a].get(name, 0.0)
                                                       for a, name in names.items()))
        return self.event_cache[events]

    def _scores(self, members, global_):
        terms = {i: [(self.mhs[i].local, self.events[i])] if self.mhs[i].local else [] for i in members}
        parents = {i: [] for i in members}
        for i in members:
            for child in self.mhs[i].children:
                if child in members:
                    parents[child].append(i)
        heights = {i: max(self.lh[self.mhs[i].left], self.rh[self.mhs[i].right]) for i in members}
        if self.tie_uniform:
            queue = [next(iter(v)) for v in self._ordered([frozenset({i}) for i in members],
                      lambda v: heights[next(iter(v))], "score-height")]
        else:
            queue = sorted(members, key=lambda i: (-heights[i], self._key(frozenset({i}))))

        def point(i):
            return math.fsum(coefficient * self._probability(events) for coefficient, events in terms[i])

        for child in queue:
            got = parents[child]
            if not global_ and self.s.block_most_out_of_mapping:
                ordered = self._ordered([frozenset({p}) for p in got],
                                        lambda p: point(next(iter(p))), "trickle-down")
                lb, rb, selected = set(), set(), []
                for p in ordered:
                    p = next(iter(p))
                    h = self.mhs[p]
                    if h.left not in lb and h.right not in rb:
                        selected.append(p)
                        lb.add(h.left)
                        rb.add(h.right)
                got = selected
            for parent in got:
                terms[child].extend((coefficient * self.s.trickle_down, events | self.events[child])
                                    for coefficient, events in terms[parent])
        return {i: point(i) for i in members}

    def run(self):
        result = super().run()
        candidates = []
        for candidate in result.candidates:
            local = {(h.left, h.right): h.local * self._probability(self.events[i])
                     for i in candidate.members for h in (self.mhs[i],)}
            breakdown = tuple((a, b, local[a, b], old_local + passed - local[a, b])
                              for a, b, old_local, passed in candidate.breakdown)
            candidates.append(replace(candidate, breakdown=breakdown))
        return replace(result, version=VERSION, candidates=tuple(candidates))


def validate(left, right, result):
    """候補の作り方と別の一対一・引数・点の検査。"""
    assert result.version == VERSION
    assert result.left_fingerprint == left.fingerprint()
    assert result.right_fingerprint == right.fingerprint()
    for candidate in result.candidates:
        pairs = candidate.relation_mapping + candidate.entity_mapping
        _checked_mapping(left, right, pairs)
        assert len(candidate.breakdown) == len(pairs)
        assert math.isclose(math.fsum(local + passed for _, _, local, passed in candidate.breakdown),
                            candidate.score, abs_tol=1e-12, rel_tol=1e-12)
        mapping = dict(pairs)
        lb, rb = left.by_id, right.by_id
        for a, b in pairs:
            x, y = lb[a], rb[b]
            if x.kind != "entity" and "unknown" not in {x.kind, y.kind}:
                assert tuple(mapping[arg] for arg in x.args) == y.args
    return True
