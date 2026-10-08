"""走行の列の一行から、一本ずつの命令（run_after_audit.py の sme.commands.json と同じ形）を作る。走らせない。
使い方：build_commands.py <#> <出力の JSON>
- 行の「版・旗・出力先」から、版（7〜40 桁の 16 進）、旗（` ` で囲んだもの）、出力先（/home/… か ~/…）を読む。
- 世界の欄（例「お店 1・2」「お店 2」）から --shop-world、種の欄（例「1〜20」「41〜48」）から --seeds を作る。
- 旗は、v3_run.py の config と出力先の後ろに置く引数の全部とみなす。旗に --seeds・--shop-world・出力先が入っていたら、行の欄と重なるので止まる。
- 読めない・決まらないところがあれば、作らずに止まる（推測で埋めない）。止まったら、受け箱に問いを書く。"""
import json
import re
import shlex
import sys

sys.path.insert(0, "/home/tatsu/queue")
from queue_row import read, rows  # noqa: E402

CONFIG = "config/sweep_shop_hide1_s1_2026-10-01.json"


def seeds_of(s):
    m = re.fullmatch(r"(\d+)\s*[〜~\-]\s*(\d+)", s.strip())
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    if re.fullmatch(r"\d+", s.strip()):
        return [int(s)]
    sys.exit(f"★ 種の欄「{s}」が読めない")


def worlds_of(s):
    if "動詞" in s:
        sys.exit(f"★ 世界の欄「{s}」：動詞の世界の命令の形はまだ決まっていない。作らない")
    w = [int(x) for x in re.findall(r"\d", s)]
    if not w or any(x not in (1, 2) for x in w):
        sys.exit(f"★ 世界の欄「{s}」が読めない")
    return w


num, out = sys.argv[1], sys.argv[2]
r = [x for x in rows(read()) if x["num"] == num]
if len(r) != 1:
    sys.exit(f"★ 行 #{num} が一つに決まらない")
r = r[0]
spec = r["spec"]
commit = re.findall(r"\b[0-9a-f]{7,40}\b", spec)
flags = re.findall(r"`([^`]+)`", spec)
dest = re.findall(r"(?:/home/tatsu|~)/[^\s、，,）)`]+", spec)
if len(set(commit)) != 1 or len(flags) != 1 or len(set(dest)) != 1:
    sys.exit(f"★ 「版・旗・出力先」が一つずつに読めない：版 {commit}、旗 {len(flags)} 個、出力先 {dest}\n  欄：{spec}")
args = shlex.split(flags[0])
for bad in ("--seeds", "--shop-world"):
    if bad in args:
        sys.exit(f"★ 旗に {bad} が入っている（行の欄と重なる）。作らない")
dest = dest[0].replace("~", "/home/tatsu", 1)
plan = []
for w in worlds_of(r["world"]):
    for s in seeds_of(r["seeds"]):
        arm = f"q{num}_w{w}"
        plan.append(dict(arm=arm, seed=s, diagnostic_only=False,
                         command=["python3.12", "tools/v3_run.py", CONFIG, f"{dest}/{arm}/seed{s:03d}", *args, "--shop-world", str(w), "--seeds", str(s)]))
if len(plan) != int(re.sub(r"\D", "", r["n"]) or 0):
    sys.exit(f"★ 作った本数 {len(plan)} が、行の本数「{r['n']}」と合わない")
json.dump(dict(row=num, commit=commit[0], what=r["what"], spec=spec, plan=plan), open(out, "w"), ensure_ascii=False, indent=1)
print(f"#{num}：{len(plan)} 本、版 {commit[0]}、出力先 {dest}")
print("見本：", " ".join(plan[0]["command"]))
