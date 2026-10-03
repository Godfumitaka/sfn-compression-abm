"""集団化で届いた定義を使った場合の答え（委任書 2026-10-03「集団化で届いた定義」）。★ 記録を読むだけ。走行も模型の変更もしない。
対象：Codex の集団化の一対一（世界 2、A・C、通信あり／なし、集団の種 1〜20）の、例外の日にドアが問われて外れた試行（台帳の coverage＝1・hit≠1・
  held_out_is_door・shop_cue＝e。Codex の analyze_unselected.py の errors の行）。
やり方：tools/selcands.py one_trial と同じ（予測の直前の状態を台帳から作り直し、F・H の席がある定義すべてを候補にして、候補ごとに選びのあとの段を
  やり直す＝「その定義での答え」）。状態の作り直しは tools/sealrestore.py・tools/extrap_reader.py（状態の sha256 を台帳と全試行で比べる）。
  ・集団化の台帳は個体ごと（ledgers/cells/<セル>/seed<世界の種>.jsonl.gz。二体目の世界の種は集団の種＋1000）。
  ・設定と旗は個体版と同じ作り方（sealrestore.make_task。集団の種で作り、世界の種だけ差し替える：tools/v3_run.py _run_collective と同じ）。
    集団化の差し込み（v311c.install：名札・束・通信）は入れない。予測の選びは名札を使わないため。作り直した予測が本物と同じことを毎件確かめる。
  ・届いた定義：Codex の unselected.json の exception_definitions_unselected（名前と生まれた試行）。候補の中で同じ名前・同じ生まれた試行の定義を探す。
出力：<出力>/<条件>.json（外れ一件ごと：選ばれた定義、届いた定義ごとの「その定義での答え」、候補の中に門を通って正しく答える定義があるか）。
使い方  python3.12 tools/colldefs.py <出力の場所> <集団化の走行根（outputs/pilot_…）> <unselected.json>"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from random import Random

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(W, "tools"), W]


def analysis(task, cfg, root, cell, wseed, targets):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    import shopworld as sw
    import sealrestore as sr
    import selcands as sc
    import v39
    import v310be
    from extrap_reader import iter_run
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    config = sr.configs_of(cfg, task)[cfg["agent_ids"][0]]
    agent = cfg["agent_ids"][0]
    import abm.world as wmod
    wrapped = wmod.generate_trial
    base = wrapped
    while getattr(base, "__module__", None) != "abm.world":
        base = [c.cell_contents for c in (base.__closure__ or ()) if getattr(getattr(c, "cell_contents", None), "__name__", "") == "generate_trial"][0]
    wmod.generate_trial = base
    it = iter_run(root, cell, wseed, check_hash=True)
    first = next(it)
    wmod.generate_trial = wrapped
    argmap, scenes, pred_by_id, door_ids, role_ids = {}, {}, {}, set(), set()
    out = []

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
            cands, _o, chk = sc.one_trial(st, wt, tr["row"], config, agent, t, info, pred_by_id, door_ids, role_ids, sw, v39, v310be, ar, sme, loop)
            e = targets[t]
            got = []
            for u in e["exception_definitions_unselected"]:
                c = next((c for c in cands if c["R"] == u["R"] and c["生まれた試行"] == u["R_born"]), None)
                got.append({"R": u["R"], "R_born": u["R_born"], "候補にある": c is not None,
                            **({"今の規則の順位": c["今の規則の順位"], "割合": c["割合"], "分母": c["分母"],
                                "その定義での答え": c["その定義での答え"]} if c else {})})
            good = [c for c in cands if c["その定義での答え"]["当たり"] and c["その定義での答え"]["門を通る"]]
            out.append({"world_seed": wseed, "agent": e["agent"], "trial": t, "selected_R": e["selected_R"], "確かめ": chk,
                        "候補の数": len(cands), "届いた定義": got,
                        "届いた定義で正しく答えられる": any(g.get("その定義での答え", {}).get("当たり") and g["その定義での答え"]["門を通る"] for g in got),
                        "候補の中に正しく答える定義がある": bool(good),
                        "正しく答える候補": [{"R": c["R"], "生まれた試行": c["生まれた試行"], "今の規則の順位": c["今の規則の順位"]} for c in good]})
        if fl.get("strict_pc"):
            import strictpc
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if tr["disclosed"] else ())
        sr._clear_caches(loop)
    return out


def one(args):
    root, cell, group_seed, wseed, targets = args
    import sweep
    import v3_run
    import sealrestore as sr
    scratch = tempfile.mkdtemp(prefix=f"colldefs_{wseed}_")
    task, cfg = sr.make_task(root, cell, group_seed, scratch)
    task = dict(task, seed=wseed)   # ★ tools/v3_run.py _run_collective と同じ：集団の種の task から、世界の種だけ差し替える
    box = {}

    def fake_run_one(tk):
        box["res"] = analysis(tk, cfg, root, cell, wseed, targets)
        return {"cell": tk["cell"], "seed": tk["seed"]}

    sweep.run_one = fake_run_one
    v3_run.worker(task)
    return box["res"]


def main():
    import glob
    from multiprocessing import get_context
    out_dir, root, upath = sys.argv[1], sys.argv[2], sys.argv[3]
    name = os.path.basename(root.rstrip("/"))
    dest = os.path.join(out_dir, name + ".json")
    assert not os.path.exists(dest), ("既存の出力を上書きしない", dest)
    group_seed = int(name.rsplit("_g", 1)[1])
    cell = os.path.basename(os.path.dirname(sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz")))[0]))
    u = json.load(open(upath, encoding="utf-8"))
    by = {}
    for e in u["errors"]:
        if e["held_out_is_door"] and e["shop_cue"] == "e":
            by.setdefault(e["world_seed"], {})[e["trial"]] = e
    jobs = [(root, cell, group_seed, ws, tg) for ws, tg in sorted(by.items())]
    t0 = time.time()
    with get_context("spawn").Pool(1, maxtasksperchild=1) as pool:
        res = [r for rs in pool.map(one, jobs, chunksize=1) for r in rs]
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"条件": name, "対象": sum(len(v) for v in by.values()), "作った": len(res), "秒": round(time.time() - t0, 1), "外れ": res},
              open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    bad = sum(1 for r in res if not all(r["確かめ"].values()))
    print(name, "対象", sum(len(v) for v in by.values()), "作った", len(res), "確かめの食い違い", bad, flush=True)


if __name__ == "__main__":
    main()
