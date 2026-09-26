"""★ 種ごとの数を、結果で分ける（2026-09-26 アストラさんの指示。読むだけ。D の表から）。
★ 対象は D の分布の図（tools/D_hist_spoke.R）と同じ：中心的過程（通過群 L=3・6）を通り、内の世界偽の率 5% 以下、内外とも主張 20 本以上（世界不明は除く）。
★ 呼び名（2026-09-26 から。群S／群N とは分ける）
   外で当たる定義 ＝ 外の世界偽の率 5% 以下
   外で外す定義   ＝ 外の世界偽の率 50% 以上
   あわせて、それぞれの中の「群S（またぎ有り、matagi=1）」の本数も出す。
★ 物差し：旧（①≧1／①=0）・新（話した）・副（話して開示）・新①（走行全体）・新②（後半 t>=870 の主張だけ）。表に列が無い物差しは飛ばす。
使い方  python3.12 per_seed_outcome.py <出力csv> <表csv>…"""
import csv, sys, collections, statistics as st
out, files = sys.argv[1], sys.argv[2:]
MS = [("", "旧"), ("_spk", "新"), ("_fb", "副"), ("_all", "新①全体"), ("_late", "新②後半")]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


rows = []
for f in files:
    T = list(csv.DictReader(open(f, encoding="utf-8")))
    arm = T[0]["arm"]
    seeds = sorted({r["seed"] for r in T})
    for s, lab in MS:
        if "rate_in" + s not in T[0] or all(num(r["rate_in" + s]) is None for r in T):
            continue
        for L in (6, 3):
            C = collections.defaultdict(collections.Counter)
            for r in T:
                if r[f"L{L}"] != "1":
                    continue
                ri, ro, ni, no = num(r["rate_in" + s]), num(r["rate_out" + s]), num(r["n_in" + s]), num(r["n_out" + s])
                if None in (ri, ro, ni, no) or ri > 0.05 or ni < 20 or no < 20:
                    continue
                c = C[r["seed"]]; c["対象"] += 1
                for k, ok in (("外で当たる", ro <= 0.05), ("外で外す", ro >= 0.5)):
                    if ok:
                        c[k] += 1
                        if r["matagi"] == "1":
                            c[k + "_群S"] += 1
            for sd in seeds:
                c = C[sd]
                rows.append({"arm": arm, "L": L, "物差し": lab, "seed": sd, "対象": c["対象"],
                             "外で当たる": c["外で当たる"], "外で当たる_群S": c["外で当たる_群S"],
                             "外で外す": c["外で外す"], "外で外す_群S": c["外で外す_群S"]})
with open(out, "w", newline="", encoding="utf-8") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("腕 | L | 物差し | 種 | 対象 計 | 外で当たる 計（群S）種ごと中央 [最小〜最大] | 外で外す 計（群S）種ごと中央 [最小〜最大]")
key = lambda r: (r["arm"], r["L"], r["物差し"])
for k in dict.fromkeys(key(r) for r in rows):
    R = [r for r in rows if key(r) == k]
    g = lambda c: f"{sum(r[c] for r in R)}（{sum(r[c + '_群S'] for r in R)}）{st.median([r[c] for r in R]):g} [{min(r[c] for r in R)}〜{max(r[c] for r in R)}]"
    print(f"{k[0]} | {k[1]} | {k[2]} | {len(R)} | {sum(r['対象'] for r in R)} | {g('外で当たる')} | {g('外で外す')}")
print("->", out)
