"""C の格子（2026-10-02 朝の委任書）の報告の表と図。後づけの集計だけ。使い方：tables.py <腕…>  → 標準出力に markdown、図は ~/cgrid/fig_*.svg。
材料：tables/<腕>/trials.tsv.gz（全種の試行ごとの表）、<腕>/side/*/seed*.answers.csv、<腕>/side/*/seed*.shop.jsonl（f の格子の tables.py と同じ）。
定め方（仮の決定）：
  率＝その組の課題（例外の日のドア／通常の日のドア）あたりの正解・誤答・棄権の割合（20 種の和で割る）。
  d の値：図の横軸の e × d の d には、試行ごとの表から数えた「ドアが伏せられた試行の割合」（実測）を使う（旗なしは約 0.1）。e も実測（例外の日の試行の割合）。
  シールの席の状態：予測の時点で生きているシールの席（f の格子と同じ作り方）。後半の U の割合＝試行 870〜1739 の U ÷（F＋H＋U）を、全種・全試行で足してから割る。
  例外の日のドアの誤答のうち支持の割合が 1 の割合：answers.csv の support_ratio。"""
import csv
import glob
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict

OUT = os.path.expanduser("~/cgrid")
L50, L90 = 0.01873710622997919, 0.09900039055209096


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


def parse(arm):
    _, rule, lam, e, d = arm.split("_")
    return rule, (L50 if lam == "L50" else L90), lam, float(e[1:]), d[1:]


