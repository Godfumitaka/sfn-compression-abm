"""Specifications-only reference for commissions 41--42^5 and attention inbox 2.

Written by the decoration reviewer before reading the new model implementation.
Only the unchanged 10cd8bd tools/sme2017.py is imported as the ordinary scorer.
This is an audit tool, not model code. It uses exhaustive name cases and fresh
matching. Large inputs may be prohibitively slow; it never silently fixes a
mapping, freezes attention mismatches, samples cases, or clips negative values.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import importlib.util
import itertools
import math
from pathlib import Path
import random
import sys
from typing import Callable


def load_ordinary(path: str | Path):
    """Load exactly the independently recorded ordinary SME file."""
    spec = importlib.util.spec_from_file_location("shop_audit_ordinary_sme", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def distribution(values) -> tuple[tuple[str, float], ...]:
    items = tuple((str(k), float(v)) for k, v in values.items())
    if any(not math.isfinite(v) or v < 0 for _, v in items):
        raise ValueError("invalid probability")
    if not math.isclose(math.fsum(v for _, v in items), 1.0, abs_tol=1e-12):
        raise ValueError("distribution must already be normalized")
    return items


@dataclass(frozen=True)
class Seat:
    key: str
    kind: str
    args: tuple[str, ...] | None
    state: str = "F"
    fixed: str | None = None
    counts: tuple[tuple[str, float], ...] = ()
    background: tuple[tuple[str, float], ...] = ()
    ubiquitous: bool = False

    def probabilities(self, eps=.01, alpha=1.0, *, matching="shared"):
        if self.kind in {"entity", "unknown"}:
            raise ValueError("entities/hidden positions do not draw names")
        b = dict(self.background)
        distribution(b)
        if self.state not in {"F", "H", "U"} or not 0 <= eps < 1:
            raise ValueError("state/epsilon")
        if matching not in {"shared", "0"}:
            raise ValueError("matching epsilon policy")
        if self.state == "U" or self.state == "F" and self.fixed is None:
            return b
        names = set(b) | set(dict(self.counts))
        if self.fixed is not None:
            names.add(self.fixed)
        if self.state == "F":
            q = {n: float(n == self.fixed) for n in names}
        else:
            if alpha != 1.0 or any(v < 0 for _, v in self.counts):
                raise ValueError("the authorized Dirichlet alpha is 1")
            counts = dict(self.counts)
            total = math.fsum(counts.values())
            q = {n: (counts.get(n, 0.0) + alpha*b.get(n, 0.0))/(total+alpha)
                 for n in names}
        if matching == "0":
            return q
        return {n: (1-eps)*q.get(n, 0.0) + eps*b.get(n, 0.0) for n in names}

    def thin(self):
        if self.kind in {"entity", "unknown"} or self.state == "U":
            raise ValueError("not an eligible F/H seat")
        return replace(self, state="H" if self.state == "F" else "U")


@dataclass(frozen=True)
class Definition:
    key: str
    seats: tuple[Seat, ...]
    # Eligibility is supplied by the learner record, never reconstructed from
    # researcher truth. None is deliberately not a production default.
    gate_eligible: frozenset[str]

    def thin(self, key):
        if sum(s.key == key for s in self.seats) != 1:
            raise ValueError("seat key")
        return replace(self, seats=tuple(s.thin() if s.key == key else s for s in self.seats))

    def graph(self, sme):
        nodes = []
        for s in self.seats:
            names = (frozenset() if s.kind in {"entity", "unknown"} or s.state == "U"
                     else frozenset({s.fixed}) if s.state == "F" and s.fixed is not None
                     else frozenset(n for n, c in s.counts if c > 0))
            state = "U" if s.state == "F" and s.fixed is None else s.state
            nodes.append(sme.Node(s.key, s.kind, names, s.args, state, s.ubiquitous))
        return sme.Graph(tuple(nodes))


def _fixed_engine(sme, left, right, mapping, settings=None):
    """Build an explicit ordered M; do not search for a self-mapping."""
    engine = sme._Engine(left, right, settings or sme.Settings(), random.Random(0))
    lb, rb = left.by_id, right.by_id
    mapping = dict(mapping)
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("M is not one-to-one")
    built, active = {}, set()

    def add(lk):
        if lk in built:
            return built[lk]
        if lk in active:
            raise ValueError("cyclic mapping")
        active.add(lk)
        rk = mapping[lk]
        l, r = lb[lk], rb[rk]
        if l.kind == "entity" or r.kind == "entity":
            if l.kind != r.kind:
                raise ValueError("entity mapped to a seat")
            children, kind, local = (), "entity", 0.0
        elif l.kind == "unknown" or r.kind == "unknown":
            # No imagined hidden arguments; no name local score.
            children, kind, local = (), "hidden", 0.0
        else:
            if l.kind != r.kind or len(l.args) != len(r.args):
                raise ValueError("shape/ordered arity mismatch")
            for la, ra in zip(l.args, r.args):
                if mapping.get(la) != ra:
                    raise ValueError("M does not include parallel arguments")
            children = tuple(add(a) for a in l.args)
            kind, local = "name", engine.s.same_functor
        index = engine._add(sme.Hypothesis(lk, rk, None, children, kind, local))
        built[lk] = index
        active.remove(lk)
        return index

    for lk in mapping:
        add(lk)
    return engine, built


def _prune(engine, members):
    """Parallel connectivity: repeatedly remove a parent with a missing child."""
    members = set(members)
    while True:
        removed = {i for i in members if any(c not in members for c in engine.mhs[i].children)}
        if not removed:
            return frozenset(members)
        members -= removed


def fixed_mapping_score(sme, left, right, mapping, q, *, settings=None, details=False):
    """Enumerate independent match/nonmatch events for a consistent fixed M.

    Every non-hidden relation pair needs one probability in q, including U.
    Entities and hidden positions need none. Shared children have one MH/event.
    All surviving cases are scored with the unchanged ordinary _scores method.
    """
    engine, built = _fixed_engine(sme, left, right, mapping, settings)
    events = []
    for lk, i in built.items():
        if engine.mhs[i].kind in {"entity", "hidden"}:
            continue
        p = float(q[lk])
        if not 0 <= p <= 1:
            raise ValueError("q outside [0,1]")
        events.append((i, p))
    base = frozenset(built.values())
    totals, rows = [], []
    for case in itertools.product((False, True), repeat=len(events)):
        weight = math.prod(p if on else 1-p for on, (_, p) in zip(case, events))
        if weight == 0:
            continue
        alive = _prune(engine, base - {i for on, (i, _) in zip(case, events) if not on})
        # Explicitly call the ordinary scorer. No expected-local shortcut.
        score = math.fsum(sme._Engine._scores(engine, alive, True).values())
        totals.append(weight*score)
        if details:
            rows.append({"on": list(case), "weight": weight, "score": score,
                         "surviving": [engine.mhs[i].left for i in sorted(alive)]})
    value = math.fsum(totals)
    return (value, rows) if details else value


def self_structure_score(sme, graph, *, settings=None):
    mapping = {n.key: n.key for n in graph.nodes}
    engine, built = _fixed_engine(sme, graph, graph, mapping, settings)
    return math.fsum(sme._Engine._scores(engine, frozenset(built.values()), True).values())


def expected_match(sme, definition, scene, *, eps=.01, matching="shared", tie_seed=0,
                   settings=None):
    """Fresh ordinary SME greedy pipeline with exhaustive expected scores.

    The ordinary kernel/merge/top-3/cutoff machinery is reused unchanged. The
    q>0 pairs and expected-score integration are independently written here.
    Initial (possibly incompatible) hypotheses sharing one left seat use one
    categorical name draw, NOT independent Bernoulli draws per competing MH.
    Observed scene relation names must be singletons; this is a prediction
    oracle. E-to-E uncertain-name matching requires a separate record adapter.
    """
    left = definition.graph(sme)
    probs = {s.key: s.probabilities(eps, matching=matching) for s in definition.seats
             if s.kind not in {"entity", "unknown"}}
    for n in scene.nodes:
        if n.kind not in {"entity", "unknown"} and len(n.names) != 1:
            raise ValueError("prediction scene must contain observed singleton names")

    class Exhaustive(sme._Engine):
        def _grow(self, lk, rk, parent=False):
            key = lk, rk, parent
            if key in self.memo:
                return self.memo[key]
            l, r = self.lb[lk], self.rb[rk]
            if l.kind == "entity" or r.kind == "entity":
                out = ((self._add(sme.Hypothesis(lk, rk, None, (), "entity", 0.0)),)
                       if l.kind == r.kind else ())
            elif l.kind == "unknown" or r.kind == "unknown":
                out = (self._add(sme.Hypothesis(lk, rk, None, (), "hidden", 0.0)),)
            elif l.kind != r.kind or len(l.args) != len(r.args):
                out = ()
            elif probs[lk].get(next(iter(r.names)), 0.0) <= 0:
                out = ()
            elif not parent and (l.ubiquitous or r.ubiquitous):
                out = ()
            else:
                children = [self._grow(a, b, True) for a, b in zip(l.args, r.args)]
                got = []
                for group in itertools.product(*children):
                    i = self._add(sme.Hypothesis(lk, rk, None, tuple(group), "name", self.s.same_functor))
                    if self._consistent(self.closures[i]):
                        got.append(i)
                out = tuple(got)
            self.memo[key] = out
            return out

        def _scores(self, members, global_):
            members = frozenset(members)
            # Integrate one categorical variable per latent seat. Aggregate
            # untested names into one OTHER event without changing the mean.
            wanted = {}
            for i in members:
                h = self.mhs[i]
                if h.kind == "name":
                    wanted.setdefault(h.left, set()).add(next(iter(self.rb[h.right].names)))
            cases = []
            for lk, names in wanted.items():
                options = [(n, probs[lk].get(n, 0.0)) for n in names]
                other = 1-math.fsum(p for _, p in options)
                if other < -1e-12:
                    raise ValueError("invalid categorical draw")
                options.append((None, max(0.0, other)))
                cases.append((lk, [(n, p) for n, p in options if p > 0]))
            parts = {i: [] for i in members}
            tie_state = self.rng.getstate()
            for assignment in itertools.product(*(options for _, options in cases)):
                draws = {lk: value[0] for (lk, _), value in zip(cases, assignment)}
                weight = math.prod(value[1] for value in assignment)
                alive = _prune(self, {i for i in members if self.mhs[i].kind != "name"
                                      or draws[self.mhs[i].left] == next(iter(self.rb[self.mhs[i].right].names))})
                # Case scoring uses a private RNG, with the same frozen tie
                # state in every case. Never advances the production stream.
                oracle = sme._Engine(self.left, self.right, self.s, random.Random())
                oracle.rng.setstate(tie_state)
                oracle.mhs = self.mhs
                scores = sme._Engine._scores(oracle, alive, global_)
                for i, score in scores.items():
                    parts[i].append(weight*score)
            return {i: math.fsum(parts[i]) for i in members}

    engine = Exhaustive(left, scene, settings or sme.Settings(), random.Random(tie_seed))
    result = engine.run()
    return result, engine


def mismatch(observed: str, p, background, *, eps=.01):
    if not 0 < eps < 1:
        raise ValueError("attention normalization needs epsilon in (0,1)")
    px, bx = p.get(observed, 0.0), background.get(observed, 0.0)
    if px <= 0 or bx <= 0:
        raise ValueError("m has no finite formula at zero P or zero baseline; report it")
    return math.log(bx/px)/(-math.log(eps))


def average_distributions(distributions):
    if not distributions:
        raise ValueError("no distributions")
    names = set().union(*(p for p in distributions))
    return {n: math.fsum(p.get(n, 0.0) for p in distributions)/len(distributions) for n in names}


@dataclass(frozen=True)
class Candidate:
    definition: str
    q: float
    gate: bool
    answer: tuple[tuple[str, float], ...]
    # Every visible position is listed, including m=0 for unmapped positions.
    positions: tuple[tuple[str, str, float], ...]  # position ID, shared k2 key, m
    utterance: str | None
    target_case: str

    def z(self, attention):
        return (-math.inf if self.q <= 0 else
                math.log(self.q) - math.fsum(attention.get(key, 0.0)*m for _, key, m in self.positions))


@dataclass(frozen=True)
class Prediction:
    selected: str | None
    distribution: tuple[tuple[str, float], ...]
    utterance: str | None
    candidates: tuple[Candidate, ...]
    logits: tuple[tuple[str, float], ...]
    mixture: tuple[tuple[str, float], ...]
    target_case: str


def select(candidates, attention, fallback, *, tie_choice=0):
    """Gate, rank all definitions and keep the top1 and mixture distributions.

    Existing tie/utterance policies are inputs from the learner record adapter;
    this function never sorts IDs/names to invent a tie rule. tie_choice is a
    saved draw into the ordered tied candidate list supplied by that adapter.
    """
    candidates = tuple(candidates)
    logits = tuple((c.definition, c.z(attention)) for c in candidates)
    available = [(c, z) for c, (_, z) in zip(candidates, logits) if c.gate and math.isfinite(z)]
    if not available:
        b = distribution(fallback)
        return Prediction(None, b, None, candidates, logits, b, "global_fallback")
    best = max(z for _, z in available)
    tied = [c for c, z in available if z == best]
    chosen = tied[tie_choice % len(tied)]
    exponents = [math.exp(z-best) for _, z in available]
    total = math.fsum(exponents)
    names = set().union(*(dict(c.answer) for c, _ in available))
    mix = {n: math.fsum(w*dict(c.answer).get(n, 0.0)
                        for (c, _), w in zip(available, exponents))/total for n in names}
    return Prediction(chosen.definition, chosen.answer, chosen.utterance, candidates, logits,
                      distribution(mix), chosen.target_case)


def loss(prediction, y, fallback_length: Callable[[str], float], *, arm="top1"):
    if arm == "alpha":
        return 0.0 if prediction.utterance == y else fallback_length(y)
    if arm not in {"top1", "mixture"}:
        raise ValueError("loss arm")
    p = dict(prediction.distribution if arm == "top1" else prediction.mixture).get(y, 0.0)
    return -math.log2(p) if p > 0 else fallback_length(y)


@dataclass(frozen=True)
class FrozenState:
    memory: tuple[Definition, ...]
    attention: tuple[tuple[str, float], ...]
    global_background: tuple[tuple[str, float], ...]
    pre_time: int
    usage: tuple[tuple[str, int], ...] = ()
    tie_seed: int = 0


def marginal_values(state, public_question, disclosed_y, predictor, fallback_length,
                    *, arm="top1", scope="all"):
    """Every intervention starts from the frozen pretrial snapshot.

    predictor receives NO disclosed answer. It must return a freshly matched
    Prediction for every definition, including those outside the gate. No
    fixed mapping cache is accepted by this interface.
    """
    if scope not in {"all", "chosen"}:
        raise ValueError("scope")
    before = predictor(state, public_question)
    base_loss = loss(before, disclosed_y, fallback_length, arm=arm)
    rows = []
    for di, definition in enumerate(state.memory):
        if scope == "chosen" and definition.key != before.selected:
            continue
        for seat in definition.seats:
            if seat.kind in {"entity", "unknown"} or seat.state == "U":
                continue
            memory = list(state.memory)
            memory[di] = definition.thin(seat.key)
            after_state = replace(state, memory=tuple(memory))
            after = predictor(after_state, public_question)
            new_loss = loss(after, disclosed_y, fallback_length, arm=arm)
            rows.append({"definition": definition.key, "seat": seat.key,
                         "before_loss": base_loss, "after_loss": new_loss,
                         "delta": new_loss-base_loss, "before_selected": before.selected,
                         "after_selected": after.selected,
                         "before_target_case": before.target_case,
                         "after_target_case": after.target_case,
                         "before_utterance": before.utterance, "after_utterance": after.utterance})
    return rows


def provisional_definition(template, first_observed):
    """first_observed is learner-visible/revealed material one ONLY."""
    seats = []
    for s in template.seats:
        if s.kind in {"entity", "unknown"}:
            seats.append(s)
            continue
        name = first_observed.get(s.key)
        seats.append(replace(s, fixed=name if s.state == "F" else None,
                             counts=((name, 1.0),) if name is not None else ()))
    return replace(template, seats=tuple(seats))


def birth_values(state, template, first_observed, visible_second, question_factory,
                 predictor, fallback_length, question_type_counts, disclosed_door_names,
                 *, arm="top1", decay_weight=1.0):
    """42\u2033: each visible second-material relation supplies a fake question.

    visible_second is (public relation ID, observed name) pairs. question_factory
    constructs the same public hidden-placeholder format as real questions,
    without copying hidden arguments. Geometry/visibility is an explicit record
    adapter boundary, not inferred from researcher scene/type metadata.
    """
    provisional = provisional_definition(template, first_observed)
    if provisional.key in {d.key for d in state.memory}:
        raise ValueError("new definition key already present")
    combined = replace(state, memory=state.memory+(provisional,))
    visible_second = tuple(visible_second)
    if not visible_second:
        return {"values": {}, "questions": [], "missing_type_weight": 1.0}
    types = {rid: "door" if name in disclosed_door_names else "non_door"
             for rid, name in visible_second}
    total_history = sum(question_type_counts.values())
    counts = {t: sum(types[rid] == t for rid, _ in visible_second) for t in ("door", "non_door")}
    weights = {rid: (1/len(visible_second) if total_history == 0 else
                     question_type_counts.get(types[rid], 0)/total_history/counts[types[rid]])
               for rid, _ in visible_second}
    # Preserve missing mass if an historically asked type has no visible fake
    # question. Never silently renormalize the other type.
    missing = 1-math.fsum(weights.values())
    accum = {s.key: [] for s in provisional.seats if s.kind not in {"entity", "unknown"} and s.state != "U"}
    questions = []
    for rid, y in visible_second:
        question = question_factory(rid)
        rows = marginal_values(combined, question, y, predictor, fallback_length, arm=arm)
        own = [r for r in rows if r["definition"] == provisional.key]
        for row in own:
            accum[row["seat"]].append(weights[rid]*row["delta"]*decay_weight)
        questions.append({"visible_relation": rid, "type": types[rid], "weight": weights[rid], "rows": own})
    return {"values": {key: math.fsum(parts) for key, parts in accum.items()},
            "questions": questions, "missing_type_weight": missing}


def attention_gradient(prediction, y):
    """Derivative of natural-log mixture loss; retention uses bits separately."""
    available = [(c, z) for c, (_, z) in zip(prediction.candidates, prediction.logits)
                 if c.gate and math.isfinite(z)]
    if not available:
        return {}
    best = max(z for _, z in available)
    weights = [math.exp(z-best) for _, z in available]
    norm = math.fsum(weights)
    weights = [w/norm for w in weights]
    py = dict(prediction.mixture).get(y, 0.0)
    if py <= 0:
        raise ValueError("zero mixture probability: no finite logarithmic gradient")
    parts = {}
    for (c, _), w in zip(available, weights):
        factor = w*(dict(c.answer).get(y, 0.0)/py-1)
        for _, key, m in c.positions:
            parts.setdefault(key, []).append(factor*m)
    return {key: math.fsum(values) for key, values in parts.items()}


def update_attention(attention, gradient, *, disclosed, eta=.1):
    if not disclosed:
        return dict(attention)
    return {key: min(10.0, max(0.0, attention.get(key, 0.0)-eta*gradient.get(key, 0.0)))
            for key in set(attention) | set(gradient)}


def fresh_candidate(sme, definition, scene, target, position_keys, fallback,
                    *, eps=.01, matching="shared", threshold=0.0, empty_gate_ratio=None,
                    tie_seed=0, answer_resolver=None):
    """Build Q, support gate, m and target P anew for one definition.

    Production adapters must supply eligible seats, empty-gate policy, actual
    target resolver, keys, and saved tie policy. The direct-target resolver is
    useful for explicit small graphs; it does not invent missing structure.
    """
    result, engine = expected_match(sme, definition, scene, eps=eps, matching=matching,
                                    tie_seed=tie_seed)
    left = definition.graph(sme)
    denom = self_structure_score(sme, left)+self_structure_score(sme, scene)
    q = 2*result.best.score/denom if result.best and denom > 0 else 0.0
    mapping = dict(result.best.relation_mapping) if result.best else {}
    reverse = {right: left for left, right in mapping.items()}
    seats = {s.key: s for s in definition.seats}
    observed = {n.key: next(iter(n.names)) for n in scene.nodes
                if n.kind not in {"entity", "unknown"}}
    eligible = [seats[k] for k in definition.gate_eligible
                if seats[k].state in {"F", "H"} and seats[k].kind not in {"entity", "unknown"}]
    supported = 0
    for s in eligible:
        name = observed.get(mapping.get(s.key))
        if name is not None and (s.state == "F" and name == s.fixed or
                                 s.state == "H" and dict(s.counts).get(name, 0) > 0):
            supported += 1
    if not eligible and empty_gate_ratio is None:
        raise ValueError("empty F/H gate policy must come from the old record definition")
    ratio = supported/len(eligible) if eligible else empty_gate_ratio
    positions = []
    for rid, name in observed.items():
        if rid == target:
            raise ValueError("hidden target exposed to attention")
        key, baseline = position_keys[rid]
        mapped = seats.get(reverse.get(rid))
        p = mapped.probabilities(eps) if mapped is not None else dict(baseline)
        positions.append((rid, key, mismatch(name, p, dict(baseline), eps=eps)))
    if answer_resolver is None:
        candidates = [reverse[target]] if target in reverse else []
    else:
        candidates = answer_resolver(definition, scene, result, target)
    distributions = [seats[k].probabilities(eps) for k in candidates]
    answer = average_distributions(distributions) if distributions else dict(fallback)
    target_case = ("multiple_seats" if len(distributions) > 1 else "one_seat"
                   if distributions else "global_fallback")
    maximum = max(answer.values())
    modes = [n for n, p in answer.items() if p == maximum]
    # Fixture utterance policy: same-seat mode tie abstains. The production
    # replay supplies the existing answer/tie policy in its adapter.
    utterance = modes[0] if len(modes) == 1 and distributions else None
    return Candidate(definition.key, q, ratio >= threshold, distribution(answer),
                     tuple(positions), utterance, target_case), result
