"""★ 種ごとの数（2026-09-26 アストラさんの指示）。読むだけ。D の表（tools/defs_table_spoke.py の出力）から。
★ 群は所見記録 §118 の名のとおり：P＝通過群（t1739 生存・新θ8）／S＝神話の形（またぎ≥1・非通過）／N＝抽象の形（またぎ0・非通過）。
★ 種（seed）ごと・4 セルを合わせた本数。t1739 に生存している定義（alive=1）と、消えた定義も含めた全体の両方を出す。
使い方  python3.12 per_seed_spoke.py <出力csv> <表csv>…"""
import csv, sys, collections, statistics as st
out, files = sys.argv[1], sys.argv[2:]
rows = []
for f in files:
    C = collections.defaultdict(collections.Counter)
    arm = None
    for r in csv.DictReader(open(f, encoding="utf-8")):
        arm = r["arm"]; sd = r["seed"]
        C[sd]["全体"] += 1; C[sd]["全体_" + r["grp"]] += 1
        if r["alive"] == "1":
            C[sd]["生存"] += 1; C[sd]["生存_" + r["grp"]] += 1
    for sd in sorted(C):
        c = C[sd]
        rows.append({"arm": arm, "seed": sd, "生存": c["生存"], "生存_P通過群": c["生存_P"], "生存_S神話の形": c["生存_S"],
                     "生存_N抽象の形": c["生存_N"], "全体": c["全体"], "全体_S神話の形": c["全体_S"], "全体_N抽象の形": c["全体_N"]})
with open(out, "w", newline="", encoding="utf-8") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("腕 | 種の数 | 種ごとの中央（最小〜最大）：生存 ／ 生存 S 神話の形 ／ 生存 N 抽象の形 ／ 生存 P 通過群")
for arm in dict.fromkeys(r["arm"] for r in rows):
    R = [r for r in rows if r["arm"] == arm]
    f = lambda k: f"{st.median([r[k] for r in R]):g}（{min(r[k] for r in R)}〜{max(r[k] for r in R)}）"
    print(f"{arm} | {len(R)} | {f('生存')} ／ {f('生存_S神話の形')} ／ {f('生存_N抽象の形')} ／ {f('生存_P通過群')}")
print("->", out)
