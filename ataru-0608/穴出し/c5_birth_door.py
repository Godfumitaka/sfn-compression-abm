"""穴出しの候補 5：お店の世界で、混ざった材料（土台の場面と今の場面でドアの述語が違う）から定義が生まれるとき、
ドア（答える位置）の席と、その上の構造（ドアの親・祖先）が定義から落ちるか（後づけの集計。走行はしない）。
材料：side/<セル>/seed<種>.jsonl の kind=birth（試行 t・土台の場面 base_written_at・m_alloc）と、
  side/<セル>/seed<種>.routing.jsonl の kind=m1（同じ試行・同じ R の、席ごとの mapped_to＝今の場面の関係 ID）。
  ドアの ID・祖先の ID・ドアの述語・ドアが伏せられたかは、場面を走行と同じ作り方で作り直して取る（hole/shopgen.py、研究者の側）。
分け方：今の場面のドアが伏せられた（席に写せない）／ドアの述語が土台と今で同じ／違う（混ざった材料）。
数えるもの：ドアの席がある誕生の割合、ドアの祖先（親から根まで）の席の数、定義の席の数（m_alloc）。
使い方：c5_birth_door.py <世界 1|2> <腕の置き場所>…"""
import glob
import gzip
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopgen  # noqa: E402

WORLD = int(sys.argv[1])
seed_obj = shopgen.setup(WORLD)
import shopworld  # noqa: E402


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


SCENES = {}


def scenes(run_seed):
    if run_seed not in SCENES:
        out = {}
        for t, tr in shopgen.trials(run_seed, 1740, seed_obj):
            info = shopworld.INFO[tr.G_star.graph_id]
            by_id = {r.relation_id: r for r in tr.G_star.relations}
            parent = {a: r.relation_id for r in tr.G_star.relations for a in r.arguments if a in by_id}
            anc = []
            x = info["door_id"]
            while x in parent:
                x = parent[x]
                anc.append(x)
            vis = {r.relation_id for r in tr.target_graph_partial.relations}
            out[t] = {"door": info["door_id"], "pred": by_id[info["door_id"]].predicate, "hidden": info["door_id"] not in vis,
                      "anc": anc, "type": info["shop_type"], "cue": info["shop_cue"], "sig": info["sig_id"], "link": info["link_id"]}
        SCENES[run_seed] = out
    return SCENES[run_seed]


print(f"### 世界 {WORLD}\n")
print("| 腕 | 分け方 | 誕生 | ドアの席がある | ドアの祖先の席の数の平均（祖先の数） | 定義の席の数の中央値 |\n|---|---|---:|---:|---|---:|")
EX = []
SEAL = defaultdict(Counter)
for root in sys.argv[2:]:
    arm = os.path.basename(root.rstrip("/"))
    agg = defaultdict(lambda: Counter())
    seats_n = defaultdict(list)
    anc_n = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.routing.jsonl*"))):
        seed = int(os.path.basename(p)[4:7])
        sdir = os.path.dirname(p)
        sj = next(q for q in (os.path.join(sdir, f"seed{seed:03d}.jsonl"), os.path.join(sdir, f"seed{seed:03d}.jsonl.gz")) if os.path.exists(q))
        births = {}
        for line in opn(sj):
            r = json.loads(line)
            if r.get("kind") == "birth":
                births[(r["trial"], r["R"])] = r
        S = scenes(seed)
        for line in opn(p):
            r = json.loads(line)
            if r.get("kind") != "m1" or r.get("was_extension") or (r["trial"], r["R"]) not in births:
                continue
            t, b = r["trial"], r["base_written_at"]
            st, sb = S[t], S[b]
            if st["hidden"]:
                cls = "今の場面のドアが伏せられた"
            elif st["pred"] == sb["pred"]:
                cls = "ドアの述語が同じ"
            else:
                cls = "ドアの述語が違う（混ざった材料）"
            mapped = {s.get("mapped_to") for s in r["seats"]}
            sk = "シールの日が同じ" if st["cue"] == sb["cue"] else "シールの日が違う"
            SEAL[(arm, sk)]["n"] += 1
            SEAL[(arm, sk)]["sig"] += st["sig"] in mapped
            SEAL[(arm, sk)]["link"] += st["link"] in mapped
            has = st["door"] in mapped
            na = sum(a in mapped for a in st["anc"])
            agg[cls]["n"] += 1
            agg[cls]["door"] += has
            anc_n[cls].append((na, len(st["anc"])))
            seats_n[cls].append(len(r["seats"]))
            if cls.startswith("ドアの述語が違う") and len(EX) < 3:
                EX.append((arm, seed, t, b, st["pred"], sb["pred"], has, na, len(st["anc"]), len(r["seats"])))
    for cls in ("ドアの述語が同じ", "ドアの述語が違う（混ざった材料）", "今の場面のドアが伏せられた"):
        a = agg[cls]
        if not a["n"]:
            continue
        an = anc_n[cls]
        print(f"| {arm} | {cls} | {a['n']:,} | {a['door']:,}（{a['door'] / a['n']:.1%}） | "
              f"{statistics.fmean(x for x, _ in an):.2f}（{statistics.fmean(y for _, y in an):.1f}） | {statistics.median(seats_n[cls])} |")
print("\n| 腕 | 誕生の材料の二つの場面 | 誕生 | シールの席がある | link の席がある |\n|---|---|---:|---:|---:|")
for (arm, sk), a in sorted(SEAL.items()):
    print(f"| {arm} | {sk} | {a['n']:,} | {a['sig']:,}（{a['sig'] / a['n']:.1%}） | {a['link']:,}（{a['link'] / a['n']:.1%}） |")
print("\n例（ドアの述語が違う誕生）：")
for e in EX:
    print(f"- {e[0]} 種 {e[1]}：試行 {e[2]} に土台の試行 {e[3]} から誕生。ドアの述語 今 {e[4]}・土台 {e[5]}。ドアの席 {'あり' if e[6] else 'なし'}、"
          f"ドアの祖先の席 {e[7]}／{e[8]}、定義の席 {e[9]}")
