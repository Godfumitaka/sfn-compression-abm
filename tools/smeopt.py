"""呼び出しごとの種の上で、証拠のある再利用と厳密な上限だけを接続する。

名前の使用の回数・学習の記録・世界の完全な記録は読まない。
通常の控えのキーと寿命を保ち、省いたエンジンの呼び出しを別に記録する。
"""
from collections import OrderedDict
from fractions import Fraction
from hashlib import sha256
import math
import sys

import smebounds
import smereuse
import smeshared as shared
from sme2017 import VERSION, validate

ALIASES = OrderedDict()
STATS = {}
LIMIT = 512
BASE_SNAPSHOT = shared.snapshot
BASE_RESTORE = shared.restore
BASE_SELECT = shared.select_definition


def _call_kind():
    # 記録だけ。種を作った窓口の種類を読む。候補の選びには使わない。
    frame = sys._getframe(1)
    while frame is not None:
        if frame.f_globals.get("__name__") == "smeshared":
            if frame.f_code.co_name == "self_score":
                return "自己照合"
            if frame.f_code.co_name == "map_graphs":
                return frame.f_locals["use"]
        frame = frame.f_back
    return "部品検査"


def _bump(name):
    STATS[name] = STATS.get(name, 0) + 1


def _reuse_match(real, left, right, *, use_cache=True, tie_seed=None):
    engine = shared.ENGINE
    key = engine.match_key(left, right, tie_seed)
    # 通常の完全な控えを先に使う。連続の乱数と、控えを禁じた要求は包まない。
    if not use_cache or tie_seed is None or key in engine.cache:
        return real(left, right, use_cache=use_cache, tie_seed=tie_seed)
    at = smereuse.positions(left, right)
    if at is None:
        _bump("alias_ambiguous")
        return real(left, right, use_cache=use_cache, tie_seed=tie_seed)
    token = VERSION, engine.settings, at.code
    if token in ALIASES:
        original, old_at, origin_id = ALIASES.pop(token)
        # 同じ不変の図なら、Resultの実体も共有して二重に持たない。
        if (original.left_fingerprint, original.right_fingerprint) == (left.fingerprint(), right.fingerprint()):
            result = original
        else:
            result = smereuse.relabel(original, old_at, at, left, right)
        validate(left, right, result)
        assert not result.choices
        engine.cache[key] = result
        engine.cache_rng[key] = {"policy": "call-seed-uniform-v1" if shared.CTX.get("tie_uniform") else "call-seed-v1", "seed": tie_seed}
        ALIASES[token] = original, old_at, origin_id
        _bump("alias_hits")
        shared._log({"kind": "sme_skipped", "reason": "canonical_reuse_no_choices",
                     "version": VERSION, "trial": shared.CTX["trial"], "tie_seed": tie_seed,
                     "call_kind": _call_kind(),
                     "left": result.left_fingerprint, "right": result.right_fingerprint,
                     "result": sha256(repr(key).encode()).hexdigest(), "origin": origin_id,
                     "proof_choices": (), "unique_positions": True})
        return result
    result = real(left, right, use_cache=use_cache, tie_seed=tie_seed)
    _bump("alias_computed")
    if result.choices:
        _bump("alias_tied")
    else:
        ALIASES[token] = result, at, sha256(repr(key).encode()).hexdigest()
        if len(ALIASES) > LIMIT:
            ALIASES.popitem(last=False)
        STATS["alias_peak"] = max(STATS.get("alias_peak", 0), len(ALIASES))
    return result


def _preview(d, history):
    import v39
    graph = v39.v39_graph(d, history)
    try:
        return shared.typed_graph(graph)
    finally:
        v39.unregister(graph)


