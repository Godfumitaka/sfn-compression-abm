"""支持で見分けられるか（2026-10-03 の依頼。記録を読むだけ、走行なし）。使い方：separability.py → 標準出力に markdown。
材料：answers.csv（答えた課題ごと：trial・hit・support_ratio）、試行ごとの表 trials.tsv.gz（ドア・通常／例外）、
  N3 の腕は選びの記録 select.jsonl.gz（選ばれた定義の N3）。
AUC：答えた課題の正解（hit＝1）と外れ（hit＝0）を、量の大きい方を正解と見たときの Mann-Whitney の AUC（同点は 0.5）。0.5 なら見分けられない。
門の曲線：支持の割合が t 未満の答えを黙ったことにする（t＝0.50〜1.00、0.05 刻み）。避けられる外れ＝黙りにした外れ、失う正解＝黙りにした正解。
  比べは実際の答え（今の門 0.67 で答えたもの）から。t≦0.67 では今の門で既に黙っている答えは数に入らない（答えた課題だけが材料）。"""
import bisect
import csv
import glob
import gzip
import json
import os
from collections import Counter, defaultdict

H = os.path.expanduser("~")
GROUPS = ("全課題", "ドア・例外", "ドア・通常")
TS = [round(0.5 + 0.05 * k, 2) for k in range(11)]
BINS = [(0.0, 0.5), (0.5, 0.67), (0.67, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0), (1.0, 1.0001)]


def arms():
    out = []
    for wd in (2, 1):
        for r in ("A_L50", "A_L90", "C_L50", "C_L90", "D_t04"):
            n3 = (f"n3_w{wd}_{r}", f"{H}/n3prod/{f'n3_w{wd}_{r}'}", f"{H}/n3prod/tables/n3_w{wd}_{r}")
            if r == "D_t04":
                now = (f"uf_w{wd}_t0.4", f"{H}/ufprod/full/uf_w{wd}_t0.4", f"{H}/ufprod/full/tables/uf_w{wd}_t0.4")
            elif wd == 2:
                now = (f"fg_f050_{r}", f"{H}/fgrid/fg_f050_{r}", f"{H}/fgrid/tables/fg_f050_{r}")
            else:
                now = (f"now_w1_{r}", f"{H}/n3prod/now_w1_{r}", f"{H}/n3prod/tables/now_w1_{r}")
            out.append((wd, r, "N3", *n3))
            out.append((wd, r, "今の規則", *now))
    return out


def auc(pos, neg):
    if not pos or not neg:
        return None
    s = sorted(neg)
    tot = 0.0
    for x in pos:
        lo = bisect.bisect_left(s, x)
        hi = bisect.bisect_right(s, x)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(pos) * len(neg))


def fmt(a):
    return "—" if a is None else f"{a:.3f}"


R = {}
for wd, rule, how, name, side, tab in arms():
    TR = {}
    with gzip.open(f"{tab}/trials.tsv.gz", "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            x = line.rstrip("\n").split("\t")
            TR[(int(x[0]), int(x[1]))] = (x[5] == "1", x[7])
    n3sel = {}
    if how == "N3":
        for p in glob.glob(f"{side}/side/*/seed*.select.jsonl.gz"):
            seed = int(os.path.basename(p)[4:7])
            for line in gzip.open(p, "rt", encoding="utf-8"):
                r = json.loads(line)
                s = [c for c in r["cands"] if c["selected"]]
                if s:
                    n3sel[(seed, r["t"])] = s[0]["N3"]
    data = defaultdict(list)    # 組 → [(支持の割合, 正解か, N3)]
    for ap in glob.glob(f"{side}/side/*/seed*.answers.csv"):
        seed = int(os.path.basename(ap)[4:7])
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            t = int(a["trial"])
            if a["support_ratio"] in ("", None):
                continue
            door, cue = TR[(seed, t)]
            v = (float(a["support_ratio"]), a["hit"] == "1", n3sel.get((seed, t)))
            data["全課題"].append(v)
            if door:
                data["ドア・例外" if cue == "e" else "ドア・通常"].append(v)
    R[(wd, rule, how)] = (name, data)

L = ["# 支持で見分けられるか（記録を読むだけ）\n"]
L.append("## 1 AUC（答えた課題の正解と外れを、量で分ける力。0.5 なら見分けられない）\n")
L.append("| 世界 | 規則 | 選び方 | 走行 | 組 | 正解 | 外れ | AUC（支持の割合） | AUC（選んだ定義の N3） |")
L.append("|---:|---|---|---|---|---:|---:|---:|---:|")
for (wd, rule, how), (name, data) in R.items():
    for g in GROUPS:
        d = data[g]
        pos = [x[0] for x in d if x[1]]
        neg = [x[0] for x in d if not x[1]]
        a2 = None
        if how == "N3":
            a2 = auc([x[2] for x in d if x[1] and x[2] is not None], [x[2] for x in d if not x[1] and x[2] is not None])
        L.append(f"| {wd} | {rule} | {how} | {name} | {g} | {len(pos):,} | {len(neg):,} | {fmt(auc(pos, neg))} | {fmt(a2) if how == 'N3' else ''} |")

L.append("\n## 2 門の曲線（支持の割合が t 未満なら黙る。全課題。避けられる外れ／失う正解。左が世界 2、右が世界 1）\n")
for rule in ("A_L50", "A_L90", "C_L50", "C_L90", "D_t04"):
    for how in ("今の規則", "N3"):
        d2 = R[(2, rule, how)][1]["全課題"]
        d1 = R[(1, rule, how)][1]["全課題"]
        L.append(f"\n### {rule}・{how}（世界 2：答えた {len(d2):,}、外れ {sum(not x[1] for x in d2):,}／世界 1：答えた {len(d1):,}、外れ {sum(not x[1] for x in d1):,}）\n")
        L.append("| t | 世界 2 避けられる外れ | 世界 2 失う正解 | 世界 1 避けられる外れ | 世界 1 失う正解 |\n|---:|---:|---:|---:|---:|")
        for t in TS:
            c2 = Counter(x[1] for x in d2 if x[0] < t - 1e-12)
            c1 = Counter(x[1] for x in d1 if x[0] < t - 1e-12)
            L.append(f"| {t:.2f} | {c2[False]:,} | {c2[True]:,} | {c1[False]:,} | {c1[True]:,} |")

L.append("\n## 3 支持の割合の分布（答えた課題、全課題。正解／外れ）\n")
heads = ["0〜0.5", "0.5〜0.67", "0.67〜0.7", "0.7〜0.8", "0.8〜0.9", "0.9〜1 未満", "1"]
L.append("| 世界 | 規則 | 選び方 | " + " | ".join(heads) + " |\n|---:|---|---|" + "---|" * len(heads))
for (wd, rule, how), (name, data) in R.items():
    d = data["全課題"]
    cells = []
    for lo, hi in BINS:
        sel = [x for x in d if lo - 1e-12 <= x[0] < hi - 1e-12] if hi <= 1.0 else [x for x in d if x[0] >= 1 - 1e-12]
        cells.append(f"{sum(x[1] for x in sel):,}／{sum(not x[1] for x in sel):,}")
    L.append(f"| {wd} | {rule} | {how} | " + " | ".join(cells) + " |")
print("\n".join(L))
