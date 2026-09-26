"""二つ目の実験の試し（2026-09-26 午後）の表：誕生・同化・走行末の生存定義の数だけ。★ 判定しない。神話や世界偽の値は出さない。
入力：analysis_v32_2026-09-26/try/<腕>/side/<セル>/seedNNN.jsonl（tools/v3_run.py の side）と manifest.jsonl。すべてこのマックで走らせたもの。
  誕生 ＝ side の kind "birth" の数、同化 ＝ kind "assim" の数（m1 が定義を登録・更新した試行。v3_run.py の wrapped m1）。
  走行末の生存定義 ＝ side の最後の行（kind "final"）の alive_end の数。
使い方  python3.12 tools/v32_try_tab.py <出力.md>"""
import collections, json, sys
from pathlib import Path
T = Path("/Users/tatsu-admin/sfn/sfn-compression-abm/analysis_v32_2026-09-26/try")
ARMS = [("v3_ref", "v3"), ("v31a_ref", "v3.1a"), ("v31a_ABC", "v3.1a＋A・B・C"), ("v31b_ref", "v3.1b"), ("v31b_ABC", "v3.1b＋A・B・C")]
out = sys.argv[1]
D = {}
secs = {}
for arm, _ in ARMS:
    for side in sorted((T / arm / "side").glob("*/seed*.jsonl")):
        cell, sd = side.parent.name, side.stem
        k = collections.Counter(); fin = None
        for line in open(side, encoding="utf-8"):
            r = json.loads(line); k[r.get("kind")] += 1
            if r.get("kind") == "final":
                fin = r
        if fin is None:
            continue                                  # ★ 走り終えていない
        D[(arm, cell, sd)] = (k["birth"], k["assim"], len(fin["alive_end"]))
    man = T / arm / "manifest.jsonl"
    if man.exists():
        for line in open(man, encoding="utf-8"):
            m = json.loads(line)
            secs[(arm, m["cell"], f"seed{m['seed']:03d}")] = m.get("elapsed_sec")
cells = sorted({(c, s) for (_, c, s) in D})
lab = lambda c: c.replace("f0.5000_", "").replace("_vt0.3842_first_order", "・最頻").replace("・最頻_fill-sample", "・sample")
L = ["# 二つ目の実験の試し：誕生・同化・走行末の生存定義の数（このマック、2026-09-26）　判定しない", "",
     "★ 腕：hide（f＝0.5）、NSIM（基準）0.8、seed001・002 × 4 セル（θ′2.1・2.3 × 最頻・sample）。",
     "★ v3 ＝ --nohash --nsim 0.8 --vt 0.3842 --greedy（クラウドの v3cn80 と同じ旗）。v3.1a・b ＝ それに --extend-rule profit／none --charge1 d32。",
     "★ ＋A・B・C ＝ --ident-rho 0.5 --ident-argmax --ident-commons（tools/v32.py）。",
     "★ 誕生・同化は m1 が定義を登録・更新した試行の数（1,740 試行のうち）。走行末の生存定義は最後の試行の後の数。", ""]
for j, name in enumerate(("誕生", "同化", "走行末の生存定義")):
    L += [f"## {name}", "", "| 種 | セル | " + " | ".join(l for _, l in ARMS) + " |", "|---|---|" + "---:|" * len(ARMS)]
    for c, s in cells:
        L.append(f"| {s} | {lab(c)} | " + " | ".join(str(D[(a, c, s)][j]) if (a, c, s) in D else "—" for a, _ in ARMS) + " |")
    L.append("")
L += ["## 1 本の時間（秒、走行の記録 elapsed_sec。並列で走らせたので目安）", "", "| 種 | セル | " + " | ".join(l for _, l in ARMS) + " |", "|---|---|" + "---:|" * len(ARMS)]
for c, s in cells:
    L.append(f"| {s} | {lab(c)} | " + " | ".join(f"{secs[(a, c, s)]:,.0f}" if secs.get((a, c, s)) else "—" for a, _ in ARMS) + " |")
Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
print("->", out)
