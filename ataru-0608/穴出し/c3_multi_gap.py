"""穴出しの候補 3：--answer-gap のもとで、同じ欠けた位置に二つ以上の席が対応するか（後づけの集計。走行はしない）。
材料：side/<セル>/seed<種>.routing.jsonl(.gz) の kind=score の行（開示のあった試行。使った定義の全部の席の
  状態 st・対応先 cid（tools/v310be.py role_target。--answer-gap の適格の判定と同じ関数）・各状態の答え ans）。
  欠けた位置＝開示された関係（received）の ID（設定 hide1 では、場面の欠けた位置は伏せ辺一つ）。
適格な候補（--answer-gap が残すもの）：cid ＝ 欠けた位置 で、その席の今の状態の答え（F→ans.F、H→ans.H、U→ans.U）が null でない席。
数えるもの：開示のあった試行のうち、適格な候補が 2 つ以上の試行。そのうち答えの述語が違うもの、正解が一つ目でない（並び順で外れる）もの。
並び順（tools/v39.py fill_decision）：投影（F の席）が先、次に穴埋めの候補を席の番号の順。ここでは「F の席を先、次に席の番号の順」で一つ目を決める
（投影の候補は F の席だけなので、同じ並び）。実際に話した答えは answers.csv の同じ試行の行と突き合わせる。
使い方：c3_multi_gap.py <腕の置き場所>…  → 標準出力に markdown と例。"""
import csv
import glob
import gzip
import json
import os
import sys
from collections import Counter


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


print("| 腕 | 種 | 開示のあった試行（採点の行） | 適格 0 | 適格 1 | 適格 2 以上 | うち答えの述語が違う | うち正解が並びの一つ目でない | 実際の答えが並びの一つ目と同じ |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
examples = []
for root in sys.argv[1:]:
    arm = os.path.basename(root.rstrip("/"))
    c = Counter()
    seeds = 0
    for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.routing.jsonl*"))):
        seeds += 1
        seed = int(os.path.basename(p)[4:7])
        ans_csv = os.path.join(os.path.dirname(p), f"seed{seed:03d}.answers.csv")
        spoke = {}
        if os.path.exists(ans_csv):
            for r in csv.DictReader(open(ans_csv, encoding="utf-8")):
                spoke[int(r["trial"])] = (r["slot"], r["pred"], r["hit"])
        for line in opn(p):
            r = json.loads(line)
            if r.get("kind") != "score":
                continue
            c["採点の行"] += 1
            gid, gpred, gargs = r["received"]
            el = []
            for it in r["items"]:
                a = (it.get("ans") or {}).get(it["st"])
                if it.get("cid") == gid and a is not None:
                    el.append((0 if it["st"] == "F" else 1, it["slot"], it["st"], a))
            el.sort()
            c[f"適格 {min(len(el), 2)}"] += 1
            if len(el) >= 2:
                preds = {x[3] for x in el}
                if len(preds) > 1:
                    c["述語が違う"] += 1
                    if el[0][3] != gpred and any(x[3] == gpred for x in el[1:]):
                        c["正解が一つ目でない"] += 1
                        if len(examples) < 6:
                            examples.append((arm, seed, r["trial"], gpred, el, spoke.get(r["trial"])))
                sp = spoke.get(r["trial"])
                if sp is not None:
                    c["話した"] += 1
                    c["一つ目と同じ"] += str(el[0][1]) == sp[0]
    print(f"| {arm} | {seeds} | {c['採点の行']:,} | {c['適格 0']:,} | {c['適格 1']:,} | {c['適格 2']:,} | {c['述語が違う']:,} | {c['正解が一つ目でない']:,} | {c['一つ目と同じ']:,}／{c['話した']:,} |")
print("\n例（正解が並びの二つ目以降にあった試行）：")
for arm, seed, t, gp, el, sp in examples:
    print(f"- {arm} 種 {seed} 試行 {t}：正解の述語 {gp}。適格な候補（並びの順）" + "、".join(f"席 {x[1]}（{x[2]}）→{x[3]}" for x in el) + f"。話した答え {sp}")
