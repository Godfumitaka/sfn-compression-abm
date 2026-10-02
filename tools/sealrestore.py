"""シールを戻す確かめ（委任書「シールを戻す確かめ（記録の解析だけ）」2026-10-02 昼の 1）。★ 記録を読むだけ。本物の状態・乱数・台帳・side は変えない。
やり方：
  1 走行と同じ差し替え（tools/v3_run.py worker の install の並び）を、作業用の置き場所（side・台帳の書き出し先）で入れる。走行の本体
    （sweep.run_one）は呼ばず、代わりにこの解析を呼ぶ（新しい走行はしない）。
  2 予測の直前の状態を、台帳から作り直した dict（tools/extrap_reader.py iter_run）から、模型の状態の型（AgentStateV39）に戻す。
    ・定義：行は slot_index の順、関係の引数の並びは世界の同じ ID の関係から（tools/roletarget_recompute.py _restore_def と同じ）。
    ・原型の場面：作り直した世界の提示の場面（同じ graph_id）の物そのもの。並びは書いた試行の順（仮の決定。予測は点数・書いた試行・
      graph_id で並べ直すので並びに依らない）。
    ・16 本の成績の列（merit・exceptions・v39_seats）は、台帳の正準形が列を整列して書く（abm/loop.py _canonical_build）ので元の並びに
      戻せない。台帳の並びのまま入れる（予測には使わない量。下の確かめ①で、予測が本物と同じになることを全件で確かめる）。
    ・--strict-pc の引数の種類の控えは、tools/roletarget_recompute.py と同じく各試行の後に足す。
  3 確かめ①：作り直した状態（何も戻さない）で予測をやり直し、本物の予測（台帳の R_used・答えの述語と引数・棄権の理由・支持の数と m_live）と
    比べる。対象は、その走行の全試行（仮の決定）。確かめ②：作り直した状態の正準形の sha256 が台帳の指紋と同じ。
  4 戻して答え直す（対象の件ごと）：写しの上で、選ばれた定義のシールの席だけを「U になる前の最後の状態」に戻し、本物の予測と同じ乱数
    （abm/loop.py _rng_seed(agent, 試行)）から予測をやり直す。正解は渡さない。
    「最後の状態」：それより前の試行の終わりの状態のうち、その席（定義名・定義の登録試行・席の番号・行の登録試行で同じ席とする）が U でなかった
    最後のもの。F なら行を生かして固定の名前（その時の述語）と履歴の欄、H なら履歴の欄（名前と回数）を戻す。取り出せない件は理由別に数えて除く。
    比べの条件：同じ定義の、シール以外の U の席のうち最後の状態を取り出せるものから一つを無作為に（乱数の種は件ごと：
    "ctrl|<腕>|<種>|<試行>"）選び、同じように戻す。
出力：<出力>/<腕>/seed<種>.restore.jsonl（件ごと）、<出力>/<腕>/seed<種>.check.json（確かめ）。
使い方  python3.12 tools/sealrestore.py <出力の場所> <腕の走行根> <対象の件の csv（sealmem の answers）の場所> [種 …]（並列 SR_WORKERS、既定 2）"""
from __future__ import annotations

