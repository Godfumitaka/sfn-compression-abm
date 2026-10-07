"""~/surface/out/per_run.csv の数を、前の解析 ~/sme_analysis/out/error_types_<条件>.csv と突き合わせる（読むだけ）。
古い主の条件 160 本で、道具が同じ数を出すことの確かめ。
使い方：python3.12 ~/surface/crosscheck.py
欄：tasks・correct・wrong・silent・selection_error・distinction_loss。範囲（全課題／ドア課題）× 日（例外／通常）× 種。"""
import csv
import json
import sys
from pathlib import Path

HOME = Path.home()
OLD = HOME / "sme_analysis/out"
NEW = HOME / "surface/out/per_run.csv"
KEYS = ("tasks", "correct", "wrong", "silent", "selection_error", "distinction_loss")

cfg = json.loads((HOME / "surface/configs.json").read_text())
arm_of = {}
for g in cfg["groups"]:
    if g.get("family") == "古い主の条件":
        for arm, spec in g["arms"].items():
            arm_of[(spec["config"], spec["world"])] = arm
new = {}
for r in csv.DictReader(open(NEW, encoding="utf-8")):
    arm = arm_of.get((r["config"], int(r["world"])))
    if arm and r["day"] in ("例外", "通常"):
        new[(arm, int(r["seed"]), r["scope"], r["day"])] = r
compared = cells = 0
diffs = []
seen = set()
for p in sorted(OLD.glob("error_types_*.csv")):
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["seed"] == "計" or not r["scope"]:
            continue
        k = (r["arm"], int(r["seed"]), r["scope"], r["day"])
        seen.add(k)
        n = new.get(k)
        if n is None:
            diffs.append((k, "surface に無い"))
            continue
        compared += 1
        for f in KEYS:
            cells += 1
            if str(n[f]) != str(r[f]):
                diffs.append((k, f, r[f], n[f]))
extra = sorted(set(new) - seen)
runs = len({k[:2] for k in seen})
print(f"本 {runs}、行 {compared}、数の欄 {cells}、違い {len(diffs)}、surface にだけある行 {len(extra)}")
for d in diffs[:50]:
    print("  違い", d)
for e in extra[:20]:
    print("  surface にだけ", e)
sys.exit(1 if diffs or extra else 0)
