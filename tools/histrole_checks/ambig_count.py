"""U の席の同点で黙った回数（2026-09-30 の依頼「U 同点で黙る」、マックの小さな世界の C35・C36 の型）。★ 数えるだけ。判断しない。
答えごとの記録の side/<セル>/seed<種>.ambig.csv（あいまい＝ambiguous_projection で黙った試行）を読む。
  C35・C36 の型：伏せられた関係に当たる席（--score-role の対応先が伏せ辺の ID と一致）が F か H で答えを持ち、その席自身は穴埋めで同点でなく、
    ほかの U の席が同点だった試行。そのうち、その F・H の答えが当たり（名前と写した位置が伏せ辺と同じ）だった回数。
使い方  python3.12 tools/histrole_checks/ambig_count.py <腕の走行根> <腕名>   （表の一行を標準出力に。数は種の和）"""
import collections
import csv
import glob
import sys

root, arm = sys.argv[1], sys.argv[2]
C = collections.Counter()
for f in sorted(glob.glob(f"{root}/side/*/seed*.ambig.csv")):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        C["あいまいで黙った"] += 1
        uo = int(r["tied_U_other"] or 0)
        C["ほかの U の席が同点"] += uo > 0
        if r["held_found_by"] != "cid":
            C["伏せ辺に当たる席が定義に無い"] += 1
            continue
        st = r["held_state"]
        C[f"伏せ辺に当たる席_{st}"] += 1
        if st in ("F", "H") and r["held_answer"] and r["held_tied"] == "0" and uo > 0:
            C["C35・C36 の型"] += 1
            C[f"C35・C36 の型_{st}"] += 1
            C["C35・C36 の型_当たり"] += r["held_hit"] == "1"
            C[f"C35・C36 の型_{st}_当たり"] += r["held_hit"] == "1"
g = C.get
print(f"| {arm} | {g('あいまいで黙った', 0):,} | {g('ほかの U の席が同点', 0):,} | {g('伏せ辺に当たる席が定義に無い', 0):,} | "
      f"{g('伏せ辺に当たる席_F', 0):,}／{g('伏せ辺に当たる席_H', 0):,}／{g('伏せ辺に当たる席_U', 0):,} | "
      f"{g('C35・C36 の型', 0):,}（F {g('C35・C36 の型_F', 0):,}・H {g('C35・C36 の型_H', 0):,}） | "
      f"{g('C35・C36 の型_当たり', 0):,}（F {g('C35・C36 の型_F_当たり', 0):,}・H {g('C35・C36 の型_H_当たり', 0):,}） |")