import ast
import copy
import csv
import glob
import hashlib
import json
import os
import sys
import tempfile
import time
from multiprocessing import get_context
from random import Random

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def make_task(root, cell, seed, scratch):
    """flag.json から tools/v3_run.py main と同じ task を作る（書き出し先は作業用の置き場所）。"""
    import sweep
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(W, fl["config"]), encoding="utf-8"))
    cfg2 = copy.deepcopy(cfg)
    cfg2["output"]["dir"] = os.path.join(scratch, "ledgers")
    if fl.get("nsim") is not None:
        cfg2["fixed"]["nsim_threshold"] = fl["nsim"]
    if fl.get("vt") is not None:
        cfg2["axes"]["verbatim_theta"] = [fl["vt"]]
    runs = [r for r in sweep.enumerate_runs(cfg2) if r["seed"] == seed and r["cell"] == cell]
    assert len(runs) == 1, (cell, seed, len(runs))
    seedobj = sweep.load_seed(cfg["seed_file"])
    t = {**runs[0], "cfg": cfg2, "code_commit": fl["commit"], "orig_dir": None, "out_root": scratch,
         "seed_file_sha256": getattr(seedobj, "file_sha256", None), "nohash": fl["nohash"], "prune": fl["greedy"], "extgreedy": fl["extgreedy"],
         "lowmem": fl["lowmem"], "extend_rule": fl["extend_rule"], "charge1": fl["charge1"], "dump_slot_history": fl["dump_slot_history"],
         "ident_rho": fl["ident_rho"], "ident_argmax": fl["ident_argmax"], "ident_shadow": fl["ident_shadow"], "ident_commons": fl["ident_commons"],
         "fast": fl["fast"], "nohist": fl["nohist"], "fix2": fl["fix2"], "fix_order": fl["fix_order"], "fix_order2": fl["fix_order2"],
         "rename_check": fl["rename_check"], "proj_first": fl["proj_first"], "fix2_full": fl["fix2_full"], "fill_unseen": fl["fill_unseen"],
         "fill_norestate": fl["fill_norestate"], "no_charge2": fl["no_charge2"], "death_terms": fl["death_terms"], "checks": fl["checks"],
         "own_evidence": fl["own_evidence"], "v39": fl["v39"], "v39_budget": (None if fl["v39_budget"] == "inf" else int(fl["v39_budget"])),
         "v39_init": fl["v39_init"], "v39_a": float(fl["v39_a"]), "v39_u": fl["v39_u"], "v39_decay": fl["v39_decay"], "v39_price": fl["v39_price"],
         "v39_dump_cands": False, "v310_be": fl["v310_be"], "hist_role": fl["hist_role"], "score_role": fl["score_role"],
         "world_cue": bool(fl["world_cue"]), "world_cue_p": fl["world_cue"] or 0.8, "dump_answers": fl["dump_answers"], "dump_routing": fl["dump_routing"],
         "u_struct": fl["u_struct"], "relearn_init": fl["relearn_init"], "tie_struct": fl["tie_struct"], "amb_local": fl["amb_local"],
         "answer_gap": fl["answer_gap"], "probe_world": fl["probe_world"], "shop_world": fl["shop_world"], "shop_exc": fl["shop_exc"] or 0.2,
         "shop_keep_cue": fl["shop_keep_cue"], "strict_pc": fl["strict_pc"], "cf_value": fl["cf_value"], "e_price": fl["e_price"],
         "cf_learn": fl["cf_learn"], "compare": False}
    return t, cfg


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


_MV38 = []


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


def seat_st(dd_alive, key2, sh):
    return "F" if dd_alive else ("H" if key2 in sh else "U")


def outcome(output, held):
    from abm.domains import EdgePrediction
    p = output.prediction
    tr = output.trace
    n = tr.get("m_live") or 0
    sup = tr.get("support_at_adoption", 0)
    if isinstance(p, EdgePrediction):
        e = p.edge
        hit = e.predicate == held.predicate and tuple(e.arguments) == tuple(held.arguments)
        return {"R": tr.get("R_used"), "答え": e.predicate, "引数": list(e.arguments), "当たり": hit, "黙り": False, "理由": None,
                "支持": sup, "m_live": n, "支持の割合": (sup / n if n else None)}
    return {"R": tr.get("R_used"), "答え": None, "引数": None, "当たり": False, "黙り": True, "理由": getattr(p, "reason", None),
            "支持": sup, "m_live": n, "支持の割合": (sup / n if n else None)}


