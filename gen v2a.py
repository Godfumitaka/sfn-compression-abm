"""U-011_seed_v2a を生成する。式は seed_gen.py と同一（v1 を再現済み）。"""
import json
from math import log2
import seed_gen as g

# ---- v2a の構造（写像検証済み） ----
# 部分木 4 つ。各モチーフは隣り合う 2 つを持つ（環状）
SUBTREE = {                     # 名前: (二階述語, 一階述語 2 本)
    "A": ("cause",   ("hold",  "push")),
    "B": ("require", ("carry", "lift")),
    "C": ("enable",  ("break", "cut")),
    "D": ("avert",   ("turn",  "press")),
}
MOTIF_SUBTREES = {"M1": ("A","B"), "M2": ("B","C"), "M3": ("C","D"), "M4": ("D","A")}
THIRD = {"M1":"allow", "M2":"depend", "M3":"prevent", "M4":"block"}   # 三階・モチーフ固有
PERIPHERAL = {"M1":"cold", "M2":"wet", "M3":"hard", "M4":"dry"}       # ★ 他層と重ならない語
ROLE_UNARY = g.ROLE_UNARY
PI_A = {"M1":0.075555,"M2":0.080697,"M3":0.155859,"M4":0.263846}  # u_target を満たすよう解いた
BAGS, GLUE = g.BAGS, g.GLUE
P = 0.25                                                              # モチーフ出現確率

# 1 場面の固定関係数 = 三階1 + 二階2 + 一階4 + 媒介1 + 役割ユナリー1 = 9
Z = 9 + sum(PI_A.values())/4 + 2.0                                    # + 周縁 + glue平均


def layers_of(m):
    """(layer, predicate, new_slots) を返す。実体対は全部分木で共有（新規スロット 0）"""
    s1, s2 = MOTIF_SUBTREES[m]
    out = [("三階", THIRD[m], 0), ("二階1", SUBTREE[s1][0], 0), ("二階2", SUBTREE[s2][0], 0)]
    for i, s in enumerate((s1, s2)):
        for j, p in enumerate(SUBTREE[s][1]):
            out.append((f"一階{i+1}-{j+1}", p, 0))
    out += [("媒介", "stone", 1), ("周縁A", PERIPHERAL[m], 1)]
    return out


def counts():
    c = {}
    add = lambda p, v: c.__setitem__(p, c.get(p, 0.0) + v)
    for m in g.MOTIFS:
        for layer, pred, _ in layers_of(m):
            if layer == "媒介":
                for w, ms in BAGS.items():
                    if m in ms:
                        add(w, P / g.bag_size(m))
            elif layer == "周縁A":
                add(pred, P * PI_A[m])
            else:
                add(pred, P)
        add(ROLE_UNARY[m], P)
        for gl in GLUE:
            add(gl, P * 2.0 / len(GLUE))
    return c


def build():
    cnt = counts()
    marginal = {p: v / Z for p, v in cnt.items()}
    rows = []
    for m in g.MOTIFS:
        for layer, pred, ns in layers_of(m):
            rate = cnt[pred]
            ell = -log2(rate / Z)
            c = 1 + 3 * 2 - 3 * ns
            a = (ell + c) / ell
            pi = (1.0 / g.bag_size(m) if layer == "媒介"
                  else PI_A[m] if layer == "周縁A" else 1.0)
            u = a * pi * g.one_minus_h(PI_A[m])
            rows.append(dict(motif=m, predicate=pred, layer=layer, arity=2,
                             new_slots=ns, c=c, rate=round(rate, 6),
                             ell=round(ell, 4), a=round(a, 4),
                             pi=round(pi, 6), u=round(u, 6)))
    return marginal, rows


def theta_grid(rows):
    """v1 の規則：0 / 4 / 6 / 8 本を切る位置に置く（構成素の重複を含めて数える）。"""
    us = sorted(r["u"] for r in rows)          # ★ 重複を残す
    t2 = round((us[3] + us[4]) / 2, 4)         # 4 本を切る
    t3 = round((us[5] + us[6]) / 2, 4)         # 6 本を切る
    t4 = round(t3 + (t3 - t2), 4)              # 8 本を切る
    t1 = round(us[0] / 2, 4)                   # 0 本
    return [t1, t2, t3, t4], sorted(set(us))


if __name__ == "__main__":
    marg, rows = build()
    grid, us = theta_grid(rows)
    print(f"Z = {Z:.6f}   構成素 {len(rows)} 件   異なり述語 {len(marg)}")
    print(f"marginal 総和 = {sum(marg.values()):.10f}")
    print(f"\n--- M1 の構成素（u 降順）---")
    for r in sorted([r for r in rows if r["motif"] == "M1"], key=lambda r: -r["u"]):
        print(f"  {r['layer']:<8} {r['predicate']:<9} rate={r['rate']:.4f} "
              f"ell={r['ell']:.4f} c={r['c']} a={r['a']:.4f} u={r['u']:.6f}")
    print(f"\n--- u の下端 8 件 ---")
    for u in us[:8]:
        who = [f"{r['motif']}/{r['predicate']}" for r in rows if r["u"] == u]
        print(f"  {u:.6f}  {who}")
    print(f"\n★ θ′ 格子 = {grid}")
    for t in grid:
        print(f"   θ′={t}: u を割る構成素 {sum(1 for r in rows if r['u'] < t)} 本")

    seed = {
        "version": "U-011_seed_v2a",
        "generated": "2026-09-03",
        "assumptions": {
            "reading": "alpha (p̂ = 場面生成の設計値)", "pool": "global",
            "Z": round(Z, 6),
            "Z_composition": "一階4 + 二階2 + 三階1 + 周縁A + 媒介1 + glue2 + 役割ユナリー1",
            "K_ROLE": 1.0, "glue_mean": 2.0,
            "bag_sizes": {m: g.bag_size(m) for m in g.MOTIFS}, "m": 9,
        },
        "bags": BAGS, "glue": GLUE, "role_unary": ROLE_UNARY,
        "canon": {m: "stone" for m in g.MOTIFS}, "pi_A": PI_A,
        "one_minus_h": {m: round(g.one_minus_h(PI_A[m]), 6) for m in g.MOTIFS},
        "theta_grid": grid,
        "marginal": {p: round(v, 8) for p, v in sorted(marg.items(), key=lambda kv: -kv[1])},
        "constituents": rows,
        "motif_structure": {m: {"third": THIRD[m], "subtrees": MOTIF_SUBTREES[m],
                                "peripheral": PERIPHERAL[m]} for m in g.MOTIFS},
        "subtrees": {k: {"higher": v[0], "first_order": list(v[1])} for k, v in SUBTREE.items()},
    }
    with open("/mnt/user-data/outputs/U-011_seed_v2a.json", "w", encoding="utf-8") as fh:
        json.dump(seed, fh, ensure_ascii=False, indent=2)
    print("\n書き出し: U-011_seed_v2a.json")