rows_out, ts_out, POINTS = [], [], []
for arm in sys.argv[1:]:
    rule, lam, lname, e, dname = parse(arm)
    rows = [l.rstrip("\n").split("\t") for l in gzip.open(f"{OUT}/tables/{arm}/trials.tsv.gz", "rt", encoding="utf-8")][1:]
    TR = {(int(r[0]), int(r[1])): r for r in rows}
    bits = sum(float(r[9]) for r in rows) / len(rows)
    d_meas = sum(r[5] == "1" for r in rows) / len(rows)
    e_meas = sum(r[7] == "e" for r in rows) / len(rows)

    def rate(sub):
        n = len(sub)
        c = sum(r[3] == "c" for r in sub)
        w = sum(r[3] == "w" for r in sub)
        a = n - c - w
        return n, c, w, a

    de = rate([r for r in rows if r[5] == "1" and r[7] == "e"])
    dn = rate([r for r in rows if r[5] == "1" and r[7] == "n"])
    bins = defaultdict(Counter)
    nb = Counter()
    late = Counter()
    sup1 = Counter()
    for sp in sorted(glob.glob(f"{OUT}/{arm}/side/*/seed*.shop.jsonl*")):
        seed = int(os.path.basename(sp)[4:7])
        trans = []
        for line in opn(sp):
            r = json.loads(line)
            if r.get("kind") == "shop_seat" and r.get("which") == "sig":
                trans.append((r["trial"], (r["R"], r["reg"], r["slot"]), r["to"]))
        trans.sort(key=lambda x: x[0])
        cur = {}
        j = 0
        for t in range(1740):
            while j < len(trans) and trans[j][0] < t:
                _t, k, to = trans[j]
                if to in ("F", "H", "U"):
                    cur[k] = to
                else:
                    cur.pop(k, None)
                j += 1
            cnt = Counter(cur.values())
            b = min(t // 174, 9)
            for s in ("F", "H", "U"):
                bins[b][s] += cnt[s]
                if t >= 870:
                    late[s] += cnt[s]
            nb[b] += 1
        ap = os.path.join(os.path.dirname(sp), f"seed{seed:03d}.answers.csv")
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            r = TR[(seed, int(a["trial"]))]
            if a["hit"] == "0" and r[5] == "1" and r[7] == "e":
                sr = a["support_ratio"]
                sup1["n"] += 1
                sup1["1"] += sr not in ("", None) and float(sr) >= 1.0 - 1e-12
    u_late = late["U"] / max(1, late["F"] + late["H"] + late["U"])
    wr = de[2] / de[0] if de[0] else float("nan")
    rows_out.append(f"| {arm} | {rule} | {lname} | {e} | {dname} | {e_meas:.3f} | {d_meas:.3f} | {bits:,.0f} | "
                    f"{de[1]/de[0]:.3f}・{wr:.3f}・{de[3]/de[0]:.3f}（{de[1]:,}・{de[2]:,}・{de[3]:,}／{de[0]:,}） | "
                    f"{dn[1]/dn[0]:.3f}・{dn[2]/dn[0]:.3f}・{dn[3]/dn[0]:.3f}（{dn[0]:,}） | {u_late:.3f} | "
                    f"{(sup1['1']/sup1['n']) if sup1['n'] else float('nan'):.3f}（{sup1['1']:,}／{sup1['n']:,}） |")
    ts_out.append(f"| {arm} | " + " | ".join(f"{bins[b]['F']/nb[b]:.1f}／{bins[b]['H']/nb[b]:.1f}／{bins[b]['U']/nb[b]:.1f}" for b in range(10)) + " |")
    POINTS.append(dict(arm=arm, rule=rule, lname=lname, lam=lam, e=e, d=dname, ed=e_meas * d_meas, wr=wr, ul=u_late))

print("### 腕ごと（20 種の和）\n")
print("| 腕 | 規則 | λ | e | d | e（実測） | d（実測：ドアを伏せた試行の割合） | 平均の記憶のビット | 例外の日のドア 正解・誤答・棄権の率（数／課題） | 通常の日のドアの率（課題） | 後半のシールの U の割合 | 例外の日のドアの誤答のうち支持 1 の割合 |")
print("|---|---|---|---:|---|---:|---:|---:|---|---|---:|---|")
print("\n".join(rows_out))
print("\n### シールの席の状態の時間変化（予測の時点で生きているシールの席の数 F／H／U、種あたり・試行あたりの平均、174 試行ずつ）\n")
print("| 腕 | " + " | ".join(f"{b*174}〜" for b in range(10)) + " |\n|---|" + "---|" * 10)
print("\n".join(ts_out))


def svg(path, title, xkey, ykey, ylabel, logx):
    W, H, M = 760, 520, 75
    pts = [p for p in POINTS if not math.isnan(p[ykey])]
    xs = [p[xkey] if xkey == "ed" else p["ed"] / p["lam"] for p in pts]
    for p, x in zip(pts, xs):
        p["_x"] = x
    if logx:
        lo, hi = math.log10(min(xs)), math.log10(max(xs))
        X = lambda v: M + (math.log10(v) - lo) / max(hi - lo, 1e-9) * (W - 2 * M)  # noqa: E731
    else:
        hi = max(xs)
        X = lambda v: M + v / hi * (W - 2 * M)  # noqa: E731
    ymax = max(0.01, max(p[ykey] for p in pts)) * 1.05
    Y = lambda v: H - M - v / ymax * (H - 2 * M)  # noqa: E731
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="white"/><text x="{W/2}" y="24" text-anchor="middle" font-size="15">{title}</text>',
         f'<line x1="{M}" y1="{H-M}" x2="{W-M}" y2="{H-M}" stroke="black"/><line x1="{M}" y1="{M}" x2="{M}" y2="{H-M}" stroke="black"/>',
         f'<text x="{W/2}" y="{H-28}" text-anchor="middle">{"e × d（実測）" if xkey == "ed" else "e × d ÷ λ（実測、対数目盛）"}</text>',
         f'<text x="18" y="{H/2}" text-anchor="middle" transform="rotate(-90 18 {H/2})">{ylabel}</text>']
    for i in range(6):
        if logx:
            xv = 10 ** (lo + (hi - lo) * i / 5)
        else:
            xv = hi * i / 5
        yv = ymax * i / 5
        o.append(f'<text x="{X(xv) if xv > 0 else M}" y="{H-M+16}" text-anchor="middle">{xv:.3g}</text>')
        o.append(f'<text x="{M-6}" y="{Y(yv)+4}" text-anchor="end">{yv:.3f}</text>')
    series = [("C", "L50", "#c0392b", "C・λ＝0.0187"), ("C", "L90", "#2471a3", "C・λ＝0.099"), ("A", "L50", "#7f8c8d", "A・λ＝0.0187（d＝0.5）")]
    for li, (rule, ln, color, label) in enumerate(series):
        ps = sorted((p for p in pts if p["rule"] == rule and p["lname"] == ln), key=lambda p: p["_x"])
        if not ps:
            continue
        if rule == "C":
            o.append('<polyline fill="none" stroke="%s" stroke-width="1.5" points="%s"/>' % (color, " ".join(f"{X(p['_x']):.1f},{Y(p[ykey]):.1f}" for p in ps)))
        for p in ps:
            o.append(f'<circle cx="{X(p["_x"]):.1f}" cy="{Y(p[ykey]):.1f}" r="4" fill="{color}"/>')
            o.append(f'<text x="{X(p["_x"])+5:.1f}" y="{Y(p[ykey])-5:.1f}" fill="{color}" font-size="9">e{p["e"]}/d{p["d"]}</text>')
        o.append(f'<line x1="{W-M-190}" y1="{M+18*li}" x2="{W-M-165}" y2="{M+18*li}" stroke="{color}" stroke-width="2"/><text x="{W-M-160}" y="{M+18*li+4}">{label}</text>')
    o.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(o))


for xkey, logx, tag in (("ed", False, "ed"), ("ed_lam", True, "ed_over_lam")):
    svg(f"{OUT}/fig_{tag}_wrong.svg", "例外の日のドアの誤答率", xkey, "wr", "例外の日のドアの誤答率（課題あたり）", logx)
    svg(f"{OUT}/fig_{tag}_sealU.svg", "後半（試行 870 以降）のシールの席の U の割合", xkey, "ul", "後半のシールの U の割合", logx)
