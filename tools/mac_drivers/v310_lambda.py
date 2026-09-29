"""control/2026-09-29_v3.10の較正.md から λ の 4 段階（25・50・75・90 パーセンタイル）を読む。判断しない。
表の行で、最初の欄が 25・50・75・90（後ろに % か「パーセンタイル」が付いてもよい）、次の欄が数だけのものを拾う。
四つがちょうど一つずつ見つかったときだけ、{"25": "<数の字面>", ...} を出す。そうでなければ終了コード 3（止まって control/ に書く）。
上書き：~/v310prod/lambda.json があれば、それをそのまま使う（人が読んで書いたもの）。
使い方  python3.12 tools/mac_drivers/v310_lambda.py <較正の md>"""
import json
import os
import re
import sys

ov = os.path.expanduser("~/v310prod/lambda.json")
if os.path.exists(ov):
    d = json.load(open(ov))
    print(json.dumps({k: str(d[k]) for k in ("25", "50", "75", "90")}))
    sys.exit(0)
pat = re.compile(r"^\|\s*(?:λ\s*)?(25|50|75|90)\s*(?:%|パーセンタイル)?\s*\|\s*([0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*\|")
found = {}
for line in open(sys.argv[1], encoding="utf-8"):
    m = pat.match(line.strip())
    if m:
        found.setdefault(m.group(1), []).append(m.group(2))
if sorted(found) == ["25", "50", "75", "90"] and all(len(v) == 1 for v in found.values()):
    print(json.dumps({k: v[0] for k, v in found.items()}))
    sys.exit(0)
print(json.dumps({"読めなかった": found}, ensure_ascii=False))
sys.exit(3)
