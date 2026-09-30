"""answerseat_analysis.py の .json と extrap.csv（外挿の印）から、3・4・5 の表を作る。★ 数えるだけ。判断しない。
使い方  python3.12 tools/answerseat_tables.py <345.json> <出力の場所> <腕名>=<腕の走行根> …
  3 は、ぶら下がり無しの試行の集合を、extrap.csv の「判定不能」の試行の集合（粗い・細かい）と試行ごとに突き合わせる。"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter

PER_ARM = 34800


def d_row(x):
    if not x:
        return "— | — | — | — | —"
    return f"{x['中央値']} | {x['第1四分位']} | {x['第3四分位']} | {x['最大']} | {x['n']:,}"


def main():
    res = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    roots = dict(s.split("=", 1) for s in sys.argv[3:])
    L3 = ["# 3 伏せた関係の ID が、見えている関係のどれかの引数に入っているか", "",
          f"分母：全課題（腕ごと {PER_ARM:,}）。「判定不能」は外挿の印（extrap.csv）の粗い・細かいの印。", "",
          "| 腕 | 入っている | 入っていない | 判定不能（粗い） | 判定不能（細かい） | 入っていない ⊕ 判定不能（細かい） の食い違い | 同（粗い） |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    mism = {}
    for name, arm in res.items():
        none = {(int(s), t) for s, ts in arm["ぶら下がり無しの試行"].items() for t in ts}
        und = {"粗": set(), "細": set()}
        reasons = Counter()
        for p in sorted(glob.glob(os.path.join(roots[name], "side/*/seed*.extrap.csv"))):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                if not 1 <= int(r["seed"]) <= 20:
                    continue
                for g in ("粗", "細"):
                    if r[f"{g}_印"] == "判定不能":
                        und[g].add((int(r["seed"]), int(r["trial"])))
                if r["細_印"] == "判定不能":
                    reasons[r["situation_undet_reason"]] += 1
        x = {g: sorted(none ^ und[g]) for g in und}
        mism[name] = {g: [{"seed": s, "trial": t, "入っていない": (s, t) in none, "判定不能": (s, t) in und[g]} for s, t in v[:20]] for g, v in x.items()}
        mism[name]["判定不能の理由（細かい）"] = dict(reasons)
        a = arm["ぶら下がった参照"]
        L3.append(f"| {name} | {a['あり']:,} | {a['なし']:,} | {len(und['粗']):,} | {len(und['細']):,} | {len(x['細']):,} | {len(x['粗']):,} |")
    L3 += ["", "- 判定不能の理由（細かい、腕ごと）：" + "；".join(f"{n} " + "、".join(f"{k} {v:,}" for k, v in m["判定不能の理由（細かい）"].items()) for n, m in mism.items()), ""]
    L4 = ["# 4 定義の厚さ", "", "## 4-1 予測で選ばれた定義（台帳の R_used）の、予測の直前の F・H・U の席の数", "",
          f"分母：R_used のある予測（腕ごとの数は n の列。全課題は {PER_ARM:,}）。", "",
          "| 腕 | 席 | 中央値 | 第1四分位 | 第3四分位 | 最大 | n |", "|---|---|---:|---:|---:|---:|---:|"]
    for name, arm in res.items():
        s = arm["選ばれた定義の席"]
        for k in ("F", "H", "U", "席の計"):
            L4.append(f"| {name} | {k} | {d_row(s[k])} |")
    L4 += ["", "## 4-2 全定義の F・H・U の席の数と定義の本数（試行 100・200・…・1,700 の終わり、走行の終わり）", "",
           "定義の本数は 20 走行の和と、走行ごとの中央値〔最小–最大〕。席の数は、その時点の全定義（20 走行の和）の上の分布。", ""]
    for name, arm in res.items():
        L4 += [f"### {name}", "", "| 時点 | 定義の本数（和） | 走行ごと 中央値〔最小–最大〕 | F 中央値〔四分位〕最大 | H 中央値〔四分位〕最大 | U 中央値〔四分位〕最大 |",
               "|---|---:|---|---|---|---|"]
        for k, v in arm["全定義の席"].items():
            pr = v["定義の本数（走行ごと）"]
            f = lambda x: (f"{x['中央値']}〔{x['第1四分位']}–{x['第3四分位']}〕{x['最大']}" if x else "—")  # noqa: E731
            L4.append(f"| {k} | {v['定義の本数（走行の和）']:,} | {pr['中央値']}〔{pr['最小']}–{pr['最大']}〕 | {f(v['F'])} | {f(v['H'])} | {f(v['U'])} |")
        L4.append("")
    L5 = ["# 5 細かい状況で「確かめる機会がまだなかった」課題", ""]
    sets = {n: sorted((x["seed"], x["trial"]) for x in a["未経験_細かい"]) for n, a in res.items()}
    same = len({tuple(v) for v in sets.values()}) == 1
    L5 += [f"- 腕ごとの数：" + "、".join(f"{n} {len(v)}" for n, v in sets.items()) + f"。（種, 試行）の集合がどの腕でも同じか：{'同じ' if same else '違う'}。", ""]
    first = next(iter(res.values()))["未経験_細かい"]
    L5 += ["| 種 | 試行 | 型 | 伏せた位置の階 | 伏せた述語 |", "|---:|---:|---|---:|---|"]
    for x in sorted(first, key=lambda z: (z["seed"], z["trial"])):
        L5.append(f"| {x['seed']} | {x['trial']} | {x['型']} | {x['伏せた位置の階']} | {x['伏せた述語']} |")
    tc = Counter(x["trial"] for x in first)
    L5 += ["", "- 試行番号の分布：" + "、".join(f"試行 {t}：{v}" for t, v in sorted(tc.items())),
           "- 型：" + "、".join(f"{k} {v}" for k, v in sorted(Counter(x["型"] for x in first).items())),
           "- 階：" + "、".join(f"{k} {v}" for k, v in sorted(Counter(x["伏せた位置の階"] for x in first).items())), ""]
    for fn, L in (("3_ぶら下がった参照.md", L3), ("4_定義の厚さ.md", L4), ("5_未経験の課題.md", L5)):
        open(os.path.join(out, fn), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(mism, open(os.path.join(out, "3_食い違いの例.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(L3))
    print("\n".join(L5[:3]))


if __name__ == "__main__":
    main()
