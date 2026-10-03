"""SME v4 の順つき式の照合部品。模型への接続前の部品検査用。

原典：公式配布 v4/mhs.lsp, se.lsp, greedy-merge.lsp, param.lsp。
F/H/U と観察できない位置の拡張：control/2026-10-03_SME版の仕様_Codex.md。
名前と ID は候補の順位に使わない。未知の位置の引数は作らない。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
import hashlib
import json
import math
import random

VERSION = "sme2017-ordered-component-1"


@dataclass(frozen=True)
class Settings:
    same_functor: float = 0.0005
    same_function: float = 0.0002
    trickle_down: float = 8.0
    max_local_score: float | None = None
    functor_trickle_down: bool = False
    greedy_cutoff: float = 0.8
    greedy_max: int = 3
    block_most_out_of_mapping: bool = True
    allow_out_of_mapping: bool = True
    less_greedy: bool = True
    fold_attributes: bool = True
    entity_supported_inferences: bool = True

    def __post_init__(self):
        # この部品では本番の既定設定と、原典の例で使う三係数を扱う。
        # 未実装の実験設定を黙って別の計算にしない。
        if self.functor_trickle_down or not self.allow_out_of_mapping:
            raise NotImplementedError("既定外の functor／kernel の点の設定は未接続")
        if not self.block_most_out_of_mapping:
            raise NotImplementedError("この部品の全体の点は対応内で計算する設定")


@dataclass(frozen=True)
class Node:
    key: str
    kind: str
    names: frozenset[str] = frozenset()
    args: tuple[str, ...] | None = ()
    state: str = "F"
    ubiquitous: bool = False

    def __post_init__(self):
        if self.kind not in {"entity", "relation", "function", "attribute", "unknown"}:
            raise ValueError(self.kind)
        if self.state not in {"F", "H", "U"}:
            raise ValueError(self.state)
        if self.kind == "unknown" and (self.names or self.args is not None):
            raise ValueError("未知の関係に名前や隠れた引数を入れない")
        if self.state == "U" and self.names:
            raise ValueError("U の名前は照合器に渡さない")
        if self.kind == "entity" and (self.names or self.args):
            raise ValueError("物の名前を照合の証拠にしない")
        if self.kind not in {"entity", "unknown"} and self.state == "F" and len(self.names) != 1:
            raise ValueError("F は固定名一つ")


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]

    def __post_init__(self):
        by = self.by_id
        if len(by) != len(self.nodes):
            raise ValueError("番号が重複")
        for n in self.nodes:
            if any(a not in by for a in n.args or ()):
                raise ValueError((n.key, "引数が未登録"))
        # 循環は原典の式の入力に含まれない。勝手に切って照合しない。
        self.heights()

    @property
    def by_id(self):
        return {n.key: n for n in self.nodes}

    def fingerprint(self):
        data = [(n.key, n.kind, sorted(n.names), n.args, n.state, n.ubiquitous)
                for n in sorted(self.nodes, key=lambda x: x.key)]
        return hashlib.sha256(json.dumps(data, separators=(",", ":")).encode()).hexdigest()

    def heights(self):
        by = self.by_id
        memo, active = {}, set()

        def visit(k):
            if k in active:
                raise ValueError("循環した式")
            if k not in memo:
                active.add(k)
                n = by[k]
                memo[k] = 0 if n.kind == "entity" else 1 + max((visit(a) for a in n.args or ()), default=0)
                active.remove(k)
            return memo[k]

        for k in by:
            visit(k)
        return memo


@dataclass(frozen=True)
class Hypothesis:
    left: str
    right: str
    name_pair: tuple[str, str] | None
    children: tuple[int, ...]
    kind: str
    local: float


@dataclass(frozen=True)
class Candidate:
    members: frozenset[int]
    score: float
    initial_score: float
    relation_mapping: tuple[tuple[str, str], ...]
    entity_mapping: tuple[tuple[str, str], ...]
    match_kinds: tuple[tuple[str, str, str], ...]
    breakdown: tuple[tuple[str, str, float, float], ...]
    inferences: tuple


@dataclass(frozen=True)
class Result:
    version: str
    settings: Settings
    left_fingerprint: str
    right_fingerprint: str
    candidates: tuple[Candidate, ...]
    selected: int | None
    tied: tuple[int, ...]
    choices: tuple
    hypotheses: tuple[Hypothesis, ...]

    @property
    def best(self):
        return None if self.selected is None else self.candidates[self.selected]


def _canonical(labels, edges):
    """名前を含まない色つき有向図の正準形。区別不能な色を個別化して全探索。

    順つき引数を辺の色で保つ。色の細分だけで同型と決めず、残った組を
    個別化する。ID は探索の順にだけ使い、最小の符号には含めない。
    """
    incoming = [[] for _ in labels]
    outgoing = [[] for _ in labels]
    for a, b, label in edges:
        outgoing[a].append((label, b))
        incoming[b].append((label, a))

    def ranks(values):
        values = [json.dumps(v, separators=(",", ":")) for v in values]
        table = {s: i for i, s in enumerate(sorted(set(values)))}
        return tuple(table[s] for s in values)

    def refine(colors):
        while True:
            nxt = ranks([(colors[i], sorted((p, colors[j]) for p, j in outgoing[i]),
                          sorted((p, colors[j]) for p, j in incoming[i])) for i in range(len(labels))])
            if len(set(nxt)) == len(set(colors)):
                return nxt
            colors = nxt

    @lru_cache(None)
    def search(colors):
        colors = refine(colors)
        cells = {}
        for i, c in enumerate(colors):
            cells.setdefault(c, []).append(i)
        ambiguous = [(len(v), c, v) for c, v in cells.items() if len(v) > 1]
        if not ambiguous:
            order = sorted(range(len(labels)), key=colors.__getitem__)
            pos = {v: i for i, v in enumerate(order)}
            return json.dumps(([labels[v] for v in order],
                               sorted((pos[a], pos[b], p) for a, b, p in edges)), separators=(",", ":"))
        _, _, cell = min(ambiguous)
        return min(search(tuple(max(colors) + 1 if j == i else c for j, c in enumerate(colors))) for i in cell)

    return search(ranks(labels))


class Matcher:
    """同点専用の乱数と状態別の控えを持つ。世界の乱数は受け取らない。"""

    def __init__(self, settings=Settings(), tie_seed=0):
        self.settings = settings
        self.rng = random.Random(tie_seed)
        self.cache = {}
        self.self_cache = {}
        self.cache_rng = {}

    def snapshot(self):
        return self.rng.getstate(), dict(self.cache), dict(self.self_cache), dict(self.cache_rng)

    def restore(self, snapshot):
        rng, cache, self_cache, cache_rng = snapshot
        self.rng.setstate(rng)
        self.cache = dict(cache)
        self.self_cache = dict(self_cache)
        self.cache_rng = dict(cache_rng)

    def match(self, left, right, *, use_cache=True):
        key = (VERSION, self.settings, left.fingerprint(), right.fingerprint())
        if use_cache and key in self.cache:
            return self.cache[key]
        rng_before = self.rng.getstate()
        engine = _Engine(left, right, self.settings, self.rng)
        result = engine.run()
        if use_cache:
            self.cache[key] = result
            self.cache_rng[key] = rng_before
        return result

    def self_score(self, graph):
        key = (VERSION, self.settings, graph.fingerprint())
        if key not in self.self_cache:
            result = self.match(graph, graph)
            self.self_cache[key] = result.best.score if result.best else 0.0
        return self.self_cache[key]


class _Engine:
    def __init__(self, left, right, settings, rng):
        self.left, self.right, self.s, self.rng = left, right, settings, rng
        self.lb, self.rb = left.by_id, right.by_id
        self.lh, self.rh = left.heights(), right.heights()
        self.mhs, self.index, self.memo, self.closures = [], {}, {}, {}
        self.choices = []
        self.key_cache = {}

    def _key(self, members):
        if members in self.key_cache:
            return self.key_cache[members]
        labels, edges, ids, lexical = [], [], {}, {}
        for side, graph in enumerate((self.left, self.right)):
            for n in graph.nodes:
                ids[side, n.key] = len(labels)
                labels.append((side, n.kind, n.state, len(n.names), len(n.args) if n.args is not None else -1))
            for n in graph.nodes:
                for p, a in enumerate(n.args or ()):
                    edges.append((ids[side, n.key], ids[side, a], f"arg{p}"))
                for name in n.names:
                    if name not in lexical:
                        lexical[name] = len(labels)
                        labels.append((2, "name"))
                    edges.append((ids[side, n.key], lexical[name], "allows"))
        for i in members:
            h = self.mhs[i]
            edges.append((ids[0, h.left], ids[1, h.right], h.kind))
            if h.name_pair:
                v = len(labels)
                labels.append((3, "functor-match"))
                edges.extend(((v, lexical[h.name_pair[0]], "base"), (v, lexical[h.name_pair[1]], "target")))
        value = _canonical(labels, edges)
        self.key_cache[members] = value
        return value

    def _ordered(self, values, scorer, phase):
        by_score = {}
        for value in set(values):
            by_score.setdefault(-scorer(value), []).append(value)
        groups = {}
        for score, values_at_score in by_score.items():
            # 点だけで順が決まるものには、構造の同点の鍵を作らない。
            if len(values_at_score) == 1 and math.isfinite(score):
                groups[score, ()] = values_at_score
            else:
                for value in values_at_score:
                    groups.setdefault((score, self._key(value)), []).append(value)
        out = []
        for rank in sorted(groups):
            tied = groups[rank]
            # 構造でも区別不能な集合だけ専用乱数で一様な順列にする。
            if len(tied) > 1:
                tied.sort(key=lambda v: tuple(sorted((self.mhs[i].left, self.mhs[i].right,
                                                     self.mhs[i].name_pair or ()) for i in v)))
                self.rng.shuffle(tied)
                self.choices.append((phase, tuple(tuple(sorted(v)) for v in tied)))
            out.extend(tied)
        return out

    def _consistent(self, members):
        lm, rm, lf, rf, variants = {}, {}, {}, {}, {}
        for i in members:
            h = self.mhs[i]
            if h.left in lm and lm[h.left] != h.right or h.right in rm and rm[h.right] != h.left:
                return False
            if (h.left, h.right) in variants and variants[h.left, h.right] != i:
                return False
            lm[h.left], rm[h.right], variants[h.left, h.right] = h.right, h.left, i
            if h.name_pair:
                a, b = h.name_pair
                if a in lf and lf[a] != b or b in rf and rf[b] != a:
                    return False
                lf[a], rf[b] = b, a
        return True

    def _add(self, h):
        if h in self.index:
            return self.index[h]
        i = len(self.mhs)
        self.mhs.append(h)
        self.index[h] = i
        self.closures[i] = frozenset({i}).union(*(self.closures[j] for j in h.children))
        return i

    def _grow(self, lk, rk, parent=False):
        key = (lk, rk, parent)
        if key in self.memo:
            return self.memo[key]
        l, r = self.lb[lk], self.rb[rk]
        if l.kind == "entity" or r.kind == "entity":
            out = (self._add(Hypothesis(lk, rk, None, (), "entity", 0.0)),) if l.kind == r.kind else ()
            self.memo[key] = out
            return out
        unknown = l.kind == "unknown" or r.kind == "unknown"
        structural = unknown or l.state == "U" or r.state == "U"
        if not unknown and l.kind != r.kind:
            self.memo[key] = ()
            return ()
        if l.args is not None and r.args is not None and len(l.args) != len(r.args):
            self.memo[key] = ()
            return ()
        common = l.names & r.names
        if structural:
            names, local, kind = (None,), 0.0, "hidden" if unknown else "structure"
        elif common:
            if not parent and (l.ubiquitous or r.ubiquitous):
                self.memo[key] = ()
                return ()
            names, local, kind = tuple((p, p) for p in common), self.s.same_functor, "name"
        elif parent and l.kind == r.kind == "function":
            names, local, kind = tuple(product(l.names, r.names)), self.s.same_function, "function"
        else:
            self.memo[key] = ()
            return ()
        children = [self._grow(a, b, True) for a, b in zip(l.args or (), r.args or ())] if not unknown else []
        out = []
        for name_pair in names:
            for child_group in product(*children):
                h = Hypothesis(lk, rk, name_pair, tuple(child_group), kind, local)
                # 不整合な親は作らない。名前のある子は独立に候補になれる。
                j = self._add(h)
                if self._consistent(self.closures[j]):
                    out.append(j)
        self.memo[key] = tuple(out)
        return tuple(out)

    def _scores(self, members, global_):
        scores = {i: self.mhs[i].local for i in members}
        parents = {i: [] for i in members}
        for i in members:
            for child in self.mhs[i].children:
                if child in members:
                    parents[child].append(i)
        heights = {i: max(self.lh[self.mhs[i].left], self.rh[self.mhs[i].right]) for i in members}
        if any(heights[parent] <= heights[child] for child, got in parents.items() for parent in got):
            # 高さが親から子へ減らない入力には、元の順をそのまま使う。
            queue = sorted(members, key=lambda i: (-heights[i], self._key(frozenset({i}))))
        else:
            queue = []
            for height in sorted(set(heights.values()), reverse=True):
                at_height = [i for i in members if heights[i] == height]
                # 同じ高さは点を渡し合わない。親が複数あるものの相対順だけは
                # 同点の乱数の順を保つため、従来の構造の鍵で並べる。
                uses_order = lambda i: not global_ and self.s.block_most_out_of_mapping and len(parents[i]) > 1
                queue.extend(i for i in at_height if not uses_order(i))
                queue.extend(sorted((i for i in at_height if uses_order(i)),
                                    key=lambda i: self._key(frozenset({i}))))
        for child in queue:
            got = parents[child]
            if not global_ and self.s.block_most_out_of_mapping:
                ordered = self._ordered([frozenset({p}) for p in got],
                                        lambda p: scores[next(iter(p))], "trickle-down")
                lb, rb, selected = set(), set(), []
                for p in ordered:
                    p = next(iter(p))
                    h = self.mhs[p]
                    if h.left not in lb and h.right not in rb:
                        selected.append(p)
                        lb.add(h.left)
                        rb.add(h.right)
                got = selected
            score = scores[child] + self.s.trickle_down * math.fsum(scores[p] for p in got)
            scores[child] = min(score, self.s.max_local_score) if self.s.max_local_score is not None else score
        return scores

    def _cream(self, candidates, cutoff, limit):
        scorer = lambda c: math.fsum(self.initial[i] for i in c)
        remaining = self._ordered(candidates, scorer, "greedy-merge")
        used, solutions, best = [], [], -1.0
        while remaining and limit > 0:
            solution, rest, taken = remaining[0], [], [remaining[0]]
            for c in remaining[1:]:
                if self._consistent(solution | c):
                    solution |= c
                    taken.append(c)
                else:
                    rest.append(c)
            if self.s.less_greedy:
                for c in used:
                    if self._consistent(solution | c):
                        solution |= c
            used.extend(taken)
            value = scorer(solution)
            if value < cutoff * best:
                break
            best = max(best, value)
            solutions.append(solution)
            remaining = rest
            limit -= 1
        return [c for c in set(solutions) if scorer(c) >= cutoff * best]

    def _roots(self, k):
        parents = {a: set() for a in self.lb}
        for n in self.left.nodes:
            for a in n.args or ():
                parents[a].add(n.key)
        found = set()

        def ascend(x):
            if not parents[x]:
                found.add(x)
            for p in parents[x]:
                ascend(p)

        ascend(k)
        return found

    def _inferences(self, members):
        mapping = {self.mhs[i].left: self.mhs[i].right for i in members}
        parents = {a for n in self.left.nodes for a in n.args or ()}
        roots = [n for n in self.left.nodes if n.kind != "entity" and n.key not in parents and n.key not in mapping]
        out = []
        for n in roots:
            seen = set()

            def visit(k):
                seen.add(k)
                for a in self.lb[k].args or ():
                    if a not in seen:
                        visit(a)

            visit(n.key)
            support = seen & set(mapping)
            if not self.s.entity_supported_inferences:
                support = {k for k in support if self.lb[k].kind != "entity"}
            if support:
                def project(k):
                    if k in mapping:
                        return ("mapped", mapping[k])
                    v = self.lb[k]
                    if v.kind == "entity":
                        return ("skolem", k)
                    return (v.kind, tuple(sorted(v.names)), tuple(project(a) for a in v.args or ()))
                out.append((n.key, project(n.key)))
        return tuple(sorted(out))

    def run(self):
        seeds = []
        for l in self.left.nodes:
            if l.kind == "entity":
                continue
            for r in self.right.nodes:
                if r.kind != "entity":
                    seeds.extend(self._grow(l.key, r.key))
        good = set().union(*(self.closures[i] for i in seeds)) if seeds else set()
        self.initial = self._scores(good, False)
        children = {c for i in good for c in self.mhs[i].children}
        kernels = [self.closures[i] for i in good - children
                   if any(self.mhs[j].local > 0.0 for j in self.closures[i])]
        # 共有する基の根ごとの第一段、次に全体の第二段。
        attributes, regular = [], []
        for c in set(kernels):
            if all(self.lb[self.mhs[i].left].kind in {"attribute", "entity"} for i in c):
                attributes.append(c)
            else:
                regular.append(c)
        if self.s.fold_attributes:
            folded = []
            for c in regular:
                entities = {(self.mhs[i].left, self.mhs[i].right) for i in c if self.lb[self.mhs[i].left].kind == "entity"}
                for a in attributes:
                    ae = {(self.mhs[i].left, self.mhs[i].right) for i in a if self.lb[self.mhs[i].left].kind == "entity"}
                    if entities & ae and self._consistent(c | a):
                        c |= a
                folded.append(c)
            kernels = folded + attributes
        partitions = {}
        for c in set(kernels):
            root_mhs = c - {j for i in c for j in self.mhs[i].children}
            roots = set().union(*(self._roots(self.mhs[i].left) for i in root_mhs))
            for r in roots:
                partitions.setdefault(r, []).append(c)
        merged = set()
        for candidates in partitions.values():
            merged.update(self._cream(candidates, 0.0, len(candidates)))
        globals_ = self._cream(merged, self.s.greedy_cutoff, self.s.greedy_max)
        globals_ = self._ordered(globals_, lambda c: math.fsum(self._scores(c, True).values()), "final")
        candidates = []
        for c in globals_:
            scores = self._scores(c, True)
            rm, em, kinds, breakdown = [], [], [], []
            for i in c:
                h = self.mhs[i]
                (em if self.lb[h.left].kind == "entity" else rm).append((h.left, h.right))
                kinds.append((h.left, h.right, h.kind))
                breakdown.append((h.left, h.right, h.local, scores[i] - h.local))
            candidates.append(Candidate(c, math.fsum(scores.values()), math.fsum(self.initial[i] for i in c),
                                        tuple(sorted(rm)), tuple(sorted(em)), tuple(sorted(kinds)),
                                        tuple(sorted(breakdown)), self._inferences(c)))
        tied = ()
        if candidates:
            at_best_score = tuple(i for i, c in enumerate(candidates) if c.score == candidates[0].score)
            if len(at_best_score) <= 1:
                tied = at_best_score
            else:
                best_key = self._key(globals_[0])
                tied = tuple(i for i in at_best_score if self._key(candidates[i].members) == best_key)
        return Result(VERSION, self.s, self.left.fingerprint(), self.right.fingerprint(), tuple(candidates),
                      0 if candidates else None, tied, tuple(self.choices), tuple(self.mhs))


def validate(left, right, result):
    """照合の候補を作る関数を使わず、採用した全引数と点の重複を検査する。"""
    assert result.version == VERSION
    assert result.left_fingerprint == left.fingerprint()
    assert result.right_fingerprint == right.fingerprint()
    lb, rb = left.by_id, right.by_id
    for c in result.candidates:
        pairs = c.relation_mapping + c.entity_mapping
        lm = dict(pairs)
        assert len(lm) == len(pairs)
        assert len(set(lm.values())) == len(lm)
        assert len(c.breakdown) == len(lm), "席を二重に数えた"
        assert math.isclose(math.fsum(local + td for _, _, local, td in c.breakdown), c.score, abs_tol=1e-14)
        for l, r in pairs:
            a, b = lb[l], rb[r]
            if a.kind == "entity" or b.kind == "entity":
                assert a.kind == b.kind == "entity"
                continue
            if a.kind == "unknown" or b.kind == "unknown":
                continue
            assert len(a.args) == len(b.args)
            assert tuple(lm[x] for x in a.args) == b.args, (l, r, "順つき引数が不整合")
        kinds = {(l, r): k for l, r, k in c.match_kinds}
        for l, r, local, td in c.breakdown:
            if kinds[l, r] == "name":
                assert lb[l].names & rb[r].names
                assert local == result.settings.same_functor, "H の名前を二重に数えた"
            if lb[l].state == "U" or rb[r].state == "U" or "unknown" in {lb[l].kind, rb[r].kind}:
                assert local == 0.0
    return True
