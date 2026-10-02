"""一つずつの評価の確かめ（委任書「シールを戻す確かめ」2026-10-02 昼の 3）。★ 記録を読むだけ。模型は変えない。写しの上だけで測る。
問い：同じ役割の席が二つあるとき、--cf-learn の評価（tools/cflearn.py variants_correct：席を一つずつ薄くした写しで最終的な答えをやり直す）は、
  二つの席それぞれにいくつの価値を付けるか。片方を薄くしたあと、もう片方を測り直すと変わるか。
小さな例の作り方（仮の決定）：本物の記録から、--cf-learn が「シールの席を薄くすると答えが外れる」と評価した試行を選び、その試行の
  予測の直前の状態と提示の場面を作り直す（tools/sealrestore.py と同じ。作り直した状態で予測が本物と同じことを確かめる）。その写しの上で、
  ・場面：シールの関係 s とその link の関係 k（attach(s, 根)）に、同じ述語・同じ引数の複製 s′（新しい ID）と k′＝attach(s′, 根) を足す。
  ・定義：シールの行と link の行に、同じ中身の複製の行（新しい席の番号、関係 ID は元の ID ＋ "_dup"、k′ の引数は s′ と同じ根）を足し、
    履歴の欄・席の記録（v39_seats）・merit・embed・exceptions も同じ値で複製する（m_alloc は ＋2）。
  これで「同じ情報を持つ二つのシールの席」を作る。
測るもの（どれも正解は渡さない。乱数は本物の予測と同じ種）：
  A 複製の前：元のシールの席の評価（記録の --cf-learn と同じになることを確かめる）。
  B 複製の後：元のシールの席と複製のシールの席の、それぞれの評価（今の状態・H・U のときに答えが当たるか）。
  C 元のシールの席を U まで薄くした後：複製のシールの席の評価。
  D 複製のシールの席を U まで薄くした後：元のシールの席の評価。
  E 両方を U まで薄くしたときの答え。
  シールの席は、--cf-learn の記録の席（引数で 種:試行:席 と渡す）。定義にシールの行が二つ以上あることがあるため。
使い方  python3.12 tools/dupseal.py <出力の .json> <腕の根> <種:試行:席> …"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import replace
from random import Random

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def analysis(job):
    import abm.loop as loop
    import abm.world as wmod
    import cflearn
    import shopworld as sw
    import sealrestore as sr
    import v39
    from extrap_reader import iter_run
    task, cfg, root, cell, seed, slots, out = job
    trials = sorted(slots)
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    config = sr.configs_of(cfg, task)[cfg["agent_ids"][0]]
    agent = cfg["agent_ids"][0]
    wrapped = wmod.generate_trial
    base = wrapped
    while getattr(base, "__module__", None) != "abm.world":
        nxt = [c.cell_contents for c in (base.__closure__ or ()) if getattr(getattr(c, "cell_contents", None), "__name__", "") == "generate_trial"]
        base = nxt[0]
    wmod.generate_trial = base
    it = iter_run(root, cell, seed, check_hash=True)
    first = next(it)
    wmod.generate_trial = wrapped
    argmap, scenes = {}, {}
    res = []

    def chain():
        yield first
        yield from it

    for tr in chain():
        t = tr["t"]
        if t > max(trials):
            break
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
        scenes.setdefault(wt.target_graph_partial.graph_id, wt.target_graph_partial)
        if t in trials and tr["pre"] is not None:
            st, _bad = sr.restore_state(tr["pre"], argmap, scenes)
            res.append(one_case(st, tr, wt, config, agent, seed, t, sw, v39, cflearn, loop, slots))
        if fl.get("strict_pc"):
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        sr._clear_caches(loop)
    return res


def one_case(st, tr, wt, config, agent, seed, t, sw, v39, cflearn, loop, slots):
    from abm.domains import Relation, RelationGraph
    seed_rng = loop._rng_seed(agent, t)
    ai = loop._agent_input(wt, st)
    out, _p = loop.predict(ai, st, config, Random(seed_rng))
    R = out.trace.get("R_used")
    held = wt.held_out_edge
    rec = {"seed": seed, "trial": t, "R": R, "開示あり": tr["disclosed"], "本物の R_used": tr["row"].get("R_used")}
    if R is None or R != tr["row"].get("R_used"):
        rec["除いた理由"] = "やり直しの選ばれた定義が本物と違う"
        return rec
    d = st.definitions[R]
    want = slots.get(t)
    srow = next((r for r in d.constituents if r.slot_index == want and sw.IDS.get(r.relation.relation_id) == "sig"), None)
    rec["シールの行の数"] = sum(1 for r in d.constituents if sw.IDS.get(r.relation.relation_id) == "sig")
    lrow = next((r for r in d.constituents if sw.IDS.get(r.relation.relation_id) == "link"), None)
    info = sw.INFO[wt.G_star.graph_id]
    scene = wt.target_graph_partial
    sid, kid = info["sig_id"], info["link_id"]
    srel = next((r for r in scene.relations if r.relation_id == sid), None)
    krel = next((r for r in scene.relations if r.relation_id == kid), None)
    if srow is None or srel is None:
        rec["除いた理由"] = "指定の席がシールの行でない、又は提示にシールの関係が無い"
        return rec

    def vc(state, aiX):
        # ★ 今の状態の答え（variants_correct の「実際の答え」）は、その写しで出し直した答え
        actual, _p = loop.predict(aiX, state, config, Random(seed_rng))
        r = cflearn.variants_correct(state, aiX, config, R, t, held, actual.prediction, loop.predict, seed_rng)
        return {str(k): {"今の状態": v[0], "当たり": v[1]} for k, v in r.items()}

    A = vc(st, ai)
    rec["A 複製の前（全席）"] = A
    rec["シールの席"] = srow.slot_index
    rec["本物の答えが当たり"] = cflearn._correct(out.prediction, held)
    # 場面の複製
    s2 = Relation(relation_id=sid + "_dup", predicate=srel.predicate, arguments=tuple(srel.arguments), attributes=dict(srel.attributes))
    extra = [s2]
    if krel is not None:
        extra.append(Relation(relation_id=kid + "_dup", predicate=krel.predicate,
                              arguments=tuple(s2.relation_id if a == sid else a for a in krel.arguments), attributes=dict(krel.attributes)))
    scene2 = RelationGraph(scene.graph_id, entities=scene.entities, relations=tuple(scene.relations) + tuple(extra))
    wt2 = replace(wt, target_graph_partial=scene2)
    ai2 = loop._agent_input(wt2, st)
    # 定義の複製
    mx = max(r.slot_index for r in d.constituents)
    ns = mx + 1
    rows = list(d.constituents)
    new_s = replace(srow, slot_index=ns, relation=replace(srow.relation, relation_id=srow.relation.relation_id + "_dup"))
    rows.append(new_s)
    add = [(srow, ns)]
    if lrow is not None:
        nl = mx + 2
        rows.append(replace(lrow, slot_index=nl, relation=replace(lrow.relation, relation_id=lrow.relation.relation_id + "_dup",
                                                                  arguments=tuple(new_s.relation.relation_id if a == srow.relation.relation_id else a
                                                                                  for a in lrow.relation.arguments))))
        add.append((lrow, nl))
    d2 = replace(d, constituents=tuple(rows), m_alloc=d.m_alloc + len(add))
    defs = dict(st.definitions)
    defs[R] = d2
    sh = dict(st.slot_history)
    seats = dict(st.v39_seats)
    merit = dict(st.merit)
    embed = dict(st.embed)
    exc = dict(st.exceptions)
    for row, n in add:
        if (R, row.slot_index) in sh:
            sh[(R, n)] = sh[(R, row.slot_index)]
        if (R, row.slot_index) in seats:
            seats[(R, n)] = seats[(R, row.slot_index)]
        if (R, row.slot_index) in exc:
            exc[(R, n)] = exc[(R, row.slot_index)]
        for k in list(merit):
            if k[0] == R and k[1] == row.slot_index:
                merit[(R, n, k[2])] = replace(merit[k], slot_index=n)
        for k in list(embed):
            if k[0] == R and k[1] == row.slot_index:
                embed[(R, n, k[2])] = replace(embed[k], slot_index=n)
    st2 = replace(st, definitions=defs, slot_history=sh, v39_seats=seats, merit=merit, embed=embed, exceptions=exc)
    out2, _p = loop.predict(ai2, st2, config, Random(seed_rng))
    rec["B 複製の後の答えが当たり"] = cflearn._correct(out2.prediction, held)
    B = vc(st2, ai2)
    rec["B 複製の後（全席）"] = B
    rec["複製のシールの席"] = ns

    def thin(state, slot):
        s0 = v39.seat_state(state.definitions[R], next(r for r in state.definitions[R].constituents if r.slot_index == slot), state.slot_history)
        if s0 == "F":
            state, _ = v39._convert(state, "FH", R, slot, t)
            s0 = "H"
        if s0 == "H":
            state, _ = v39._convert(state, "HU", R, slot, t)
        return state

    stC = thin(st2, srow.slot_index)
    rec["C 元のシールを U にした後（全席）"] = vc(stC, ai2)
    stD = thin(st2, ns)
    rec["D 複製のシールを U にした後（全席）"] = vc(stD, ai2)
    stE = thin(stC, ns)
    outE, _p = loop.predict(ai2, stE, config, Random(seed_rng))
    rec["E 両方を U にした答えが当たり"] = cflearn._correct(outE.prediction, held)
    return rec


def one(args):
    root, cell, seed, trials, out = args
    import sweep
    import v3_run
    import sealrestore as sr
    scratch = tempfile.mkdtemp(prefix=f"dupseal_{seed}_")
    task, cfg = sr.make_task(root, cell, seed, scratch)
    box = {}

    def fake_run_one(tk):
        box["res"] = analysis((tk, cfg, root, cell, seed, trials, out))   # trials は {試行: 席}
        return {"cell": tk["cell"], "seed": tk["seed"]}

    sweep.run_one = fake_run_one
    v3_run.worker(task)
    return box["res"]


def main():
    import glob
    from multiprocessing import get_context
    out, root = sys.argv[1], sys.argv[2]
    want = {}
    for x in sys.argv[3:]:
        s, t, sl = x.split(":")
        want.setdefault(int(s), {})[int(t)] = int(sl)
    cell = os.path.basename(os.path.dirname(sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done")))[0]))
    jobs = [(root, cell, s, ts, out) for s, ts in sorted(want.items())]
    with get_context("spawn").Pool(1, maxtasksperchild=1) as pool:
        res = [r for rs in pool.map(one, jobs, chunksize=1) for r in rs]
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    for r in res:
        print(json.dumps({k: v for k, v in r.items() if not k.startswith(("A ", "B 複製の後（", "C ", "D "))}, ensure_ascii=False, default=str))
        if "シールの席" in r:
            ss, ds = str(r["シールの席"]), str(r.get("複製のシールの席"))
            print("  A 元", r["A 複製の前（全席）"].get(ss), "| B 元", r["B 複製の後（全席）"].get(ss), "B 複製", r["B 複製の後（全席）"].get(ds),
                  "| C 複製", r["C 元のシールを U にした後（全席）"].get(ds), "| D 元", r["D 複製のシールを U にした後（全席）"].get(ss))


if __name__ == "__main__":
    main()
