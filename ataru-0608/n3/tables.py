"""N3 の走行の報告の表（2026-10-02 夜の委任書）。後づけの集計だけ。使い方：tables.py  → 標準出力に markdown。
組：N3 の腕（~/n3prod/n3_*）と、同じ機械の今の規則の腕（世界 2 の A・C は ~/fgrid/fg_f050_*、D は ~/ufprod/full/uf_w?_t0.4、
  世界 1 の A・C は ~/n3prod/now_w1_*）。
数えるもの（腕ごと、20 種の和）：平均の記憶のビット、全課題・ドア通常・ドア例外の正解・誤答・棄権、例外の日のドアの誤答のうち支持の割合 1 の割合、
  今の規則の腕と同じ種・同じ試行で並べた移り変わり（正解→外れ、正解→黙り、外れ→正解、外れ→黙り、黙り→正解、黙り→外れ）。
  ★ 学習を含む走行なので、二つの腕は試行ごとに記憶が違う。移り変わりは同じ試行の結果を並べただけ。
  N3 の腕の選びの記録（select.jsonl.gz）から：答えた試行のうち、N3 の一位が今の規則の一位と違った割合（その腕の記憶の上で）。"""
import csv
import glob
import gzip
import json
import os
from collections import Counter

H = os.path.expanduser("~")
PAIRS = []
for wd in (2, 1):
    for r in ("A_L50", "A_L90", "C_L50", "C_L90"):
        base = f"{H}/fgrid/tables/fg_f050_{r}" if wd == 2 else f"{H}/n3prod/tables/now_w1_{r}"
        bside = f"{H}/fgrid/fg_f050_{r}" if wd == 2 else f"{H}/n3prod/now_w1_{r}"
        PAIRS.append((f"n3_w{wd}_{r}", base, bside))
    PAIRS.append((f"n3_w{wd}_D_t04", f"{H}/ufprod/full/tables/uf_w{wd}_t0.4", f"{H}/ufprod/full/uf_w{wd}_t0.4"))


def load(tdir):
    rows = [l.rstrip("\n").split("\t") for l in gzip.open(f"{tdir}/trials.tsv.gz", "rt", encoding="utf-8")][1:]
    return {(int(r[0]), int(r[1])): r for r in rows}


def cwa(rows):
    n = len(rows)
    c = sum(r[3] == "c" for r in rows)
    w = sum(r[3] == "w" for r in rows)
    return f"{c:,}・{w:,}・{n - c - w:,}"


def sup1(side, TR):
    k = n = 0
    for ap in glob.glob(f"{side}/side/*/seed*.answers.csv"):
        seed = int(os.path.basename(ap)[4:7])
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            r = TR[(seed, int(a["trial"]))]
            if a["hit"] == "0" and r[5] == "1" and r[7] == "e":
                n += 1
                k += a["support_ratio"] not in ("", None) and float(a["support_ratio"]) >= 1 - 1e-12
    return f"{k / n:.3f}（{k:,}／{n:,}）" if n else "—"


T1, T2, T3 = [], [], []
for arm, btab, bside in PAIRS:
    if not os.path.exists(f"{H}/n3prod/tables/{arm}/trials.tsv.gz"):
        continue
    A = load(f"{H}/n3prod/tables/{arm}")
    B = load(btab)
    for lab, X, side in (("N3", A, f"{H}/n3prod/{arm}"), ("今の規則", B, bside)):
        rows = list(X.values())
        bits = sum(float(r[9]) for r in rows) / len(rows)
        dn = [r for r in rows if r[5] == "1" and r[7] == "n"]
        de = [r for r in rows if r[5] == "1" and r[7] == "e"]
        T1.append(f"| {arm} | {lab} | {bits:,.0f} | {cwa(rows)} | {cwa(dn)} | {cwa(de)} | {sup1(side, X)} |")
    for grp, f in (("全課題", lambda r: True), ("ドア・例外", lambda r: r[5] == "1" and r[7] == "e"), ("ドア・通常", lambda r: r[5] == "1" and r[7] == "n")):
        m = Counter((B[k][3], A[k][3]) for k in A if k in B and f(A[k]))
        name = {"c": "正解", "w": "外れ", "a": "黙り"}
        T2.append(f"| {arm} | {grp} | " + " | ".join(f"{m[(x, y)]:,}" for x, y in (("c", "w"), ("c", "a"), ("w", "c"), ("w", "a"), ("a", "c"), ("a", "w"))) +
                  f" | {sum(v for (x, y), v in m.items() if x == y):,} |")
    diff = tot = 0
    for p in glob.glob(f"{H}/n3prod/{arm}/side/*/seed*.select.jsonl.gz"):
        for line in gzip.open(p, "rt", encoding="utf-8"):
            c = json.loads(line)["cands"]
            sel = [x for x in c if x["selected"]]
            if not sel:
                continue
            tot += 1
            diff += sel[0]["rank_now"] != 1
    T3.append(f"| {arm} | {tot:,} | {diff:,}（{diff / tot:.3f}） |" if tot else f"| {arm} | 0 | — |")

print("### 腕ごと（20 種の和）：N3 と同じ機械の今の規則\n")
print("| 腕 | 選び方 | 平均の記憶のビット | 全課題 正解・誤答・棄権 | ドア・通常 | ドア・例外 | 例外の日のドアの誤答のうち支持 1 の割合 |\n|---|---|---:|---|---|---|---|")
print("\n".join(T1))
print("\n### 同じ種・同じ試行で並べた移り変わり（今の規則 → N3）\n")
print("| 腕 | 課題 | 正解→外れ | 正解→黙り | 外れ→正解 | 外れ→黙り | 黙り→正解 | 黙り→外れ | 同じ |\n|---|---|---:|---:|---:|---:|---:|---:|---:|")
print("\n".join(T2))
print("\n### N3 の腕で、選んだ定義が今の規則の一位と違った試行（選びの記録。選ぶ段まで進んだ本物の予測）\n")
print("| 腕 | 選んだ試行 | 今の規則の一位と違う |\n|---|---:|---:|")
print("\n".join(T3))
