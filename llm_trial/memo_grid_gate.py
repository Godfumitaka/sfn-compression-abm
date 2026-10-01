"""格子の関門（予約の委任書の 4）：世界 2 の全履歴の系列で、最後の試験（40 場面の後）のドアの 4 問が 3 問以上正解か。
数え方は二つ（判定が「正解」＝答えて当たった、と、最もありそうな答えが正しい＝黙りも含む）。二つが同じ結論なら PASS／FAIL、
食い違えば UNDECIDED（どちらで読むかは委任書に無いので、決めずに止まる）。4 問がそろっていなければ INCOMPLETE。
使い方  python3.12 llm_trial/memo_grid_gate.py <出力の場所>   （一行目に結論、二行目に中身の JSON）"""
import json
import os
import sys

log = os.path.join(sys.argv[1], "w2_full.jsonl")
rows = [json.loads(l) for l in open(log, encoding="utf-8")] if os.path.exists(log) else []
door = [r for r in rows if r["段"] == "試験" and r["t"] == 40 and r["種類"] == "元" and r.get("問の種類") == "ドア"]
a = sum(1 for r in door if r["判定"] == "正解")
b = sum(1 for r in door if r.get("最もありそうな答えが正しい"))
if len(door) != 4:
    g = "INCOMPLETE"
elif (a >= 3) == (b >= 3):
    g = "PASS" if a >= 3 else "FAIL"
else:
    g = "UNDECIDED"
print(g)
print(json.dumps({"ドアの問の数": len(door), "答えて当たった": a, "最もありそうな答えが正しい": b,
                  "一問ずつ": [(r["場合"], r["判定"], r.get("answer"), r["正解"], r.get("confidence")) for r in door]}, ensure_ascii=False))
