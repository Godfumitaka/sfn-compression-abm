"""選び間違いの数え上げと、候補の定義ごとの量（委任書「選び間違いの数え上げと、試行 113 の候補の表」2026-10-02 夕方）。
★ 記録を読むだけ。走行も模型の変更もしない。状態の作り直しは tools/sealrestore.py の手順（控えは試行ごとに捨てる）。
対象：腕ごとに、世界 2 の例外の日にドアが問われて答えた試行（外れと正解）。tools/sealmem.py の答えの記録（door＝1・shop_cue＝e）。
候補：予測の直前の状態の、F・H の席がある定義すべて（tools/v39.py select_definition と同じ並べ方を作り直す）。候補ごとに：
  ・定義名・生まれた試行・F/H/U の席の数。ドアの席（対応先が伏せたドアの関係）とシールの席の状態・履歴・写り先。
  ・支持の割合の分子と分母（tools/v39.py select_definition と同じ）。分子の内訳：
      (i) 見えている関係に写った F・H の席（F は名前の一致、H は履歴の名で写る：tools/v39.py _install_candidates）
      (ii) 見えていない位置（提示の関係でない ID）に写った F・H の席（構造だけ）
      (iii) U の席の ID が写りの表に入っている数（--u-struct で U の子を通った対）。分子には入らない。
  ・SME 風の点数：照合の total_score と内訳（score_breakdown。tools/fixorder2.py の map_graphs）。
  ・選択用の点数（GPT の案、仮の決定の数え方）：
      見えている名前の一致＝(i) の数
      引数の対応＝(i) の席の引数のうち、写りの表（物・関係）で写った先の関係の同じ位置の引数に当たる数
      名前どうしの一段のつながり＝(i) の席の親子の組（親の引数が子の関係 ID）で、子の写り先が親の写り先の同じ位置の引数である数
      U の席と見えていない位置には点を与えない。点数＝三つの和。
  ・場面の側の割合：提示の関係のうち、(i) の写り先になった関係の割合。
  ・r：tools/v310be.py rewrite（E の書換・追加・取消のビットと内訳。x＝提示の場面、符号表＝予測の直前の p̂ の符号長）。
  ・今の規則での順位、選ばれたか。
  ・N3（追記 2026-10-02 夕方）＝2S(d,x)÷(S(d,d)＋S(x,x))。S＝名前の一致＋引数の対応＋一段のつながり（減点なし）。
      S(d,x)：名前は見えている関係に写った F・H の席だけ（U は 0 点）、引数とつながりは見えている関係に写った席すべて（U も構造として数える）。
      S(d,d)：恒等の対応。名前＝F・H の席の数、引数＝全部の席の引数の位置の数、つながり＝引数が定義の行である位置の数。
      S(x,x)：提示の関係だけで恒等の対応。名前＝関係の数、引数＝引数の位置の数、つながり＝引数が提示の関係である位置の数。
      N3 での順位（同点は今の規則の順）、N3 で選ばれるか、その定義が今の門（支持が ceil(τ×n)）を通るか。
  ・その定義を使った場合の答え：選びのあとの段（門・投影・穴埋め・答える所。tools/v39.py predict の 604 行目より後と同じ呼び方）を
    その定義でやり直す（乱数は本物の予測と同じ種から新しく作る）。答えの名前・引数、門を通るか、当たるか、ドアの位置に答えたか。
確かめ：作り直した状態で本物と同じ予測になること。実際に選ばれた定義でやり直した答えが本物の答えと同じこと。
出力：<出力>/<腕>/seed<種>.cands.jsonl.gz（候補ごと）、seed<種>.cases.jsonl（試行ごと）、seed<種>.check.json。
使い方  python3.12 tools/selcands.py <出力の場所> <腕の走行根> <sealmem の出力の場所> [種 …]（並列 SC_WORKERS、既定 2）"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import sys
import tempfile
import time
from random import Random

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]

T_PREDS = {"couple", "anchor", "steer", "shield"}
ROOT_PREDS = {"govern", "sustainedby"}


def kind_of(rid, pred_by_id, ids, door_ids, role_ids):
    if ids.get(rid) == "sig":
        return "シール"
    if ids.get(rid) == "link":
        return "link"
    if rid in door_ids:
        return "ドア"
    if rid in role_ids:
        return "役割"
    p = pred_by_id.get(rid)
    if p in ROOT_PREDS:
        return "根"
    if p in T_PREDS:
        return "T 階"
    return "その他"


def answer_with(cand, ai, st, config, rng_seed, v39, ar, sme):
    """tools/v39.py predict の 604 行目より後（選ばれた定義を使う段）を、この候補でやり直す。"""
    from abm.domains import Abstain, EdgePrediction
    ratio, support, d, graph, al, n = cand
    scene = ai.target_graph_partial
    rng = Random(rng_seed)
    if support < ar._need(config.tau_acc, n):
        return Abstain(reason="below_tau"), False
    prediction = sme.project(al, graph, scene, prototype_prior_weight=0.0)
    filling = v39.fill_v39(d, scene, al.entity_mapping, al.relation_mapping, st.slot_history, st.p_hat, config.fill_selection, rng,
                           higher_order_predicates=config.higher_order_predicates, local_lambda=config.local_lambda)
    prediction, _path = v39.fill_decision(prediction, filling, None)
    return prediction, True


def one_trial(st, wt, row_real, config, agent, t, info, pred_by_id, door_ids, role_ids, sw, v39, v310be, ar, sme, loop):
    from dataclasses import replace
    from abm.domains import EdgePrediction
    scene = wt.target_graph_partial
    held = wt.held_out_edge
    vis = {r.relation_id: r for r in scene.relations}
    seed_rng = loop._rng_seed(agent, t)
    ai = loop._agent_input(wt, st)
    out, _p = loop.predict(ai, st, config, Random(seed_rng))
    sh = st.slot_history
    L = v39.code_lengths(st.p_hat)
    scene_ids = set(vis)
    cands = []
    for d in st.definitions.values():
        n = v39.n_FH(d, sh)
        if n == 0:
            continue
        graph, al = v39.map_v39(d, sh, scene)
        if al is None:
            continue
        rm, em = al.relation_mapping, al.entity_mapping
        rows = {r.relation.relation_id: r for r in d.constituents}
        stt = {r.relation.relation_id: v39.seat_state(d, r, sh) for r in d.constituents}
        fh = [r for r in d.constituents if stt[r.relation.relation_id] != "U"]
        support = sum(1 for r in fh if r.relation.relation_id in rm)
        i_vis = [r for r in fh if rm.get(r.relation.relation_id) in vis]
        ii_hid = [r for r in fh if r.relation.relation_id in rm and rm[r.relation.relation_id] not in vis]
        iii_u = sum(1 for r in d.constituents if stt[r.relation.relation_id] == "U" and r.relation.relation_id in rm)
        # 選択用の点数（GPT の案）
        argp = 0
        for r in i_vis:
            tgt = vis[rm[r.relation.relation_id]]
            for k, a in enumerate(r.relation.arguments):
                if k < len(tgt.arguments) and (em.get(a) == tgt.arguments[k] or rm.get(a) == tgt.arguments[k]):
                    argp += 1
        ivis_ids = {r.relation.relation_id for r in i_vis}
        links = 0
        for r in i_vis:
            tgt = vis[rm[r.relation.relation_id]]
            for k, a in enumerate(r.relation.arguments):
                if a in ivis_ids and k < len(tgt.arguments) and rm.get(a) == tgt.arguments[k]:
                    links += 1
        imgs = {rm[r.relation.relation_id] for r in i_vis}
        # ★ N3（追記 2026-10-02 夕方）：N3 ＝ 2S(d,x) ÷ (S(d,d) ＋ S(x,x))。S＝見えている名前の一致＋引数の対応＋一段のつながり（減点なし）。
        #   U の席の名前は 0 点、構造（引数・位置）は数える。伏せた関係はどこにも使わない（場面は提示の関係だけ）。自己の点は恒等の対応。
        mapped_vis = [r for r in d.constituents if rm.get(r.relation.relation_id) in vis]          # F・H・U のうち、見えている関係に写った行
        n_name = sum(1 for r in mapped_vis if stt[r.relation.relation_id] != "U")
        n_arg = 0
        for r in mapped_vis:
            tgt = vis[rm[r.relation.relation_id]]
            for k, a in enumerate(r.relation.arguments):
                if k < len(tgt.arguments) and (em.get(a) == tgt.arguments[k] or rm.get(a) == tgt.arguments[k]):
                    n_arg += 1
        mv_ids = {r.relation.relation_id for r in mapped_vis}
        n_link = 0
        for r in mapped_vis:
            tgt = vis[rm[r.relation.relation_id]]
            for k, a in enumerate(r.relation.arguments):
                if a in mv_ids and k < len(tgt.arguments) and rm.get(a) == tgt.arguments[k]:
                    n_link += 1
        S_dx = n_name + n_arg + n_link
        row_ids = {r.relation.relation_id for r in d.constituents}
        S_dd = (sum(1 for r in d.constituents if stt[r.relation.relation_id] != "U")
                + sum(len(r.relation.arguments) for r in d.constituents)
                + sum(1 for r in d.constituents for a in r.relation.arguments if a in row_ids))
        S_xx = (len(vis) + sum(len(r.arguments) for r in vis.values())
                + sum(1 for r in vis.values() for a in r.arguments if a in vis))
        N3 = 2 * S_dx / (S_dd + S_xx) if (S_dd + S_xx) else 0.0
        try:
            rbits, rparts = v310be.rewrite(st, d.name, scene, L, config, scene_ids)
        except Exception as e:  # noqa
            rbits, rparts = None, {"計算できない": repr(e)[:200]}
        seats = []
        for r in d.constituents:
            rid = r.relation.relation_id
            cid, why = v310be.role_target(d, r, al, scene)
            k = kind_of(rid, pred_by_id, sw.IDS, door_ids, role_ids)
            to_door = (cid == info["door_id"]) or (rm.get(rid) == info["door_id"])
            if k in ("シール", "link", "ドア") or to_door:
                h = sh.get((d.name, r.slot_index))
                seats.append({"席": r.slot_index, "種類": k, "状態": stt[rid], "述語": r.relation.predicate if r.alive else None,
                              "履歴": (dict(h) if hasattr(h, "items") else sorted(h)) if h is not None else None,
                              "写り先": rm.get(rid), "写り先は見えている": rm.get(rid) in vis, "対応先": cid, "ドアに写る": to_door})
        unmatched = {}
        for r in fh:
            if r.relation.relation_id not in rm:
                kk = kind_of(r.relation.relation_id, pred_by_id, sw.IDS, door_ids, role_ids)
                unmatched[kk] = unmatched.get(kk, 0) + 1
        f_ids = {r.relation.relation_id for r in d.constituents if r.alive}
        al2 = replace(al, candidate_projections=tuple(x for x in al.candidate_projections if x in f_ids))
        cands.append({"R": d.name, "生まれた試行": d.registered_at, "F": sum(1 for v in stt.values() if v == "F"),
                      "H": sum(1 for v in stt.values() if v == "H"), "U": sum(1 for v in stt.values() if v == "U"),
                      "分子": support, "分母": n, "割合": support / n, "(i) 見えている関係に写った": len(i_vis),
                      "(ii) 見えていない位置に写った": len(ii_hid), "(iii) U の席の写り": iii_u,
                      "SME の点数": al.total_score, "SME の内訳": dict(al.score_breakdown),
                      "選択用の点数": len(i_vis) + argp + links, "選択用の内訳": {"名前の一致": len(i_vis), "引数の対応": argp, "一段のつながり": links},
                      "場面の側の割合": len(imgs) / len(vis) if vis else None, "r": rbits, "r の内訳": rparts,
                      "N3": N3, "N3 の分子 S(d,x)": S_dx, "N3 の分子の内訳": {"名前": n_name, "引数": n_arg, "つながり": n_link},
                      "自己の点 S(d,d)": S_dd, "自己の点 S(x,x)": S_xx,
                      "門を通る（今の門、支持の割合）": support >= ar._need(config.tau_acc, n),
                      "写らなかった F・H の席（種類別）": unmatched, "ドア・シール・link の席": seats,
                      "_cand": (support / n, support, d, graph, al2, n)})
        v39.unregister(graph)
    cands.sort(key=lambda c: (-c["割合"], -c["分母"], -c["生まれた試行"], c["R"]))
    for k, c in enumerate(cands):
        c["今の規則の順位"] = k + 1
        c["選ばれた"] = (k == 0)
    # N3 の順位（同点は今の規則の順。仮の決定）
    for k, c in enumerate(sorted(cands, key=lambda c: (-c["N3"], c["今の規則の順位"]))):
        c["N3 での順位"] = k + 1
        c["N3 で選ばれる"] = (k == 0)
        pred, gate = answer_with(c.pop("_cand"), ai, st, config, seed_rng, v39, ar, sme)
        e = pred.edge if isinstance(pred, EdgePrediction) else None
        c["その定義での答え"] = {"門を通る": gate, "黙り": e is None, "理由": getattr(pred, "reason", None) if e is None else None,
                             "答え": e.predicate if e else None, "ドアの位置に答えた": bool(e) and tuple(e.arguments) == tuple(held.arguments),
                             "当たり": bool(e) and e.predicate == held.predicate and tuple(e.arguments) == tuple(held.arguments)}
    real_e = out.prediction.edge if isinstance(out.prediction, EdgePrediction) else None
    top = cands[0] if cands else None
    if "selectn3" in sys.modules:   # --select-n3 の走行（作り直しで tools/selectn3.py install_n3 が入った。--select-log は入れない）
        # ★ 2026-10-03（走行の係）：--select-n3 の走行では、本物の選びは N3 の一位（tools/selectn3.py の並べ方：N3 → 席の数 → 新しさ → 名前）。
        #   確かめの「一位」をその並べ方の一位にする（候補ごとの「その定義での答え」の定め方は変えない）
        top = min(cands, key=lambda c: (-c["N3"], -c["分母"], -c["生まれた試行"], c["R"])) if cands else None
    chk = {"予測が本物と同じ": (out.trace.get("R_used") == row_real.get("R_used")
                           and (real_e.predicate if real_e else None) == ((row_real.get("predicted_edge") or {}).get("predicate"))),
           "選ばれた定義が今の規則の一位": bool(top) and top["R"] == out.trace.get("R_used"),
           "一位でやり直した答えが本物と同じ": bool(top) and top["その定義での答え"]["答え"] == (real_e.predicate if real_e else None)
                                 and top["その定義での答え"]["黙り"] == (real_e is None)}
    return cands, out, chk


def analysis(job):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    import abm.world as wmod
    import shopworld as sw
    import sealrestore as sr
    import v39
    import v310be
    from extrap_reader import iter_run
    task, cfg, root, cell, seed, targets, out_dir, arm = job
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
    fc = gzip.open(os.path.join(out_dir, arm, f"seed{seed:03d}.cands.jsonl.gz"), "wt", encoding="utf-8")
    fs = open(os.path.join(out_dir, arm, f"seed{seed:03d}.cases.jsonl"), "w", encoding="utf-8")
    chk = {"対象": len(targets), "作った試行": 0, "予測が本物と違う": 0, "一位が本物の選びと違う": 0, "一位でやり直した答えが本物と違う": 0, "例": []}
    t0 = time.time()

    def chain():
        yield first
        yield from it

    last_t = max(targets) if targets else -1
    for tr in chain():
        t = tr["t"]
        if t > last_t:
            break
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
        if t in targets and tr["pre"] is not None:
            st, _bad = sr.restore_state(tr["pre"], argmap, scenes)
            cands, out, c = one_trial(st, wt, tr["row"], config, agent, t, info, pred_by_id, door_ids, role_ids, sw, v39, v310be, ar, sme, loop)
            chk["作った試行"] += 1
            for k, v in (("予測が本物と同じ", "予測が本物と違う"), ("選ばれた定義が今の規則の一位", "一位が本物の選びと違う"),
                         ("一位でやり直した答えが本物と同じ", "一位でやり直した答えが本物と違う")):
                if not c[k]:
                    chk[v] += 1
                    if len(chk["例"]) < 10:
                        chk["例"].append({"試行": t, "確かめ": k})
            hit = targets[t]
            for cd in cands:
                fc.write(json.dumps({"seed": seed, "trial": t, "本物の当たり": hit, "店": info["shop_type"], **cd}, ensure_ascii=False, default=str) + "\n")
            good = [cd for cd in cands if cd["その定義での答え"]["当たり"] and cd["その定義での答え"]["門を通る"]]
            fs.write(json.dumps({"seed": seed, "trial": t, "店": info["shop_type"], "本物の当たり": hit, "候補の数": len(cands),
                                 "選ばれた": cands[0]["R"] if cands else None, "選ばれた割合": cands[0]["割合"] if cands else None,
                                 "正しく答える候補": [cd["R"] for cd in good],
                                 "正しく答える候補の最上位": ({"R": good[0]["R"], "順位": good[0]["今の規則の順位"], "割合": good[0]["割合"],
                                                             "分母": good[0]["分母"], "生まれた試行": good[0]["生まれた試行"],
                                                             "シール": [s for s in good[0]["ドア・シール・link の席"] if s["種類"] == "シール"],
                                                             "写らなかった F・H の席（種類別）": good[0]["写らなかった F・H の席（種類別）"]} if good else None)},
                                ensure_ascii=False, default=str) + "\n")
        if fl.get("strict_pc"):
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        sr._clear_caches(loop)
    fc.close()
    fs.close()
    chk["秒"] = round(time.time() - t0, 1)
    json.dump(chk, open(os.path.join(out_dir, arm, f"seed{seed:03d}.check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return chk


def one(args):
    root, cell, seed, targets, out_dir = args
    import sweep
    import v3_run
    import sealrestore as sr
    arm = os.path.basename(root.rstrip("/"))
    scratch = tempfile.mkdtemp(prefix=f"selcands_{arm}_{seed}_")
    task, cfg = sr.make_task(root, cell, seed, scratch)
    box = {}

    def fake_run_one(tk):
        box["chk"] = analysis((tk, cfg, root, cell, seed, targets, out_dir, arm))
        return {"cell": tk["cell"], "seed": tk["seed"]}

    sweep.run_one = fake_run_one
    v3_run.worker(task)
    return {"arm": arm, "seed": seed, **{k: v for k, v in box["chk"].items() if k != "例"}}


def main():
    from multiprocessing import get_context
    out_dir, root, smdir = sys.argv[1], sys.argv[2], sys.argv[3]
    seeds = [int(x) for x in sys.argv[4:]] or list(range(1, 21))
    arm = os.path.basename(root.rstrip("/"))
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        s = int(os.path.basename(p)[4:7])
        if s not in seeds:
            continue
        cell = os.path.basename(os.path.dirname(p))
        tg = {int(r["trial"]): int(r["hit"]) for r in csv.DictReader(open(os.path.join(smdir, arm, f"seed{s:03d}.answers.csv"), encoding="utf-8"))
              if r["door"] == "1" and r["shop_cue"] == os.environ.get("SC_CUE", "e")
              and (os.environ.get("SC_ONLY_MISS") != "1" or r["hit"] == "0")}   # ★ 2026-10-03（走行の係）：日（SC_CUE）と外れだけ（SC_ONLY_MISS）
        jobs.append((root, cell, s, tg, out_dir))
    with get_context("spawn").Pool(min(int(os.environ.get("SC_WORKERS", "2")), len(jobs)), maxtasksperchild=1) as pool:
        res = pool.map(one, jobs, chunksize=1)
    os.makedirs(os.path.join(out_dir, arm), exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, arm, "checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = {k: sum(r[k] for r in res) for k in ("対象", "作った試行", "予測が本物と違う", "一位が本物の選びと違う", "一位でやり直した答えが本物と違う")}
    print(arm, json.dumps(tot, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
