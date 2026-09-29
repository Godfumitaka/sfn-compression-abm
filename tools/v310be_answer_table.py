"""B＋E の腕ごとの「実際の答え」の表（2026-09-29 夜の依頼）。★ 判断しない。tools/v39_miss_source.py の数（.json）を表にするだけ。
実際の答え＝台帳の coverage＝1（予測を出した試行）。当たり＝hit＝1、外れ＝それ以外。出どころと生まれた型の決め方は tools/v39_miss_source.py。
使い方  python3.12 tools/v310be_answer_table.py <出力の .md> <数の .json> [<数の .json> …]"""
import json
import sys

SRC = ("F の投影", "F の穴埋め", "H の穴埋め", "U の穴埋め", "分からない")
WHERE = (("生まれた型", "生まれた型の場面"), ("生まれた型以外", "それ以外の型の場面"), ("型が分からない", "生まれた型が分からない"))
out, files = sys.argv[1], sys.argv[2:]
arms = [a for f in files for a in json.load(open(f, encoding="utf-8"))]
L = []
for a in arms:
    n = a["数"]
    L += [f"### {a['腕']}（走行 {a['走行']}）", "",
          "| 出どころ | 場面 | 答え | 当たり | 外れ |", "|---|---|---:|---:|---:|"]
    tot = {"答え": 0, "外れ": 0}
    for s in SRC:
        for key, label in WHERE:
            spk = n.get(f"発話_{key}|{s}", 0)
            miss = n.get(f"誤答_{key}|{s}", 0)
            if spk == 0 and (s == "分からない" or key == "型が分からない"):
                continue
            L.append(f"| {s} | {label} | {spk:,} | {spk - miss:,} | {miss:,} |")
            tot["答え"] += spk
            tot["外れ"] += miss
    L.append(f"| 計 | | {tot['答え']:,} | {tot['答え'] - tot['外れ']:,} | {tot['外れ']:,} |")
    L += ["", f"- 出どころが「分からない」答え：{n.get('発話|分からない', 0):,}。生まれた型が分からない答え：{sum(n.get(f'発話_型が分からない|{s}', 0) for s in SRC):,}。", ""]
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("ok", out, len(arms))
