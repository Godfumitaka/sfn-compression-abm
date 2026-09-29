"""世界 v4（型の変種、--world-cue）の場面の確かめ（追記 B-2 の検査）：変種の割合、切り替わる関係と変種の対応、
それ以外は今の世界と同じ（関係の ID・引数・切り替わらない関係の述語・伏せ辺の ID・型・硬貨・見えている関係の並び）。模型は動かさない（世界を作るだけ）。
使い方  python3.12 tools/worldvariant_checks/world_stats.py <種の並び 1,2,…> <試行数> [変種 A の確率]"""
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import abm.world as w  # noqa: E402
from abm.seed import load_seed  # noqa: E402
import worldvariant as V  # noqa: E402

seeds = [int(x) for x in sys.argv[1].split(",")]
T = int(sys.argv[2])
p = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
seed = load_seed(str(ROOT / "seeds/U-011_seed_v3a2.json"))
orig_gen = w.generate_trial
C = collections.Counter()
bad = collections.Counter()
for s in seeds:
    for t in range(T):
        o = orig_gen(s, t, ["agent"], seed=seed)
        c = V.variant_trial(orig_gen, s, t, ["agent"], seed=seed, p_a=p)
        info = V.INFO[c.G_star.graph_id]
        C["場面"] += 1
        C[f"変種{info['variant']}"] += 1
        C[f"型{c.motif}_変種{info['variant']}"] += 1
        if c.held_out_edge.relation_id != o.held_out_edge.relation_id or c.motif != o.motif or c.u_coins != o.u_coins:
            bad["伏せ辺の ID・型・硬貨が今の世界と違う"] += 1
        if [r.relation_id for r in c.target_graph_partial.relations] != [r.relation_id for r in o.target_graph_partial.relations]:
            bad["見えている関係の並びが違う"] += 1
        if c.target_graph_partial.entities != o.target_graph_partial.entities or c.G_star.entities != o.G_star.entities:
            bad["物が違う"] += 1
        orel = {r.relation_id: r for r in o.G_star.relations}
        crel = {r.relation_id: r for r in c.G_star.relations}
        if list(orel) != list(crel):
            bad["関係の ID の並びが違う"] += 1
        if len(info["switch"]) != 2:
            bad["切り替わる関係が二つでない"] += 1
        changed = 0
        for rid, r in crel.items():
            x = orel[rid]
            if r.arguments != x.arguments:
                bad["引数（骨組み）が違う"] += 1
            T_ = next((k for k, v in info["switch"].items() if v == rid), None)
            if T_ is None:
                if r.predicate != x.predicate:
                    bad["切り替わらない関係の述語が違う"] += 1
                continue
            C[f"切り替わる関係_{T_}_変種{info['variant']}"] += 1
            if x.predicate != {"T1": "hold", "T2": "break", "T3": "pull", "T4": "wrap"}[T_]:
                bad["切り替わる関係の今の述語が部分木の最初の葉でない"] += 1
            want = x.predicate if info["variant"] == "A" else V.SWITCH_NEW[T_]
            if r.predicate != want:
                bad["切り替わる関係の述語が変種と対応しない"] += 1
            changed += r.predicate != x.predicate
        if changed != (2 if info["variant"] == "B" else 0):
            bad["変種 B で二つとも切り替わっていない、又は変種 A で切り替わった"] += 1
        hs = info["held_out_switch"]
        if hs is not None:
            C["伏せ辺が切り替わる関係"] += 1
            C[f"伏せ辺が切り替わる関係_変種{info['variant']}"] += 1
            if c.held_out_edge.predicate != (V.SWITCH_NEW[hs] if info["variant"] == "B" else o.held_out_edge.predicate):
                bad["伏せ辺の述語が変種と対応しない"] += 1
        elif c.held_out_edge != o.held_out_edge:
            bad["切り替わらない伏せ辺が今と違う"] += 1
print({"種": seeds, "試行": T, "変種 A の確率": p})
print(dict(sorted(C.items())))
print("変種 A の割合", round(C["変種A"] / C["場面"], 4), "変種 B の割合", round(C["変種B"] / C["場面"], 4))
print("破れ", dict(bad) if bad else "なし")
