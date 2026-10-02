"""門のしきい値 g の曲線（委任書 2026-10-02 朝「誤りの印と記憶の量」の問い 1 の表 2 への追加）。★ tools/sealmem.py の出力を読むだけ。
答え方：支持の割合（答えの記録の support_ratio）が g 未満なら黙る（読み。g＝1.00 が表 2 の P1「支持 1 のときだけ答える」と同じ）。
  g＝0.67・0.70・0.75・0.80・0.85・0.90・0.95・1.00。答えた試行の支持の割合は 0.67 以上なので、g＝0.67 はほぼ黙らせない。
腕：世界 1・2 の A・C（λ＝0.0187・0.099）の 8 腕。群：全課題・ドアの通常・ドアの例外。種：1〜20 と 11〜20（g は決めずに並べるだけなので、
  図と表は種 1〜20。11〜20 は csv に残す。仮の決定）。各点に、同じ数を無作為に黙らせた期待値も残す。
出力：<出力>/門の曲線.csv、門の曲線.md（表）。図は tools/gate_curve.R。
使い方  python3.12 tools/gate_curve.py <sealmem の出力の場所> <出力の場所>"""
import csv
import glob
import os
import sys

ARMS = [f"cw{w}_{a}_{l}" for w in (2, 1) for a in ("A", "C") for l in ("lam0187", "lam0990")]
GS = [0.67, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]
GROUPS = [("全課題", lambda r: True), ("ドア・通常", lambda r: r["door"] == "1" and r["shop_cue"] == "n"),
          ("ドア・例外", lambda r: r["door"] == "1" and r["shop_cue"] == "e")]


def main():
    base, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    rows_out = []
    for arm in ARMS:
        rows = [r for p in sorted(glob.glob(os.path.join(base, arm, "seed*.answers.csv"))) for r in csv.DictReader(open(p, encoding="utf-8"))]
        for seeds, sel in (("1〜20", lambda s: True), ("11〜20", lambda s: s >= 11)):
            for g, f in GROUPS:
                rs = [r for r in rows if f(r) and sel(int(r["seed"]))]
                N, C = len(rs), sum(int(r["hit"]) for r in rs)
                for gv in GS:
                    # ★ 支持の割合は浮動小数で書かれている（例 2/3＝0.666…）。g と比べるときは 1e-9 のゆとりを持たせる（仮の決定）
                    ab = [r for r in rs if float(r["support_ratio"]) < gv - 1e-9]
                    k = len(ab)
                    rows_out.append({"腕": arm, "世界": arm[2], "種": seeds, "群": g, "g": f"{gv:.2f}", "答えた数": N, "正解": C, "外れ": N - C,
                                     "黙らせた数": k, "避けた誤答": sum(1 - int(r["hit"]) for r in ab), "失った正解": sum(int(r["hit"]) for r in ab),
                                     "無作為：避けた誤答": round(k * (N - C) / N, 2) if N else 0, "無作為：失った正解": round(k * C / N, 2) if N else 0})
    with open(os.path.join(out, "門の曲線.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    md = ["# 門のしきい値 g の曲線（種 1〜20。避けた誤答／失った正解、かっこは同じ数を無作為に黙らせた期待値の 避けた誤答／失った正解）", "",
          "答え方：支持の割合が g 未満なら黙る（g＝1.00 が P1 と同じ）。", ""]
    for g, _f in GROUPS:
        md += [f"## {g}", "", "| 腕 | 答えた数（外れ） | " + " | ".join(f"g＝{x:.2f}" for x in GS) + " |", "|---|---|" + "---|" * len(GS)]
        for arm in ARMS:
            rs = [r for r in rows_out if r["腕"] == arm and r["群"] == g and r["種"] == "1〜20"]
            md.append(f"| {arm} | {rs[0]['答えた数']}（{rs[0]['外れ']}） | " + " | ".join(
                f"{r['避けた誤答']}／{r['失った正解']}（{r['無作為：避けた誤答']}／{r['無作為：失った正解']}）" for r in rs) + " |")
        md.append("")
    open(os.path.join(out, "門の曲線.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
