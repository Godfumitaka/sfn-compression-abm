"""U-011 種ファイル生成器（検証版）

v1 の全数値を再現できるかで正しさを確かめる。
式の出所: SPEC §3.2.1 / abm/seed.py:57-88 / abm/world.py:52-56
"""
from math import log2

# ---- 入力（v1 の構成） ----
BAGS = {
    "stone": ["M1","M2","M3","M4"], "water": ["M2","M3","M4"],
    "chain": ["M1","M4"], "rope": ["M4"], "wood": ["M1","M2","M3"],
    "bridge": ["M2","M3"], "wall": ["M1","M3"], "gate": ["M3"], "pipe": ["M3"],
    "river": ["M1","M2"], "road": ["M1","M2"], "cable": ["M1","M2"],
    "wire": ["M1","M2"], "board": ["M2"], "beam": ["M2"], "post": ["M2"],
    "cord": ["M2"], "plank": ["M2"], "rail": ["M2"], "strap": ["M1"],
    "brick": ["M1"], "shaft": ["M1"], "frame": ["M1"], "panel": ["M1"],
    "band": ["M1"], "hook": ["M1"],
}
GLUE = ["near","above","below","beside","behind","inside",
        "outside","across","under","over","along","toward"]
ROLE_UNARY = {"M1":"supported","M2":"carried","M3":"broken","M4":"moved"}
PI_A = {"M1":0.060701,"M2":0.08171,"M3":0.130073,"M4":0.265404}

# (motif, layer) -> (predicate, arity, new_slots)
LAYERS = {
    "M1": {"核一階1":("hold",2,0), "核一階2":("push",2,0), "核高階":("require",2,0),
           "媒介":("stone",2,1), "塔":("allow",2,0), "周縁A":("carry",2,1)},
    "M2": {"核一階1":("carry",2,0), "核一階2":("lift",2,0), "核高階":("cause",2,0),
           "媒介":("stone",2,1), "塔":("allow",2,0), "周縁A":("cold",2,1)},
    "M3": {"核一階1":("break",2,0), "核一階2":("cut",2,0), "核高階":("cause",2,0),
           "媒介":("stone",2,1), "塔":("allow",2,0), "周縁A":("carry",2,1)},
    "M4": {"核一階1":("push",2,0), "核一階2":("turn",2,1), "核高階":("cause",2,0),
           "媒介":("stone",2,1), "塔":("allow",2,0), "周縁A":("hard",2,1)},
}
FIXED_LAYERS = ("核一階1","核一階2","核高階","塔")   # 必ず1本出る
GLUE_MEAN = 2.0

MOTIFS = list(LAYERS)
P_MOTIF = 1.0 / len(MOTIFS)


def one_minus_h(pi_a: float) -> float:
    """abm/world.py:52-56 と同一式。1 - E[1/n]"""
    h = sum((1.0-pi_a)/(3+g) + pi_a/(4+g) for g in (1,2,3)) / 3
    return 1.0 - h


def bag_size(m):
    return sum(1 for _, ms in BAGS.items() if m in ms)


def compute_Z():
    """Z = 核一階2 + 周縁A + 媒介1 + glue2 + 高階1 + 塔1 + 役割ユナリー1"""
    n_core1st = 2; n_higher = 1; n_tower = 1; n_med = 1; n_role = 1
    mean_pi = sum(PI_A.values())/len(PI_A)
    return n_core1st + mean_pi + n_med + GLUE_MEAN + n_higher + n_tower + n_role


def expected_counts():
    """述語ごとの 1 試行あたり期待出現回数"""
    cnt = {}
    def add(p, v): cnt[p] = cnt.get(p, 0.0) + v
    for m in MOTIFS:
        for layer in FIXED_LAYERS:
            add(LAYERS[m][layer][0], P_MOTIF * 1.0)
        add(LAYERS[m]["周縁A"][0], P_MOTIF * PI_A[m])
        add(ROLE_UNARY[m], P_MOTIF * 1.0)
        bs = bag_size(m)
        for w, ms in BAGS.items():
            if m in ms:
                add(w, P_MOTIF * (1.0/bs))
        for g in GLUE:
            add(g, P_MOTIF * (GLUE_MEAN/len(GLUE)))
    return cnt


def build():
    Z = compute_Z()
    cnt = expected_counts()
    marginal = {p: c/Z for p, c in cnt.items()}
    constituents = []
    for m in MOTIFS:
        for layer in ("核一階1","核一階2","核高階","媒介","塔","周縁A"):
            pred, arity, new_slots = LAYERS[m][layer]
            rate = cnt[pred]
            ell = -log2(rate/Z)
            c = 1 + 3*arity - 3*new_slots
            a = (ell + c)/ell
            if layer == "媒介":
                pi = 1.0/bag_size(m)
            elif layer == "周縁A":
                pi = PI_A[m]
            else:
                pi = 1.0
            u = a * pi * one_minus_h(PI_A[m])
            constituents.append(dict(motif=m, predicate=pred, layer=layer,
                                     arity=arity, new_slots=new_slots, c=c,
                                     rate=rate, ell=ell, a=a, pi=pi, u=u))
    return Z, marginal, constituents


if __name__ == "__main__":
    Z, marginal, cons = build()
    print(f"Z = {Z:.6f}   (v1: 8.134472)")
    print(f"marginal 総和 = {sum(marginal.values()):.10f}   (1 であるべき)")
    print(f"異なり述語数 = {len(marginal)}   (v1: 54)")
    for m in MOTIFS:
        print(f"one_minus_h[{m}] = {one_minus_h(PI_A[m]):.6f}")
