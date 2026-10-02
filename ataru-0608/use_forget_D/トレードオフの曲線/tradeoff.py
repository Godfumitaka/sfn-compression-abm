"""トレードオフの曲線（2026-10-02 の委任書、記録の解析だけ。新しい走行はしない）。
答える門のしきい値 g を 0.67・0.70・0.75・0.80・0.85・0.90・0.95・1.00 に変えたとして、支持の割合が g 未満の答えを黙ったことにして数える。
材料：
  ~/ufprod/door/<腕>/side/*/seed*.door.jsonl（--dump-door：選ばれた定義の 支持・F＋H、答えたか）
  answers.csv（同じ置き場所。支持の割合の突き合わせだけに使う）
  試行ごとの表（段 1 の ~/ufprod/full/tables、又は 12 腕の ~/ufprod/tables）：正解・誤答・棄権、ドア、通常／例外
決め方：
  支持の割合が g 未満 ⇔ 支持 × 100 ＜ g(百分率) × (F＋H)（整数で比べる。今の門 ceil(0.67 ×（F＋H））と g＝0.67 で同じになる）。
  g で黙りにするのは、実際に答えた課題（正解か誤答）だけ。もともとの棄権はそのまま。
  無作為に黙らせた場合の期待値：同じ腕の、実際に答えた課題（g＝0.67、全種）から、同じ数 k を無作為に黙らせたときの避ける誤答
    ＝ k × 誤答 ÷ 答えた数（乱数は使わない）。全課題の組・ドア通常・ドア例外の組それぞれで、その組の答えた課題を比べる集団にする。
  種ごとの散らばり：種ごとの値の平均・標準偏差（母標準偏差）・最小・最大。
出力：tradeoff.md（表）、tradeoff_by_seed.tsv（種ごと）、図 2 枚（SVG）。"""
import csv
import glob
import gzip
import json
import os
import statistics
from collections import defaultdict

HOME = os.path.expanduser("~")
OUT = os.path.join(HOME, "ufprod/tradeoff")
ARMS = [("uf_w2_t0.4", "full/tables"), ("uf_w1_t0.4", "full/tables"), ("uf_w2_t0.25", "tables"), ("uf_w2_t0.6", "tables")]
GS = [67, 70, 75, 80, 85, 90, 95, 100]
GROUPS = ["全課題", "ドア・通常", "ドア・例外"]


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