def analysis(job):
    """sweep.run_one の代わりに呼ばれる（差し替えはすべて入った状態）。"""
    import abm.loop as loop
    import shopworld as sw
    from dataclasses import replace
    from extrap_reader import iter_run
    task, cfg, root, cell, seed, targets, out_dir, arm = job
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    configs = configs_of(cfg, task)
    agent = cfg["agent_ids"][0]
    config = configs[agent]
    strict = bool(fl.get("strict_pc"))
    argmap, scenes = {}, {}
    last = {}          # (定義名, 定義の登録試行, 席, 行の登録試行) → U でなかった最後の状態
    chk = {"trials": 0, "pred_compared": 0, "pred_mismatch": 0, "hash_mismatch": 0, "args_unrestored": 0, "examples": []}
    rows_out = []
    t0 = time.time()
    # ★ 世界の作り直し：走行と同じ差し替えが入っているので、読み手（extrap_reader）がお店の世界の包みをもう一度かぶせないよう、
    #   世界を作る間だけ abm.world.generate_trial を包まれていない元の関数にする（作り終えたら戻す）
    import abm.world as wmod
    wrapped = wmod.generate_trial
    base = wrapped
    seen = set()
    while getattr(base, "__module__", None) != "abm.world" and id(base) not in seen:
        seen.add(id(base))
        cells = [c.cell_contents for c in (base.__closure__ or ()) if callable(getattr(c, "cell_contents", None))]
        nxt = [f for f in cells if getattr(f, "__name__", "") == "generate_trial"]
        if not nxt:
            break
        base = nxt[0]
    if getattr(base, "__module__", None) != "abm.world":
        raise RuntimeError("元の generate_trial を見つけられない")
    wmod.generate_trial = base
    it = iter_run(root, cell, seed, check_hash=True)
    first = next(it)
    wmod.generate_trial = wrapped

    def chain():
        yield first
        yield from it

    max_t = int(os.environ.get("SR_MAX_T", "999999"))
    full = seed in {int(x) for x in os.environ.get("SR_FULL", "1,2,3,4,5").split(",") if x}
    chk["全試行の確かめ"] = full
    for tr in chain():
        t = tr["t"]
        if t > max_t:
            break
        if os.environ.get("SR_MEMLOG") and t % 100 == 0:
            import resource
            import v39 as _v
            sizes = {"v39.CTX": {k: len(v) for k, v in _v.CTX.items() if hasattr(v, "__len__")},
                     "loop": [len(loop._CANONICAL_CACHE), len(loop._CANONICAL_KEEP), len(loop._REPR_CACHE)]}
            for mn in ("fix2", "fixorder2", "strictpc", "ustruct", "v310be", "answergap", "tiestruct", "v32", "histrole", "answerlog", "cfvalue", "cflearn", "probeworld", "routelog"):
                m = sys.modules.get(mn)
                if m is None:
                    continue
                for an in ("CTX", "ST", "STATS", "CACHE", "KINDS", "_CACHE", "LAST", "REG"):
                    v = getattr(m, an, None)
                    if isinstance(v, dict):
                        sizes[f"{mn}.{an}"] = {k: len(x) for k, x in v.items() if hasattr(x, "__len__") and not isinstance(x, str) and len(x) > 50} or len(v)
            print("MEM", t, round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2), "GB", json.dumps(sizes, ensure_ascii=False, default=str)[:1500], flush=True)
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
        scenes.setdefault(wt.target_graph_partial.graph_id, wt.target_graph_partial)
        pre = tr["pre"]
        row = tr["row"]
        chk["trials"] += 1
        # ★ 全試行の確かめ（確かめ①②）は SR_FULL の種だけ（仮の決定。2026-10-02 昼、Mac が熱で止まったあとの負荷を下げるため）。
        #   ほかの種は、対象の試行でだけ状態を作り直す（対象の試行では、戻さない予測と本物の比べを毎件行う）
        if pre is not None and (full or t in targets):
            st, bad = restore_state(pre, argmap, scenes)
            chk["args_unrestored"] += bad
            loop._CANONICAL_CACHE.clear(); loop._CANONICAL_KEEP.clear(); loop._REPR_CACHE.clear()
            cd0 = json.loads(loop._json_bytes(loop._canonical(st)))
            if hashlib.sha256(loop._json_bytes(cd0)).hexdigest() != hashlib.sha256(loop._json_bytes(pre)).hexdigest():
                chk["hash_mismatch_full"] = chk.get("hash_mismatch_full", 0) + 1
            # ★ 確かめ②（仮の決定）：v39_seats の init・post（16 本の列の組）は、台帳の正準形が中の列と列の並びの両方を整列して書くため
            #   元の並びに戻せない。予測はこの欄を使わない（tools/v39.py three_answers は gen だけを読む）。この二つの欄を除いた全部を比べる
            if _strip(cd0) != _strip(pre):
                chk["hash_mismatch"] += 1
                if len(chk["examples"]) < 3:
                    cd = _strip(cd0)
                    pre_s = _strip(pre)
                    diff = {}
                    for k in sorted(set(cd) | set(pre_s)):
                        if cd.get(k) != pre_s.get(k):
                            a, b = cd.get(k), pre_s.get(k)
                            if isinstance(a, dict) and isinstance(b, dict):
                                ks = [x for x in sorted(set(a) | set(b)) if a.get(x) != b.get(x)]
                                ex = []
                                for x in ks[:2]:
                                    ax, bx = a.get(x), b.get(x)
                                    if isinstance(ax, dict) and isinstance(bx, dict):
                                        ex.append((x, {y: [json.dumps(ax.get(y))[:200], json.dumps(bx.get(y))[:200]] for y in set(ax) | set(bx) if ax.get(y) != bx.get(y)}))
                                    elif isinstance(ax, list) and isinstance(bx, list):
                                        ex.append((x, {"長さ": [len(ax), len(bx)], "違う位置": [i for i in range(min(len(ax), len(bx))) if ax[i] != bx[i]][:3],
                                                       "最初の違い": [json.dumps(ax[i])[:600] + " ||| " + json.dumps(bx[i])[:600] for i in range(min(len(ax), len(bx))) if ax[i] != bx[i]][:1]}))
                                    else:
                                        ex.append((x, json.dumps(ax)[:200], json.dumps(bx)[:200]))
                                diff[k] = {"違う鍵の数": len(ks), "例": ex}
                            else:
                                diff[k] = [json.dumps(a)[:300], json.dumps(b)[:300]]
                    chk["examples"].append({"種類": "指紋", "trial": t, "違う欄": diff})
            ai = loop._agent_input(wt, st)
            out, _pend = loop.predict(ai, st, config, Random(loop._rng_seed(agent, t)))
            o = outcome(out, wt.held_out_edge)
            pe = row.get("predicted_edge")
            real = {"R": row.get("R_used"), "答え": (pe or {}).get("predicate") if pe else None,
                    "引数": list((pe or {}).get("arguments") or []) if pe else None, "支持": row.get("support_at_adoption")}
            chk["pred_compared"] += 1
            same = (o["R"] == real["R"] and o["答え"] == real["答え"] and (o["引数"] or None) == (real["引数"] or None)
                    and (real["支持"] is None or o["支持"] == real["支持"]))
            if not same:
                chk["pred_mismatch"] += 1
                if len(chk["examples"]) < 20:
                    chk["examples"].append({"種類": "予測", "trial": t, "やり直し": {k: o[k] for k in ("R", "答え", "引数", "支持")}, "本物": real})
            if t in targets:
                rows_out.append(counterfactual(t, st, pre, wt, ai, config, agent, last, targets[t], o, arm, seed, sw))
        if strict:
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        _clear_caches(loop)
        # この試行の終わりの状態で、U でない席を控える
        post = tr["post"]
        shp = {_key(k): v for k, v in post["slot_history"].items()}
        for name, dd in post["definitions"].items():
            for c in dd["constituents"]:
                k2 = (name, c["slot_index"])
                s = seat_st(c["alive"], k2, shp)
                if s != "U":
                    last[(name, dd["registered_at"], c["slot_index"], c["registered_at"])] = {
                        "st": s, "pred": c["relation"]["predicate"] if c["alive"] else None, "hist": shp.get(k2), "t": t}
    chk["秒"] = round(time.time() - t0, 1)
    os.makedirs(os.path.join(out_dir, arm), exist_ok=True)
    with open(os.path.join(out_dir, arm, f"seed{seed:03d}.restore.jsonl"), "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False, default=lambda x: sorted(x) if isinstance(x, frozenset) else str(x)) + "\n")
    json.dump(chk, open(os.path.join(out_dir, arm, f"seed{seed:03d}.check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return chk


def counterfactual(t, st, pre, wt, ai, config, agent, last, tinfo, base_out, arm, seed, sw):
    import abm.loop as loop
    from dataclasses import replace
    R = tinfo["R"]
    rec = {"seed": seed, "trial": t, "R": R, "本物の答え（やり直し）": base_out}
    dd = pre["definitions"].get(R)
    if dd is None or base_out["R"] != R:
        rec["除いた理由"] = "選ばれた定義がやり直しと違う" if dd is not None else "定義が状態に無い"
        return rec
    sh = st.slot_history
    sig_rows = [c for c in dd["constituents"] if sw.IDS.get(c["relation"]["relation_id"]) == "sig"]
    u_sig = [c for c in sig_rows if seat_st(c["alive"], (R, c["slot_index"]), sh) == "U"]
    rec["シールの席の数"] = len(sig_rows)

    def redo(c):
        k = (R, dd["registered_at"], c["slot_index"], c["registered_at"])
        L = last.get(k)
        if L is None:
            return None, "U でない状態が記録に無い（生まれたときから U）"
        d = st.definitions[R]
        rows = []
        for row in d.constituents:
            if row.slot_index == c["slot_index"] and L["st"] == "F":
                row = replace(row, alive=True, relation=replace(row.relation, predicate=L["pred"]))
            rows.append(row)
        nd = replace(d, constituents=tuple(rows))
        sh2 = dict(sh)
        if L["hist"] is not None:
            sh2[(R, c["slot_index"])] = dict(L["hist"]) if isinstance(L["hist"], dict) else frozenset(L["hist"])
        elif L["st"] == "H":
            return None, "H の履歴の欄が記録に無い"
        defs2 = dict(st.definitions)
        defs2[R] = nd
        st2 = replace(st, definitions=defs2, slot_history=sh2)
        out, _p = loop.predict(ai, st2, config, Random(loop._rng_seed(agent, t)))
        o = outcome(out, wt.held_out_edge)
        o["戻した状態"] = {"st": L["st"], "pred": L["pred"], "hist": L["hist"], "その状態の試行": L["t"]}
        return o, None

    if not u_sig:
        rec["除いた理由"] = "やり直しの状態でシールの席が U でない"
        return rec
    c = u_sig[0]
    o, why = redo(c)
    rec["シール"] = o if o is not None else {"取り出せない": why}
    rec["シールの席"] = c["slot_index"]
    # 比べ：シール以外の U の席
    others = [x for x in dd["constituents"] if sw.IDS.get(x["relation"]["relation_id"]) != "sig"
              and seat_st(x["alive"], (R, x["slot_index"]), sh) == "U"]
    rec["シール以外の U の席の数"] = len(others)
    ok = [x for x in others if last.get((R, dd["registered_at"], x["slot_index"], x["registered_at"])) is not None]
    rec["シール以外の U の席のうち最後の状態を取り出せる数"] = len(ok)
    if ok:
        x = Random(f"ctrl|{arm}|{seed}|{t}").choice(sorted(ok, key=lambda y: y["slot_index"]))
        o2, why2 = redo(x)
        rec["比べ"] = o2 if o2 is not None else {"取り出せない": why2}
        rec["比べの席"] = x["slot_index"]
    return rec


def one(args):
    root, cell, seed, targets, out_dir = args
    import sweep
    import v3_run
    arm = os.path.basename(root.rstrip("/"))
    scratch = tempfile.mkdtemp(prefix=f"sealrestore_{arm}_{seed}_")
    task, cfg = make_task(root, cell, seed, scratch)
    box = {}

    def fake_run_one(tk):
        box["chk"] = analysis((tk, cfg, root, cell, seed, targets, out_dir, arm))
        return {"cell": tk["cell"], "seed": tk["seed"]}

    sweep.run_one = fake_run_one
    v3_run.worker(task)
    return {"arm": arm, "seed": seed, **{k: v for k, v in box["chk"].items() if k != "examples"}}


def main():
    out_dir, root, tdir = sys.argv[1], sys.argv[2], sys.argv[3]
    seeds = [int(x) for x in sys.argv[4:]] or list(range(1, 21))
    arm = os.path.basename(root.rstrip("/"))
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        s = int(os.path.basename(p)[4:7])
        if s not in seeds:
            continue
        cell = os.path.basename(os.path.dirname(p))
        tg = {}
        for r in csv.DictReader(open(os.path.join(tdir, arm, f"seed{s:03d}.answers.csv"), encoding="utf-8")):
            if r["door"] == "1" and r["shop_cue"] == "e" and r["hit"] == "0" and r["seal_map"] == "U":
                tg[int(r["trial"])] = {"R": r["R"]}
        jobs.append((root, cell, s, tg, out_dir))
    ctx = get_context("spawn")
    with ctx.Pool(min(int(os.environ.get("SR_WORKERS", "2")), len(jobs)), maxtasksperchild=1) as pool:
        res = pool.map(one, jobs, chunksize=1)   # ★ 一つのプロセスに一本だけ（差し替えを二度入れないため）
    os.makedirs(os.path.join(out_dir, arm), exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, arm, "checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = {k: sum(r[k] for r in res) for k in ("trials", "pred_compared", "pred_mismatch", "hash_mismatch", "args_unrestored")}
    print(arm, json.dumps(tot, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
