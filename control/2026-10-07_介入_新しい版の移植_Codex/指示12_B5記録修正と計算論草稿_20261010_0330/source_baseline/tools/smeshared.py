"""SMEの不変の結果を本番の利用側に届ける。旗を切れば読み込まない。

入力は記憶のF/H/Uと提示のグラフだけ。未知の位置に隠れた引数を足さない。
既存のmap_graphsの入口を、この同じ状態の結果を返す窓口へ置き換える。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from functools import lru_cache
import random
from hashlib import sha256
import gzip
import inspect
import io
import json
import sys

from abm.sme import Alignment, MappingResult
from sme2017 import Graph, Matcher, Node, Settings, VERSION, _Engine, validate

ENGINE = None
OLD_MAP = None
RESULTS: dict = {}
GRAPHS: dict = {}
CHOICES: dict = {}
STATS: dict = {}
LOG: dict = {}
CTX: dict = {}


def active_version():
    cstar = sys.modules.get('cstar_runtime')
    return cstar.VERSION if cstar is not None and cstar.active() else VERSION


class FrozenDict(dict):
    """JSONにそのまま書け、利用側で内容を書き替えられない辞書。"""
    def _blocked(self, *a, **k):
        raise TypeError("照合結果は不変")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _blocked

    def __deepcopy__(self, memo):
        return self


def freeze(x):
    if isinstance(x, dict):
        return FrozenDict((k, freeze(v)) for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return tuple(freeze(v) for v in x)
    return x


def graph_data(graph):
    return [{"key": n.key, "kind": n.kind, "names": sorted(n.names), "args": n.args,
             "state": n.state, "ubiquitous": n.ubiquitous} for n in graph.nodes]


@dataclass(frozen=True, slots=True)
class SharedAlignment(Alignment):
    sme_result_id: str = ""
    sme_audit: dict = None

    def __post_init__(self):
        Alignment.__post_init__(self)
        for key in ("entity_mapping", "relation_mapping", "score_breakdown", "prototype_prior_terms"):
            object.__setattr__(self, key, freeze(getattr(self, key)))
        object.__setattr__(self, "sme_audit", freeze(self.sme_audit or {}))


def typed_graph(g):
    """登録された許容名・忘れた引数を読む。図の名前や物のラベルは使わない。"""
    v39 = sys.modules.get("v39")
    entry = getattr(v39, "REG", {}).get(id(g))
    hallow = entry[1] if entry is not None and entry[0] is g else {}
    us = sys.modules.get("ustruct")
    urows = getattr(us, "UREG", {}).get(id(g), {}) if entry is not None else {}
    rels = {r.relation_id: r for r in g.relations}
    all_rels = dict(rels)
    all_rels.update(urows)
    sp = sys.modules.get("strictpc")
    relpos = getattr(sp, "RELPOS", {}).get(id(g), frozenset())
    entities = {e.entity_id for e in g.entities} - set(all_rels) - set(relpos)
    nodes = [Node(k, "entity") for k in entities]
    for k, r in all_rels.items():
        st = "U" if k in urows else "H" if k in hallow else "F"
        names = frozenset() if st == "U" else hallow[k] if st == "H" else frozenset({r.predicate})
        nodes.append(Node(k, "relation", names, tuple(r.arguments), st))
    present = entities | set(all_rels)
    missing = {a for r in all_rels.values() for a in r.arguments if a not in present}
    nodes.extend(Node(k, "unknown", args=None) for k in missing)
    return Graph(tuple(nodes))


@lru_cache(maxsize=4096)
def canonical_identity(g):
    # 字句を匿名の頂点にし、同じ名前の共有・F/H/U・引数の順を保つ。
    # 控えは純粋な関数の返り値だけ。抽選の状態は持たない。
    return _Engine(g, g, Settings(), random.Random(0))._key(frozenset())


def structural_key(g):
    return canonical_identity(g)


def call_seed(definition_identity, scene_identity, kind):
    payload = ("sme-call-seed-v1", CTX["run_seed"], CTX["trial"],
               definition_identity, scene_identity, kind)
    return int.from_bytes(sha256(json.dumps(payload, ensure_ascii=False,
                                          separators=(",", ":")).encode("utf-8")).digest(), "big")


def _match_seed(left, right, kind):
    return call_seed(canonical_identity(left), canonical_identity(right), kind) if CTX.get("call_seed") else None


def _caller():
    f = inspect.currentframe().f_back
    while f is not None:
        mod = f.f_globals.get("__name__", "")
        if mod != __name__:
            return f"{mod}:{f.f_code.co_name}"
        f = f.f_back
    return "unknown"


def _old_on_new(left, right, best, params):
    """新しい対応を旧式の四項で採点する。旧い対応の点とは分ける。"""
    import abm.sme as sme
    if best is None:
        return 0.0
    lb, rb = left.by_id, right.by_id
    names = args = links = 0
    rm, em = dict(best.relation_mapping), dict(best.entity_mapping)
    for a, b in rm.items():
        x, y = lb[a], rb[b]
        if y.kind == "unknown":
            continue
        names += int(bool(x.names & y.names))
        args += sum(em.get(p) == q or rm.get(p) == q for p, q in zip(x.args or (), y.args or ()))
        links += sum(p in rm and rm[p] == q for p, q in zip(x.args or (), y.args or ()))
    unmatched = sum(n.kind == "relation" and n.state != "U" and n.key not in rm for n in left.nodes)
    w = params or sme.SMEParams()
    return w.predicate_match_weight * names + w.argument_consistency_weight * args + w.higher_order_weight * links - w.unmatched_penalty * unmatched


def _log(record):
    if LOG.get("f") is not None:
        if LOG.get("diagnostic") or _diagnosing():
            if LOG.get("diagnostic_f") is None:
                LOG["diagnostic_f"] = _text_gzip(str(LOG["path"]).replace(".jsonl.gz", ".diagnostics.jsonl.gz"))
            target = LOG["diagnostic_f"]
        else:
            target = LOG["f"]
        target.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _diagnosing():
    # cf-valueは一つの保存を各席の後で復元する。二席目以降も記録は診断へ。
    f = inspect.currentframe().f_back
    paths = {("cfvalue", "_measure"), ("cflearn", "variants_correct"), ("probeworld", "_probe")}
    while f is not None:
        if (f.f_globals.get("__name__"), f.f_code.co_name) in paths:
            return True
        f = f.f_back
    return False


def _text_gzip(path):
    # gzipの時刻も固定し、記録の内容が同じなら圧縮後も同じにする。
    return io.TextIOWrapper(gzip.GzipFile(filename=str(path), mode="wb", mtime=0), encoding="utf-8")


def map_graphs(base_graph, target_graph_partial, params=None, *, prototype=None, prototype_prior_weight=0.0):
    import abm.sme as sme
    if prototype_prior_weight != 0.0:
        raise ValueError("SME版は指定された本番のprior=0だけを接続する")
    left, right = typed_graph(base_graph), typed_graph(target_graph_partial)
    lf, rf = left.fingerprint(), right.fingerprint()
    use = _caller()
    seed = _match_seed(left, right, use)
    cstar = sys.modules.get('cstar_runtime')
    expected = cstar is not None and cstar.active()
    engine = cstar.ENGINE if expected else ENGINE
    version = cstar.VERSION if expected else VERSION
    probability = cstar.probabilities_for_graph(base_graph,left,target_graph_partial) if expected else None
    key = (engine.match_key(left,right,seed,probabilities=probability) if expected
           else engine.match_key(left,right,seed))
    STATS["requests"] = STATS.get("requests", 0) + 1
    if key in RESULTS:
        STATS["reused"] = STATS.get("reused", 0) + 1
        out = RESULTS[key]
        _log({"kind": "sme_use", "caller": use, "version": version, "result": out.alignment.sme_result_id, "reused": True})
        return out
    result = (engine.match(left,right,tie_seed=seed,probabilities=probability) if expected
              else engine.match(left,right,tie_seed=seed))
    rng_before = engine.cache_rng[key]
    (cstar.validate if expected else validate)(left, right, result)
    GRAPHS[lf], GRAPHS[rf] = left, right
    best = result.best
    em = {} if best is None else dict(best.entity_mapping)
    rm = {} if best is None else dict(best.relation_mapping)
    # 旧い照合の計数の変更を本体へ戻さない。比較の結果だけ別の欄に残す。
    import probeworld
    snap = probeworld._snapshot_modules()
    sp = sys.modules.get("strictpc")
    sp_stats = dict(sp.STATS) if sp is not None else None
    try:
        old = OLD_MAP(base_graph, target_graph_partial, params).alignment
    finally:
        probeworld._restore_modules(snap)
        if sp_stats is not None:
            sp.STATS.clear()
            sp.STATS.update(sp_stats)
    identifier = sha256(repr(key).encode()).hexdigest()
    kinds = () if best is None else best.match_kinds
    visible_names = sum(k == "name" and b in {r.relation_id for r in target_graph_partial.relations} for a, b, k in kinds)
    if expected:
        visible_names = sum(bool(left.by_id[a].names & right.by_id[b].names)
                            for a,b in rm.items() if right.by_id[b].kind != 'unknown')
    audit = {"version": version, "settings": asdict(engine.settings), "left": lf, "right": rf,
             "selected": result.selected, "tied": result.tied, "choices": result.choices,
             "kinds": kinds, "points": () if best is None else best.breakdown,
             "visible_name_matches": visible_names, "old_on_new": _old_on_new(left, right, best, params),
             "old_selected_score": old.total_score, "old_entity_mapping": dict(old.entity_mapping),
             "old_relation_mapping": dict(old.relation_mapping),
             "new_entity_mapping": em, "new_relation_mapping": rm}
    if expected:
        audit.update(cstar_probabilities=probability,match_eps=cstar.CFG['match_eps'],
                     candidates=len(result.candidates),hypotheses=result.hypothesis_count if hasattr(result,'hypothesis_count') else None)
    if seed is not None:
        audit.update(tie_policy="call-seed-uniform-v1" if CTX.get("tie_uniform") else "call-seed-v1",
                     tie_seed=seed, trial=CTX["trial"], call_kind=use)
    projectable = sme._projectable_base_relation_ids(base_graph, target_graph_partial, em, rm,
                                                    sme._relation_ids(base_graph), sme._relation_ids(target_graph_partial))
    local = 0.0 if best is None else sum(p[2] for p in best.breakdown)
    td = 0.0 if best is None else sum(p[3] for p in best.breakdown)
    al = SharedAlignment(em, rm, 0.0 if best is None else best.score,
                         {"sme_local": local, "sme_trickle_down": td}, td, visible_names,
                         sum(n.kind == "relation" and n.key not in rm for n in left.nodes), projectable,
                         sme_result_id=identifier, sme_audit=audit)
    out = MappingResult(alignment=al)
    RESULTS[key] = out
    STATS["computed"] = STATS.get("computed", 0) + 1
    _log({"kind": "sme_result", "caller": use, "result": identifier, **audit,
          "left_nodes": graph_data(left), "right_nodes": graph_data(right), "rng_before": rng_before})
    return out


def _definition_choice(candidates, scene):
    # N3の同点では既存の席数・新しさを保ち、最後の名前順だけ構造に替える。
    first = max((r[6], r[5], r[2].registered_at) for r in candidates)
    tied = [r for r in candidates if (r[6], r[5], r[2].registered_at) == first]
    if CTX.get("tie_uniform"):
        forms = tuple(sorted(canonical_identity(GRAPHS[r[4].sme_audit["left"]]) for r in tied))
        seed = call_seed(forms, canonical_identity(scene), "定義の選び")
        token = ("definition", "call-seed-uniform-v1", seed,
                 tuple((r[2].name, r[2].registered_at) for r in tied))
        if token not in CHOICES:
            pick = random.Random(seed).randrange(len(tied)) if len(tied) > 1 else 0
            CHOICES[token] = (tied[pick][2].name, tied[pick][2].registered_at)
        selected = CHOICES[token]
        chosen = next(r for r in tied if (r[2].name, r[2].registered_at) == selected)
        _log({"kind": "sme_definition_tie", "version": active_version(),
              "set": [(r[2].name, r[2].registered_at) for r in tied], "selected": selected,
              "tie_policy": "call-seed-uniform-v1", "tie_seed": seed, "trial": CTX["trial"],
              "canonical_multiset": forms})
        return chosen, len(tied) > 1
    keys = {id(r): structural_key(GRAPHS[r[4].sme_audit["left"]]) for r in tied}
    least = min(keys.values())
    tied = [r for r in tied if keys[id(r)] == least]
    if CTX.get("call_seed"):
        forms = tuple(sorted(keys[id(r)] for r in tied))
        seed = call_seed(forms, canonical_identity(scene), "定義の選び")
        # 完全に同じ正準形の候補は、承認された登録の順（記憶の辞書の順）。
        options = sorted(tied, key=lambda r: keys[id(r)])
        token = ("definition", "call-seed-v1", seed,
                 tuple((r[2].name, r[2].registered_at) for r in options))
        if token not in CHOICES:
            pick = random.Random(seed).randrange(len(options)) if len(options) > 1 else 0
            CHOICES[token] = (options[pick][2].name, options[pick][2].registered_at)
    else:
        token = (VERSION, ENGINE.settings, scene.fingerprint(),
                 tuple(sorted((r[4].sme_audit["left"], r[2].name, r[2].registered_at) for r in tied)))
        if token not in CHOICES:
            options = sorted(tied, key=lambda r: (r[4].sme_audit["left"], r[2].name))
            pick = ENGINE.rng.randrange(len(options)) if len(options) > 1 else 0
            CHOICES[token] = (options[pick][2].name, options[pick][2].registered_at)
    selected = CHOICES[token]
    chosen = next(r for r in tied if (r[2].name, r[2].registered_at) == selected)
    _log({"kind": "sme_definition_tie", "version": active_version(),
          "set": [(r[2].name, r[2].registered_at) for r in tied], "selected": selected,
          **({"tie_policy": "call-seed-v1", "tie_seed": seed, "trial": CTX["trial"],
              "canonical_multiset": forms} if CTX.get("call_seed") else {})})
    return chosen, len(tied) > 1


def choose_trace(ranked, scene):
    """逐語の場面選びにもID順を残さず、同じ状態の同点は同じ選択を戻す。"""
    first = max((m.alignment.total_score, tr.written_at) for m, tr in ranked)
    tied = [(m, tr) for m, tr in ranked if (m.alignment.total_score, tr.written_at) == first]
    if CTX.get("tie_uniform"):
        forms = tuple(sorted(canonical_identity(GRAPHS[m.alignment.sme_audit["left"]]) for m, tr in tied))
        seed = call_seed(forms, canonical_identity(typed_graph(scene)), "逐語の選び")
        token = ("trace", "call-seed-uniform-v1", seed,
                 tuple((m.alignment.sme_audit["left"], tr.scene.graph_id) for m, tr in tied))
        if token not in CHOICES:
            pick = random.Random(seed).randrange(len(tied)) if len(tied) > 1 else 0
            CHOICES[token] = (tied[pick][0].alignment.sme_audit["left"], tied[pick][1].scene.graph_id)
        selected = CHOICES[token]
        _log({"kind": "sme_trace_tie", "version": active_version(),
              "set": [(m.alignment.sme_audit["left"], tr.scene.graph_id) for m, tr in tied],
              "selected": selected, "tie_policy": "call-seed-uniform-v1", "tie_seed": seed,
              "trial": CTX["trial"], "canonical_multiset": forms})
        return next(it for it in tied if (it[0].alignment.sme_audit["left"], it[1].scene.graph_id) == selected)
    keys = {id(tr): structural_key(GRAPHS[m.alignment.sme_audit["left"]]) for m, tr in tied}
    least = min(keys.values())
    tied = [(m, tr) for m, tr in tied if keys[id(tr)] == least]
    if CTX.get("call_seed"):
        forms = tuple(sorted(keys[id(tr)] for m, tr in tied))
        seed = call_seed(forms, canonical_identity(typed_graph(scene)), "逐語の選び")
        options = sorted(tied, key=lambda it: keys[id(it[1])])
        token = ("trace", "call-seed-v1", seed,
                 tuple((m.alignment.sme_audit["left"], tr.scene.graph_id) for m, tr in options))
        if token not in CHOICES:
            pick = random.Random(seed).randrange(len(options)) if len(options) > 1 else 0
            CHOICES[token] = (options[pick][0].alignment.sme_audit["left"], options[pick][1].scene.graph_id)
    else:
        token = ("trace", VERSION, ENGINE.settings, typed_graph(scene).fingerprint(),
                 tuple(sorted((m.alignment.sme_audit["left"], tr.written_at, tr.scene.graph_id) for m, tr in tied)))
        if token not in CHOICES:
            options = sorted(tied, key=lambda it: (it[0].alignment.sme_audit["left"], it[1].scene.graph_id))
            pick = ENGINE.rng.randrange(len(options)) if len(options) > 1 else 0
            CHOICES[token] = (options[pick][0].alignment.sme_audit["left"], options[pick][1].scene.graph_id)
    selected = CHOICES[token]
    _log({"kind": "sme_trace_tie", "version": active_version(), "set": [(m.alignment.sme_audit["left"], tr.scene.graph_id) for m, tr in tied],
          "selected": selected,
          **({"tie_policy": "call-seed-v1", "tie_seed": seed, "trial": CTX["trial"],
              "canonical_multiset": forms} if CTX.get("call_seed") else {})})
    return next(it for it in tied if (it[0].alignment.sme_audit["left"], it[1].scene.graph_id) == selected)


def select_definition(state, scene, config):
    import abm.agent_runtime as ar
    import v39
    v39.STATS["select_calls"] = v39.STATS.get("select_calls", 0) + 1
    ranked = []
    target = typed_graph(scene)
    xx = self_score(target)
    for d in state.definitions.values():
        n = v39.n_FH(d, state.slot_history)
        if not n:
            continue
        g, al = v39.map_v39(d, state.slot_history, scene)
        dd = self_score(GRAPHS[al.sme_audit["left"]])
        if dd + xx == 0:
            STATS["n3_den0"] = STATS.get("n3_den0", 0) + 1
            continue
        # 浮動小数の丸めを足さず、出たSESの比を分数として比較する。
        n3 = 2 * Fraction(al.total_score) / (Fraction(dd) + Fraction(xx))
        cstar = sys.modules.get('cstar_runtime')
        support = (sum(cstar.support(d,r,state.slot_history,al,scene) for r in d.constituents)
                   if cstar is not None and cstar.active() else
                   sum(v39.seat_state(d,r,state.slot_history) != 'U' and r.relation.relation_id in al.relation_mapping
                       for r in d.constituents))
        ranked.append((support / n, support, d, g, al, n, n3))
        _log({"kind": "sme_n3", "R": d.name, "version": active_version(), "result": al.sme_result_id,
              "S_dx": al.total_score, "S_dd": dd, "S_xx": xx, "N3": float(n3), "support": support, "m_live": n})
    if not ranked:
        return None
    best, tie = _definition_choice(ranked, target)
    ratio, support, d, graph, alignment, n, _q = best
    passed = [{"R": r[2].name, "support": r[1], "m_live": r[5], "ratio": r[0], "selected": r is best}
              for r in ranked if r[1] >= ar._need(config.tau_acc, r[5])]
    fids = {r.relation.relation_id for r in d.constituents if r.alive}
    alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in fids))
    return ratio, support, d, graph, alignment, n, tie, passed


def self_score(graph):
    """自己の点も通常の照合の第一位から。旧い行ごとの自己点は使わない。"""
    cstar = sys.modules.get('cstar_runtime')
    if cstar is not None and cstar.active():
        value = cstar.ENGINE.self_score(graph)
        _log(dict(kind='sme_self',version=cstar.VERSION,input=graph.fingerprint(),score=value,
                  self_policy='full-identity-all-names-match',settings=asdict(cstar.ENGINE.settings)))
        return value
    seed = _match_seed(graph, graph, "自己照合")
    result = ENGINE.match(graph, graph, tie_seed=seed)
    validate(graph, graph, result)
    best = result.best
    _log({"kind": "sme_self", "version": VERSION, "settings": asdict(ENGINE.settings),
          "input": graph.fingerprint(), "selected": result.selected, "tied": result.tied,
          "entity_mapping": () if best is None else best.entity_mapping,
          "relation_mapping": () if best is None else best.relation_mapping,
          "points": () if best is None else best.breakdown, "score": 0.0 if best is None else best.score,
          **({"tie_policy": "call-seed-uniform-v1" if CTX.get("tie_uniform") else "call-seed-v1",
              "tie_seed": seed, "trial": CTX["trial"], "call_kind": "自己照合"}
             if seed is not None else {})})
    return ENGINE.self_score(graph, tie_seed=seed)


def snapshot():
    saved = ENGINE.snapshot(), dict(RESULTS), dict(GRAPHS), dict(CHOICES), dict(STATS), dict(CTX)
    cstar = sys.modules.get('cstar_runtime')
    return saved + (cstar.snapshot(),) if cstar is not None and cstar.ENGINE is not None else saved


def restore(snap):
    engine, results, graphs, choices, stats, context = snap[:6]
    if len(snap) == 7:
        sys.modules['cstar_runtime'].restore(snap[6])
    ENGINE.restore(engine)
    for current, saved in ((RESULTS, results), (GRAPHS, graphs), (CHOICES, choices), (STATS, stats), (CTX, context)):
        current.clear()
        current.update(saved)


def install(path, *, tie_seed, call_seed=False, tie_uniform=False):
    global ENGINE, OLD_MAP
    import abm.sme as sme
    import probeworld
    import v39
    if tie_uniform and not call_seed:
        raise ValueError("同点の一様抽選には呼び出しごとの種が必要")
    ENGINE = Matcher(Settings(), tie_seed=int.from_bytes(sha256(f"sme-tie\x1f{tie_seed}".encode()).digest(), "big"),
                     **({"tie_uniform": True} if tie_uniform else {}))
    OLD_MAP = sme.map_graphs
    for d in (RESULTS, GRAPHS, CHOICES, STATS, LOG, CTX):
        d.clear()
    CTX.update(call_seed=call_seed, run_seed=tie_seed, trial=0)
    if tie_uniform:
        CTX["tie_uniform"] = True
    if call_seed:
        import abm.loop as loop
        real_input = loop._agent_input

        def agent_input(trial, before):
            CTX["trial"] = trial.trial
            return real_input(trial, before)

        loop._agent_input = agent_input
    LOG.update(f=_text_gzip(path) if path is not None else None, path=path, diagnostic=False, diagnostic_f=None)
    # 既に読み込まれた全入口と、これから読み込む入口を同じ窓口にする。
    for module in tuple(sys.modules.values()):
        if module is None or module is sys.modules[__name__]:
            continue
        for key, value in tuple(vars(module).items()):
            if value is OLD_MAP:
                setattr(module, key, map_graphs)
    sme.map_graphs = map_graphs
    v39.select_definition = select_definition
    v39.CFG["sme2017"] = True
    real_snapshot, real_restore = probeworld._snapshot_modules, probeworld._restore_modules

    def snapshot_modules():
        snap = real_snapshot(), snapshot(), LOG.get("diagnostic", False)
        LOG["diagnostic"] = True
        return snap

    def restore_modules(snap):
        ordinary, own, phase = snap
        real_restore(ordinary)
        restore(own)
        LOG["diagnostic"] = phase

    probeworld._snapshot_modules = snapshot_modules
    probeworld._restore_modules = restore_modules


def close():
    if LOG.get("f") is not None:
        LOG["f"].close()
    if LOG.get("diagnostic_f") is not None:
        LOG["diagnostic_f"].close()
    return {"version": VERSION, "settings": asdict(ENGINE.settings), **STATS,
            **({"tie_policy": "call-seed-uniform-v1" if CTX.get("tie_uniform") else "call-seed-v1"}
               if CTX.get("call_seed") else {})}
