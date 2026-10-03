"""既定の答えとの食い違い（委任書 2026-10-03「既定の答えとの食い違い」）。★ 記録を読むだけ。走行も模型の変更もしない。
U の席の既定の答え：tools/v39.py fill_v39 の U の席と同じ計算（tools/v39.py:493〜516）。
  位置の形（slot_signature）に合う生きた語彙 → 同じ階（_same_order）に絞る → p̂（予測の直前の状態の p_hat）で most_frequent（local_lambda は設定のまま、
  局所の数は無し）。名が無い、又は同点（tied）なら「期待なし」。その試行の正解や、後で更新された頻度は使わない。
期待一致率＝既定の答えと一致した U の席の数 ÷（既定の答えが決まり、写り先が見えている関係の U の席の数）。写り先が見えていない（伏せた位置・
  写りの表に無い＝役割を特定できない）U の席は分母に入れない。分母 0 は未定義（None）。比べる相手は写り先の関係の述語。
シールの席だけの一致・不一致も別の欄（シールの U の席で、写り先が見えていて期待が決まるもの）。
出力（種ごと）：
  <出力>/<腕>/seed<種>.trials.jsonl：答えた試行ごと（当たり・開示・ドアか・日・選ばれた定義・支持の割合・その定義の期待一致率とシールの一致）。
  <出力>/<腕>/seed<種>.cands.jsonl.gz：ドアが問われて答えた試行の候補ごと（tools/selcands.py one_trial と同じ、期待一致率の欄を足したもの）。
  <出力>/<腕>/seed<種>.check.json：確かめ（ドアの試行は作り直した予測が本物と同じこと。ほかの試行は選ばれた定義が状態にあること）。
使い方  python3.12 tools/udefault.py <出力の場所> <腕の走行根> [種 …]（並列 UD_WORKERS、既定 1）"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys
import tempfile
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def expectation(d, al, st, scene, config, stt, kinds):
    """候補の定義 d と照合 al について、U の席の既定の答えと写り先の名の一致を数える。"""
    from abm.domains import RelationGraph
    from abm.filling import _is_higher, _predicate_has_signature, _same_order, most_frequent, slot_signature
    rm = al.relation_mapping
    vis = {r.relation_id: r for r in scene.relations}
    dg = RelationGraph("definition", relations=tuple(c.relation for c in d.constituents))
    dids = {c.relation.relation_id for c in d.constituents}
    allp = tuple(st.p_hat.alive_vocab)
    hop = config.higher_order_predicates
    n_u = n_map = n_det = n_ok = 0
    s_det = s_ok = 0
    no_exp = 0
    for c in d.constituents:
        rid = c.relation.relation_id
        if stt[rid] != "U":
            continue
        n_u += 1
        tgt = rm.get(rid)
        if tgt not in vis:
            continue
        n_map += 1
        sig = slot_signature(c.relation, dg)
        pool = frozenset(p for p in allp if _predicate_has_signature(p, sig, scene, dg))
        want_higher = _is_higher(c.relation, dids)
        pool = frozenset(p for p in pool if _same_order(p, want_higher, hop))
        pred, tied = most_frequent(pool, st.p_hat, config.local_lambda, None)
        if pred is None or tied:
            no_exp += 1
            continue
        n_det += 1
        ok = pred == vis[tgt].predicate
        n_ok += ok
        if kinds.get(rid) == "シール":
            s_det += 1
            s_ok += ok
    return {"U の席": n_u, "U の席（写り先が見えている）": n_map, "U の席（期待なし）": no_exp, "期待一致率の分母": n_det, "期待一致率の分子": n_ok,
            "期待一致率": (n_ok / n_det) if n_det else None,
            "シールの U の席（期待が決まり写り先が見えている）": s_det, "シールの一致": s_ok,
            "シール": ("なし" if s_det == 0 else ("一致" if s_ok == s_det else ("不一致" if s_ok == 0 else "一部")))}


def light(pre, R, argmap):
    """選ばれた定義 R だけを状態の dict から戻す（tools/sealrestore.py restore_state と同じ戻し方の、その定義・その定義の席の履歴・p̂ の部分だけ）。
    全部を戻すと記憶が大きい後半で遅いため。ドアの試行では、全部を戻した結果と同じ値になることを確かめる（check の「軽い道の食い違い」）。"""
    import roletarget_recompute as rr
    import sealrestore as sr
    from types import SimpleNamespace
    from abm.definition import FrequencyTable
    dd = pre["definitions"].get(R)
    if dd is None:
        return None, None
    d, _b = rr._restore_def(dd, argmap)
    pref = repr(R)
    sh = {}
    for k, v in pre.get("slot_history", {}).items():
        if k.startswith("(" + pref + ","):
            sh[sr._key(k)] = dict(v) if isinstance(v, dict) else frozenset(v)
    ph = pre["p_hat"]
    p_hat = FrequencyTable(counts=dict(ph["counts"]), total=ph["total"], lambda_mix=ph["lambda_mix"], alive_vocab=frozenset(ph["alive_vocab"]))
    return d, SimpleNamespace(slot_history=sh, p_hat=p_hat)


def light_mark(pre, R, argmap, scene, config, v39, sc, sw, pred_by_id, door_ids, role_ids):
    d, st = light(pre, R, argmap)
    if d is None:
        return None, "選ばれた定義が状態に無い"
    sh = st.slot_history
    graph, al = v39.map_v39(d, sh, scene)
    if al is None:
        return None, "選ばれた定義の照合ができない"
    stt = {r.relation.relation_id: v39.seat_state(d, r, sh) for r in d.constituents}
    n = v39.n_FH(d, sh)
    sup = sum(1 for r in d.constituents if stt[r.relation.relation_id] != "U" and r.relation.relation_id in al.relation_mapping)
    kinds = {r.relation.relation_id: sc.kind_of(r.relation.relation_id, pred_by_id, sw.IDS, door_ids, role_ids) for r in d.constituents}
    e = expectation(d, al, st, scene, config, stt, kinds)
    v39.unregister(graph)
    return {"支持の割合": sup / n if n else None, **{k: e[k] for k in ("期待一致率", "期待一致率の分母", "シール")}}, None


def analysis(task, cfg, root, cell, seed, out_dir, arm):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    import abm.world as wmod
    import shopworld as sw
    import sealrestore as sr
    import selcands as sc
    import v39
    import v310be
    from extrap_reader import iter_run
    sc.EXTRA[:] = [expectation]
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    config = sr.configs_of(cfg, task)[cfg["agent_ids"][0]]
    agent = cfg["agent_ids"][0]
    wrapped = wmod.generate_trial
    base = wrapped
    while getattr(base, "__module__", None) != "abm.world":
        base = [c.cell_contents for c in (base.__closure__ or ()) if getattr(getattr(c, "cell_contents", None), "__name__", "") == "generate_trial"][0]
    wmod.generate_trial = base
    it = iter_run(root, cell, seed, check_hash=True)
    first = next(it)
    wmod.generate_trial = wrapped
    argmap, scenes, pred_by_id, door_ids, role_ids = {}, {}, {}, set(), set()
    os.makedirs(os.path.join(out_dir, arm), exist_ok=True)
    ft = open(os.path.join(out_dir, arm, f"seed{seed:03d}.trials.jsonl"), "w", encoding="utf-8")
    fc = gzip.open(os.path.join(out_dir, arm, f"seed{seed:03d}.cands.jsonl.gz"), "wt", encoding="utf-8")
    chk = {"答えた試行": 0, "ドアの試行": 0, "予測が本物と違う": 0, "一位が本物の選びと違う": 0, "一位でやり直した答えが本物と違う": 0,
           "選ばれた定義が状態に無い": 0, "選ばれた定義の照合ができない": 0, "軽い道の食い違い": 0, "軽い道の食い違いの例": []}
    t0 = time.time()

    def chain():
        yield first
        yield from it

    for tr in chain():
        t = tr["t"]
        wt = tr["world"]
        for r in wt.G_star.relations:
            argmap.setdefault(r.relation_id, tuple(r.arguments))
            pred_by_id.setdefault(r.relation_id, r.predicate)
        info = sw.INFO[wt.G_star.graph_id]
        door_ids.add(info["door_id"])
        for r in wt.G_star.relations:
            if r.predicate in ("supported", "carried") and len(r.arguments) == 1:
                role_ids.add(r.relation_id)
        scenes.setdefault(wt.target_graph_partial.graph_id, wt.target_graph_partial)
        row = tr["row"]
        answered = row.get("coverage") == 1 and (row.get("predicted_edge") or None) is not None
        if answered and tr["pre"] is not None:
            chk["答えた試行"] += 1
            R = row.get("R_used")
            scene = wt.target_graph_partial
            rec = {"seed": seed, "trial": t, "当たり": int(row.get("hit") == 1), "開示": int(tr["disclosed"]), "ドア": bool(info["held_out_is_door"]),
                   "店": info["shop_type"], "日": info["shop_cue"], "R_used": R}
            lm, why = light_mark(tr["pre"], R, argmap, scene, config, v39, sc, sw, pred_by_id, door_ids, role_ids)
            if info["held_out_is_door"]:
                chk["ドアの試行"] += 1
                st, _bad = sr.restore_state(tr["pre"], argmap, scenes)
                cands, _o, c = sc.one_trial(st, wt, row, config, agent, t, info, pred_by_id, door_ids, role_ids, sw, v39, v310be, ar, sme, loop)
                for k, v in (("予測が本物と同じ", "予測が本物と違う"), ("選ばれた定義が今の規則の一位", "一位が本物の選びと違う"),
                             ("一位でやり直した答えが本物と同じ", "一位でやり直した答えが本物と違う")):
                    chk[v] += int(not c[k])
                for cd in cands:
                    fc.write(json.dumps({"seed": seed, "trial": t, "本物の当たり": rec["当たり"], "店": info["shop_type"], "日": info["shop_cue"],
                                         **{k: cd[k] for k in ("R", "生まれた試行", "分子", "分母", "割合", "今の規則の順位", "その定義での答え", "U の席",
                                                               "U の席（写り先が見えている）", "U の席（期待なし）", "期待一致率の分母", "期待一致率の分子",
                                                               "期待一致率", "シールの U の席（期待が決まり写り先が見えている）", "シールの一致", "シール")}},
                                        ensure_ascii=False, default=str) + "\n")
                top = next((cd for cd in cands if cd["R"] == R), None)
                rec.update({"支持の割合": top["割合"] if top else None, **({k: top[k] for k in ("期待一致率", "期待一致率の分母", "シール")} if top else {})})
                full = {k: rec.get(k) for k in ("支持の割合", "期待一致率", "期待一致率の分母", "シール")}
                if lm != full:
                    chk["軽い道の食い違い"] += 1
                    if len(chk["軽い道の食い違いの例"]) < 5:
                        chk["軽い道の食い違いの例"].append({"試行": t, "全部": full, "軽い": lm, "理由": why})
            elif lm is None:
                chk[why] += 1
            else:
                rec.update(lm)
            ft.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if fl.get("strict_pc"):
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        sr._clear_caches(loop)
    ft.close()
    fc.close()
    chk["秒"] = round(time.time() - t0, 1)
    json.dump(chk, open(os.path.join(out_dir, arm, f"seed{seed:03d}.check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return chk


def one(args):
    root, cell, seed, out_dir = args
    import sweep
    import v3_run
    import sealrestore as sr
    arm = os.path.basename(root.rstrip("/"))
    scratch = tempfile.mkdtemp(prefix=f"udefault_{arm}_{seed}_")
    task, cfg = sr.make_task(root, cell, seed, scratch)
    box = {}

    def fake_run_one(tk):
        box["chk"] = analysis(tk, cfg, root, cell, seed, out_dir, arm)
        return {"cell": tk["cell"], "seed": tk["seed"]}

    sweep.run_one = fake_run_one
    v3_run.worker(task)
    return {"arm": arm, "seed": seed, **box["chk"]}


def main():
    from multiprocessing import get_context
    out_dir, root = sys.argv[1], sys.argv[2]
    seeds = [int(x) for x in sys.argv[3:]] or list(range(1, 21))
    assert all(1 <= s <= 20 for s in seeds), "種 21〜40 は読まない"
    arm = os.path.basename(root.rstrip("/"))
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        s = int(os.path.basename(p)[4:7])
        if s in seeds:
            assert not os.path.exists(os.path.join(out_dir, arm, f"seed{s:03d}.trials.jsonl")), "既存の出力を上書きしない"
            jobs.append((root, os.path.basename(os.path.dirname(p)), s, out_dir))
    with get_context("spawn").Pool(min(int(os.environ.get("UD_WORKERS", "1")), len(jobs)), maxtasksperchild=1) as pool:
        res = pool.map(one, jobs, chunksize=1)
    json.dump(res, open(os.path.join(out_dir, arm, f"checks_{'_'.join(map(str, seeds))}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    keys = ("答えた試行", "ドアの試行", "予測が本物と違う", "一位が本物の選びと違う", "一位でやり直した答えが本物と違う", "選ばれた定義が状態に無い",
            "選ばれた定義の照合ができない", "軽い道の食い違い")
    print(arm, json.dumps({k: sum(r[k] for r in res) for k in keys}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