res = {}          # (腕, g, 組) → [c, w, a]
seed_res = {}     # (腕, g, 組, 種) → [c, w, a]
check = defaultdict(int)
for arm, tdir in ARMS:
    TR = {}
    with gzip.open(os.path.join(HOME, "ufprod", tdir, arm, "trials.tsv.gz"), "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            x = line.rstrip("\n").split("\t")
            TR[(int(x[0]), int(x[1]))] = (x[3], x[5] == "1", x[7])
    for p in sorted(glob.glob(os.path.join(HOME, "ufprod/door", arm, "side/*/seed*.door.jsonl*"))):
        seed = int(os.path.basename(p)[4:7])
        ans = {}
        ap = os.path.join(os.path.dirname(p), f"seed{seed:03d}.answers.csv")
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            ans[int(a["trial"])] = a
        for line in opn(p):
            r = json.loads(line)
            t = r["t"]
            o, door, cue = TR[(seed, t)]
            grps = ["全課題"] + ([("ドア・例外" if cue == "e" else "ドア・通常")] if door else [])
            sel = r["sel"]
            if o in ("c", "w"):
                sup, n = sel[2], sel[3]
                a = ans.get(t)
                check["答えた"] += 1
                if a is not None and a["support_ratio"] not in ("", None) and abs(float(a["support_ratio"]) - sup / n) < 1e-9:
                    check["answers.csv と支持の割合が合う"] += 1
            for g in GS:
                if o in ("c", "w") and sup * 100 < g * n:
                    oo = "a"
                else:
                    oo = o
                k = "cwa".index(oo)
                for gr in grps:
                    res.setdefault((arm, g, gr), [0, 0, 0])[k] += 1
                    seed_res.setdefault((arm, g, gr, seed), [0, 0, 0])[k] += 1

seeds = sorted({k[3] for k in seed_res})
os.makedirs(OUT, exist_ok=True)
L = ["# トレードオフの曲線（記録の解析だけ。新しい走行はしない）\n",
     f"突き合わせ：答えた課題 {check['答えた']:,} 件のうち、door 記録の支持の割合が answers.csv の support_ratio と合うのは {check['answers.csv と支持の割合が合う']:,} 件。\n"]
with open(os.path.join(OUT, "tradeoff_by_seed.tsv"), "w", encoding="utf-8") as f:
    f.write("arm\tg\tgroup\tseed\tcorrect\twrong\tabstain\n")
    for (arm, g, gr, s), v in sorted(seed_res.items()):
        f.write(f"{arm}\t{g/100:.2f}\t{gr}\t{s}\t{v[0]}\t{v[1]}\t{v[2]}\n")


def sd(v):
    return f"{statistics.fmean(v):.1f}±{statistics.pstdev(v):.1f}（{min(v)}〜{max(v)}）"


CURVE = {}
for arm, _ in ARMS:
    L.append(f"\n## {arm}\n")
    for gr in GROUPS:
        b = res[(arm, 67, gr)]
        ans_n = b[0] + b[1]
        L.append(f"\n### {gr}（g＝0.67 で答えた {ans_n:,}：正解 {b[0]:,}・誤答 {b[1]:,}）\n")
        L.append("| g | 正解 | 誤答 | 棄権 | 避けた誤答 | 失った正解 | 無作為に同じ数を黙らせた場合の避ける誤答（期待値） | 種ごと：避けた誤答 平均±標準偏差（最小〜最大） | 種ごと：失った正解 |")
        L.append("|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for g in GS:
            v = res[(arm, g, gr)]
            av, lo = b[1] - v[1], b[0] - v[0]
            k = av + lo
            exp = k * b[1] / ans_n if ans_n else 0.0
            sav = [seed_res[(arm, 67, gr, s)][1] - seed_res[(arm, g, gr, s)][1] for s in seeds if (arm, g, gr, s) in seed_res]
            slo = [seed_res[(arm, 67, gr, s)][0] - seed_res[(arm, g, gr, s)][0] for s in seeds if (arm, g, gr, s) in seed_res]
            L.append(f"| {g/100:.2f} | {v[0]:,} | {v[1]:,} | {v[2]:,} | {av:,} | {lo:,} | {exp:.1f} | {sd(sav)} | {sd(slo)} |")
            CURVE[(arm, gr, g)] = (lo, av, exp)
    L.append("\n種ごとの正解・誤答・棄権（全課題、平均±標準偏差（最小〜最大））\n")
    L.append("| g | 正解 | 誤答 | 棄権 |\n|---:|---|---|---|")
    for g in GS:
        cols = [[seed_res[(arm, g, "全課題", s)][i] for s in seeds if (arm, g, "全課題", s) in seed_res] for i in range(3)]
        L.append(f"| {g/100:.2f} | {sd(cols[0])} | {sd(cols[1])} | {sd(cols[2])} |")
open(os.path.join(OUT, "tradeoff.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def svg(path, title, series, group):
    W, H, M = 720, 520, 70
    pts = [CURVE[(arm, group, g)] for arm, _c, _l in series for g in GS]
    xmax = max(1, max(p[0] for p in pts))
    ymax = max(1, max(p[1] for p in pts))
    X = lambda v: M + v / xmax * (W - 2 * M)  # noqa: E731
    Y = lambda v: H - M - v / ymax * (H - 2 * M)  # noqa: E731
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="white"/>', f'<text x="{W/2}" y="24" text-anchor="middle" font-size="15">{title}</text>',
         f'<line x1="{M}" y1="{H-M}" x2="{W-M}" y2="{H-M}" stroke="black"/><line x1="{M}" y1="{M}" x2="{M}" y2="{H-M}" stroke="black"/>',
         f'<text x="{W/2}" y="{H-25}" text-anchor="middle">失った正解（g＝0.67 から、20 種の和）</text>',
         f'<text x="18" y="{H/2}" text-anchor="middle" transform="rotate(-90 18 {H/2})">避けた誤答</text>']
    for i in range(6):
        xv, yv = xmax * i / 5, ymax * i / 5
        o.append(f'<text x="{X(xv)}" y="{H-M+16}" text-anchor="middle">{xv:,.0f}</text><line x1="{X(xv)}" y1="{H-M}" x2="{X(xv)}" y2="{H-M+4}" stroke="black"/>')
        o.append(f'<text x="{M-6}" y="{Y(yv)+4}" text-anchor="end">{yv:,.0f}</text><line x1="{M-4}" y1="{Y(yv)}" x2="{M}" y2="{Y(yv)}" stroke="black"/>')
    for li, (arm, color, label) in enumerate(series):
        cs = [CURVE[(arm, group, g)] for g in GS]
        o.append('<polyline fill="none" stroke="%s" stroke-width="2" points="%s"/>' % (color, " ".join(f"{X(c[0]):.1f},{Y(c[1]):.1f}" for c in cs)))
        o.append('<polyline fill="none" stroke="%s" stroke-width="1" stroke-dasharray="4 3" points="%s"/>' % (color, " ".join(f"{X(c[0]):.1f},{Y(c[2]):.1f}" for c in cs)))
        for g, c in zip(GS, cs):
            o.append(f'<circle cx="{X(c[0]):.1f}" cy="{Y(c[1]):.1f}" r="3.5" fill="{color}"/>')
            o.append(f'<text x="{X(c[0])+5:.1f}" y="{Y(c[1])-5:.1f}" fill="{color}" font-size="10">{g/100:.2f}</text>')
        o.append(f'<line x1="{W-M-170}" y1="{M+18*li}" x2="{W-M-145}" y2="{M+18*li}" stroke="{color}" stroke-width="2"/>'
                 f'<text x="{W-M-140}" y="{M+18*li+4}">{label}</text>')
    o.append(f'<text x="{W-M-170}" y="{M+18*len(series)+6}" font-size="10">点線：同じ数を無作為に黙らせた場合（期待値）</text>')
    o.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(o))


for gr, tag in (("全課題", "all"), ("ドア・例外", "door_exc")):
    svg(os.path.join(OUT, f"fig1_tau0.4_w1w2_{tag}.svg"), f"τ＝0.4：世界 1 と世界 2（{gr}、点の数字は g）",
        [("uf_w2_t0.4", "#c0392b", "世界 2・τ＝0.4"), ("uf_w1_t0.4", "#2471a3", "世界 1・τ＝0.4")], gr)
    svg(os.path.join(OUT, f"fig2_w2_tau_{tag}.svg"), f"世界 2：τ＝0.25・0.4・0.6（{gr}、点の数字は g）",
        [("uf_w2_t0.25", "#27ae60", "世界 2・τ＝0.25"), ("uf_w2_t0.4", "#c0392b", "世界 2・τ＝0.4"), ("uf_w2_t0.6", "#8e44ad", "世界 2・τ＝0.6")], gr)
print("ok", check)
