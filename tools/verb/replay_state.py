"""既存 sealrestore の状態復元とキャッシュ解放を使う研究者側の読み手。模型には読み込まれない。"""
from __future__ import annotations
import ast
import sys
_MV38 = []

def configs_of(cfg, task):
    """sweep.run_one と同じ AgentConfig。"""
    from abm.domains import AgentConfig, CorrectionMode, RepairScope
    from sweep import higher_order_predicates, load_seed
    fixed = cfg["fixed"]
    seed = load_seed(cfg["seed_file"])
    return {a: AgentConfig(
        fixed["threshold"], CorrectionMode(fixed["correction_mode"]), theta_prime=task["theta_prime"], tau_acc=fixed["tau_acc"],
        verbatim_theta=task["verbatim_theta"], nsim_threshold=fixed["nsim_threshold"], alpha=fixed["alpha"], beta=fixed["beta"], w=fixed["w"],
        kappa=fixed["kappa"], lambda_mix=fixed["lambda_mix"], abstain_charge=fixed["abstain_charge"], repair_scope=RepairScope(task["repair_scope"]),
        pending_claims=fixed.get("pending_claims", False), pending_gamma=fixed.get("pending_gamma", 0.0),
        pending_hold_cost=fixed.get("pending_hold_cost", 0.0), fill_selection=task["fill_selection"],
        identification_graph=fixed.get("identification_graph", "live"), self_score_cache=fixed.get("self_score_cache", "off"),
        pricing_rule=fixed.get("pricing_rule", "legacy"), refill_rule=fixed.get("refill_rule", "legacy"), local_lambda=fixed.get("local_lambda", 0.0),
        holdout_include_second_order=fixed.get("holdout_include_second_order", False), higher_order_predicates=higher_order_predicates(seed),
    ) for a in cfg["agent_ids"]}

def _key(k):
    return ast.literal_eval(k)

def _merit_v38():
    if not _MV38:
        from dataclasses import dataclass
        from abm.definition import MeritAccumulator

        @dataclass(frozen=True, slots=True)
        class MeritAccumulatorV38(MeritAccumulator):
            eval_basis: tuple = ()
        _MV38.append(MeritAccumulatorV38)
    return _MV38[0]

