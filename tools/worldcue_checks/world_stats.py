"""世界 v4（--world-cue）の場面の確かめ（委任書 2）：手がかりの割合、手がかりの関係が一度も伏せられていないこと、
中身の変わる席の述語が手がかりと必ず対応していること、それ以外は今の世界と同じであること。模型は動かさない（世界を作るだけ）。
使い方  python3.12 tools/worldcue_checks/world_stats.py <種の並び 1,2,…> <試行数> [縦の確率]"""
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import abm.world as w  # noqa: E402
from abm.seed import load_seed  # noqa: E402
import worldcue  # noqa: E402

seeds = [int(x) for x in sys.argv[1].split(",")]
T = int(sys.argv[2])
p = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
seed = load_seed(str(ROOT / "seeds/U-011_seed_v3a2.json"))
orig_gen = w.generate_trial
C = collections.Counter()
bad = collections.Counter()
for s in seeds:
    for t in range(T):
        o = orig_gen(s, t, ["agent"], seed=seed, holdout_include_second_order=True)
        c = worldcue.cue_trial(orig_gen, s, t, ["agent"], seed=seed, holdout_include_second_order=True, p_upright=p)
        info = worldcue.INFO[c.G_star.graph_id]
        C["場面"] += 1
        C[info["cue"]] += 1
        cues = [r for r in c.G_star.relations if r.predicate in (worldcue.CUE_UP, worldcue.CUE_LAT)]
        if len(cues) != 1:
            bad["手がかりの関係が一本でない"] += 1
        if c.held_out_edge.predicate in (worldcue.CUE_UP, worldcue.CUE_LAT):
            bad["手がかりの関係が伏せられた"] += 1
        if not any(r.relation_id == cues[0].relation_id for r in c.target_graph_partial.relations):
            bad["手がかりの関係が見えていない"] += 1
        want = worldcue.CUE_UP if info["cue"] == "upright" else worldcue.CUE_LAT
        if cues[0].predicate != want:
            bad["手がかりの述語と記録が違う"] += 1
        if c.held_out_edge.relation_id != o.held_out_edge.relation_id or c.motif != o.motif or c.u_coins != o.u_coins:
            bad["伏せ辺・型・硬貨が今の世界と違う"] += 1
        orel = {r.relation_id: r for r in o.G_star.relations}
        crel = {r.relation_id: r for r in c.G_star.relations if r.relation_id != cues[0].relation_id}
        if set(orel) != set(crel):
            bad["関係の ID の集まりが違う"] += 1
        for rid, r in crel.items():
            x = orel[rid]
            if r.arguments != x.arguments:
                bad["引数（骨組み）が違う"] += 1
            T_ = next((k for k, v in info["switch"].items() if v == rid), None)
            if T_ is None:
                if r.predicate != x.predicate:
                    bad["中身の変わる席でない関係の述語が違う"] += 1
            else:
                C["中身の変わる席"] += 1
                C[f"席_{T_}_{info['cue']}"] += 1
                ok = (r.predicate == x.predicate) if info["cue"] == "upright" else (r.predicate == worldcue.SWITCH_NEW[T_])
                if not ok:
                    bad["中身の変わる席の述語が手がかりと対応しない"] += 1
                if info["cue"] == "lateral" and r.predicate == x.predicate:
                    bad["横なのに述語が変わっていない"] += 1
        if len(info["switch"]) != 2:
            bad["場面の中身の変わる席が二つでない"] += 1
        if info["held_out_switch"] is not None:
            C["伏せ辺が中身の変わる席"] += 1
            C[f"伏せ辺が中身の変わる席_{info['cue']}"] += 1
print({"種": seeds, "試行": T, "縦の確率": p})
print(dict(C))
print("縦の割合", round(C["upright"] / C["場面"], 4), "横の割合", round(C["lateral"] / C["場面"], 4))
print("破れ", dict(bad) if bad else "なし")