def _pruned_selection(state, scene, config):
    import abm.agent_runtime as ar
    import v39
    from dataclasses import replace
    v39.STATS["select_calls"] = v39.STATS.get("select_calls", 0) + 1
    ranked = []
    target = shared.typed_graph(scene)
    xx = shared.self_score(target)
    best_q = None
    for d in state.definitions.values():
        n = v39.n_FH(d, state.slot_history)
        if not n:
            continue
        preview = _preview(d, state.slot_history)
        # 保存の記録にも、自己照合を行った図を残す。
        shared.GRAPHS[preview.fingerprint()] = preview
        dd = shared.self_score(preview)
        supported = (all(x.kind in {"entity", "relation", "unknown"} for x in preview.nodes)
                     and sum(x.kind == "relation" and x.state != "U" for x in preview.nodes) == n)
        if best_q is not None and supported and dd + xx > 0 and math.isfinite(dd) and math.isfinite(xx):
            try:
                sup, score, q = smebounds.bound(preview, target, shared.ENGINE.settings, dd, xx)
            except (ValueError, OverflowError):
                q = None
            if q is not None:
                _bump("bounds")
                need = ar._need(config.tau_acc, n)
                # N3だけでは門を通る候補の一覧が変わる。二つとも厳密に負けるものだけ。
                if q < best_q and sup < need:
                    _bump("pruned")
                    shared._log({"kind": "sme_skipped", "reason": "strict_n3_and_gate_upper",
                                 "version": VERSION, "trial": shared.CTX["trial"], "R": d.name,
                                 "call_kind": "v39:map_v39",
                                 "tie_seed": shared._match_seed(preview, target, "v39:map_v39"),
                                 "support_upper": sup, "gate_need": need, "score_upper": score,
                                 "N3_upper": [q.numerator, q.denominator],
                                 "best_N3": [best_q.numerator, best_q.denominator],
                                 "left": preview.fingerprint(), "right": target.fingerprint()})
                    continue
        # 本番と同じ呼び出しの種類を保つ。この利用側からmap_graphsを直接呼ばない。
        g, al = v39.map_v39(d, state.slot_history, scene)
        if dd + xx == 0:
            shared.STATS["n3_den0"] = shared.STATS.get("n3_den0", 0) + 1
            continue
        q = 2 * Fraction(al.total_score) / (Fraction(dd) + Fraction(xx))
        support = sum(v39.seat_state(d, r, state.slot_history) != "U"
                      and r.relation.relation_id in al.relation_mapping for r in d.constituents)
        ranked.append((support / n, support, d, g, al, n, q))
        best_q = q if best_q is None else max(best_q, q)
        shared._log({"kind": "sme_n3", "R": d.name, "version": VERSION, "result": al.sme_result_id,
                     "S_dx": al.total_score, "S_dd": dd, "S_xx": xx, "N3": float(q),
                     "support": support, "m_live": n})
    if not ranked:
        return None
    best, tie = shared._definition_choice(ranked, target)
    ratio, support, d, graph, alignment, n, _q = best
    passed = [{"R": r[2].name, "support": r[1], "m_live": r[5], "ratio": r[0], "selected": r is best}
              for r in ranked if r[1] >= ar._need(config.tau_acc, r[5])]
    fids = {r.relation.relation_id for r in d.constituents if r.alive}
    alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in fids))
    return ratio, support, d, graph, alignment, n, tie, passed


def install(*, reuse=False, prune=False):
    import v39
    assert shared.CTX.get("call_seed"), "省略の旗は呼び出しごとの種でのみ使う"
    ALIASES.clear()
    STATS.clear()
    if reuse:
        real_match = shared.ENGINE.match

        def match(left, right, *, use_cache=True, tie_seed=None):
            return _reuse_match(real_match, left, right, use_cache=use_cache, tie_seed=tie_seed)

        shared.ENGINE.match = match
    if prune:
        shared.select_definition = _pruned_selection
        v39.select_definition = _pruned_selection
    else:
        shared.select_definition = BASE_SELECT
        v39.select_definition = BASE_SELECT

    def snapshot():
        return BASE_SNAPSHOT(), OrderedDict(ALIASES), dict(STATS)

    def restore(snap):
        ordinary, aliases, stats = snap
        BASE_RESTORE(ordinary)
        ALIASES.clear()
        ALIASES.update(aliases)
        STATS.clear()
        STATS.update(stats)

    shared.snapshot, shared.restore = snapshot, restore