def restore_state(d, argmap, scenes):
    """台帳の状態の dict → AgentStateV39。"""
    import v39
    import roletarget_recompute as rr
    from abm.definition import EmbedState, ExceptionAccumulator, FrequencyTable, MeritAccumulator
    from abm.domains import Entity, Prototype, Relation, RelationGraph, VerbatimTrace
    defs = {}
    bad = 0
    for name, dd in d["definitions"].items():
        nd, b = rr._restore_def(dd, argmap)
        defs[name] = nd
        bad += len(b)
    MV38 = _merit_v38()
    merit = {}
    for k, v in d.get("merit", {}).items():
        kw = dict(slot_index=v["slot_index"], registered_at=v["registered_at"], basis=tuple(v["basis"]),
                  opportunity_basis=tuple(v["opportunity_basis"]), use_count=v["use_count"],
                  ext_use_count=v["ext_use_count"], ext_basis=tuple(v.get("ext_basis") or ()))
        # ★ --own-evidence（tools/v38.py:57）の型は eval_basis の欄を足したもの。同じ欄の型で戻す（欄の名で正準形が決まる）
        merit[_key(k)] = MV38(**kw, eval_basis=tuple(v["eval_basis"])) if "eval_basis" in v else MeritAccumulator(**kw)
    embed = {_key(k): EmbedState(**v) for k, v in d.get("embed", {}).items()}
    exc = {_key(k): ExceptionAccumulator(basis=tuple(v["basis"]), bits=v["bits"], event_count=v["event_count"]) for k, v in d.get("exceptions", {}).items()}
    ph = d["p_hat"]
    p_hat = FrequencyTable(counts=dict(ph["counts"]), total=ph["total"], lambda_mix=ph["lambda_mix"], alive_vocab=frozenset(ph["alive_vocab"]))
    sh = {}
    for k, v in d.get("slot_history", {}).items():
        sh[_key(k)] = dict(v) if isinstance(v, dict) else frozenset(v)
    # ★ 原型の場面：本人が観察した場面（提示に、開示があれば伏せた関係を足したもの。abm/agent_runtime.py _write_graph）。
    #   並びは、提示の場面の関係・物の並びのあとに、提示に無いもの（開示の関係）を足す。引数の並びは世界から
    tl = []
    for tr in sorted(d.get("prototype", {}).get("traces", []), key=lambda x: x["written_at"]):
        sc = tr["scene"]
        g = sc["graph_id"]
        basep = scenes.get(g)
        rels = list(basep.relations) if basep is not None else []
        have = {r.relation_id for r in rels}
        for rd in sc["relations"]:
            if rd["relation_id"] not in have:
                rels.append(Relation(relation_id=rd["relation_id"], predicate=rd["predicate"],
                                     arguments=tuple(argmap.get(rd["relation_id"], rd["arguments"])), attributes=rd.get("attributes") or {}))
        ents = list(basep.entities) if basep is not None else []
        haveE = {e.entity_id for e in ents}
        for ed in sc["entities"]:
            if ed["entity_id"] not in haveE:
                ents.append(Entity(entity_id=ed["entity_id"], label=ed.get("label"), attributes=ed.get("attributes") or {}))
        tl.append(VerbatimTrace(written_at=tr["written_at"], scene=RelationGraph(g, entities=tuple(ents), relations=tuple(rels))))
    proto = Prototype(traces=tuple(tl))
    seats = {}
    for k, v in d.get("v39_seats", {}).items():
        seats[_key(k)] = v39.SeatRec(gen=v["gen"], state=v["state"], born=v["born"], t0=v["t0"],
                                     init=tuple(tuple(c) for c in v["init"]), post=tuple(tuple(c) for c in v["post"]), n_scored=v.get("n_scored", 0))
    def tup(x):
        return tuple(tup(y) for y in x) if isinstance(x, list) else x
    rng = tup(d.get("rng_state"))
    cls = v39._state_class()
    kw = dict(prototype=proto, rng_state=rng, definitions=defs, merit=merit, embed=embed, exceptions=exc, p_hat=p_hat,
              slot_history=sh, v39_seats=seats)
    return cls(**kw), bad

def _clear_caches(loop):
    """毎試行の終わりに、物の id で控える記憶を空にする（作り直した状態は試行ごとに新しい物なので、控えが溜まり続けるため。
    本物の走行では、台帳を書く段で試行ごとに捨てられる：tools/fastledger.py・tools/lowmem.py。v39.REG・ustruct.UREG も id の控え）。
    記憶は計算の近道なので、空にしても計算の結果は変わらない（確かめ①で予測が本物と同じことを見る）。"""
    loop._CANONICAL_CACHE.clear(); loop._CANONICAL_KEEP.clear(); loop._REPR_CACHE.clear()
    for mn in ("fastledger", "lowmem"):
        m = sys.modules.get(mn)
        if m is None:
            continue
        for an in ("CACHE", "KEEP", "DESC", "REPR", "TOUCHED", "STACK", "KEYM", "KEYT", "FRAGM", "FRAGT", "LKEYS", "LKEYT"):
            v = getattr(m, an, None)
            if v is not None and hasattr(v, "clear"):
                v.clear()
    for mn, an in (("v39", "REG"), ("ustruct", "UREG")):
        m = sys.modules.get(mn)
        if m is not None and hasattr(getattr(m, an, None), "clear"):
            getattr(m, an).clear()

def _strip(d):
    d = dict(d)
    d["v39_seats"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("init", "post")} for k, v in d.get("v39_seats", {}).items()}
    return d
