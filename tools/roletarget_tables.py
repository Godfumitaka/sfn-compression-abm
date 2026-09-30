"""1・2 の表（答えた席の対応先・穴埋めの候補）。tools/roletarget_recompute.py の出力と extrap.csv（外挿の印）を試行ごとにつなぐ。★ 数えるだけ。判断しない。
使い方  python3.12 tools/roletarget_tables.py <出力の場所> <腕名>=<腕の走行根>:<roletarget の場所> …
分母：全課題（腕ごと 34,800）と、外れ（答えた課題で述語・引数が伏せた関係と一致しないもの）。"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter

PER_ARM = 34800


def load(root, rtdir):
    ex = {}
    for p in glob.glob(os.path.join(root, "side/*/seed*.extrap.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if 1 <= int(r["seed"]) <= 20:
                ex[(int(r["seed"]), int(r["trial"]))] = r
    rt = {}
    for p in glob.glob(os.path.join(rtdir, "*.roletarget.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            rt[(int(r["seed"]), int(r["trial"]))] = r
    return ex, rt


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    L1 = ["# 1 答えた席の対応先", "", f"分母：全課題（腕ごと {PER_ARM:,}）と外れ。対応先は作り直した状態から計算し直したもの（tools/roletarget_recompute.py）。", ""]
    L2 = ["# 2 投影が無く穴埋めで答えた課題の、穴埋めの候補", "", f"分母：全課題（腕ごと {PER_ARM:,}）と外れ。候補は台帳の predictions_all_slots（並び順どおり、先頭が話された答え）。", ""]
    S = {}
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        root, rtdir = rest.split(":", 1)
        ex, rt = load(root, rtdir)
        ans = [(k, ex[k], rt.get(k)) for k in sorted(ex) if ex[k]["answered"] == "1"]
        missing = sum(1 for _k, _e, r in ans if r is None or r.get("answered") != "1")
        miss_all = sum(1 for _k, e, _r in ans if e["task"] == "外れ")
        # 1-1 出どころ × 分類 × 当たり
        c = Counter((e["source"], r["cls"], e["task"]) for _k, e, r in ans if r)
        L1 += [f"## {name}", "", f"- 答えた {len(ans):,}（全課題 {PER_ARM:,} の {len(ans) / PER_ARM:.1%}）。外れ {miss_all:,}。計算し直しの行が無い答え：{missing}。", "",
               "### 1-1 出どころ × 話した席の対応先 × 当たり", "", "| 出どころ | 対応先 | 課題 | 数 | 全課題の割合 | 外れの割合 |", "|---|---|---|---:|---:|---:|"]
        for k in sorted(c):
            v = c[k]
            L1.append(f"| {k[0]} | {k[1]} | {k[2]} | {v:,} | {v / PER_ARM:.2%} | {(f'{v / miss_all:.2%}' if k[2] == '外れ' and miss_all else '—')} |")
        # 1-2 外挿の列と
        for g, gn in (("細", "細かい"), ("粗", "粗い")):
            c2 = Counter((r["cls"], e["task"], e[f"{g}_印"], {"1": "届いた", "0": "届いていない", "": "—"}[e[f"{g}_証拠が届いた"]],
                          {"1": "逐語あり", "0": "逐語なし", "": "—"}[e[f"{g}_逐語"]]) for _k, e, r in ans if r)
            L1 += ["", f"### 1-2（{gn}状況）対応先 × 課題 × 確かめる機会 × 証拠が席に届いたか × 逐語", "",
                   "| 対応先 | 課題 | 確かめる機会 | 証拠 | 逐語 | 数 |", "|---|---|---|---|---|---:|"]
            for k in sorted(c2):
                L1.append("| " + " | ".join(k) + f" | {c2[k]:,} |")
        L1.append("")
        # 2
        fill = [(k, e, r) for k, e, r in ans if r and e["source"].endswith("_fill")]
        fm = [x for x in fill if x[1]["task"] == "外れ"]
        nc = Counter(int(r["n_cands"]) for _k, _e, r in fill)
        hid = [x for x in fill if x[2]["hid_cand"] == "1"]
        other_first = [x for x in hid if x[2]["hid_first_k"] not in ("", "0")]
        hid_ok = [x for x in hid if x[2]["hid_correct"] == "1"]
        of_ok = [x for x in other_first if x[2]["hid_correct"] == "1"]
        fmh = [x for x in fm if x[2]["hid_cand"] == "1"]
        fmo = [x for x in fmh if x[2]["hid_first_k"] not in ("", "0")]
        fmo_ok = [x for x in fmo if x[2]["hid_correct"] == "1"]
        S[name] = dict(fill=len(fill), fill_miss=len(fm), hid=len(hid), other_first=len(other_first), other_first_correct=len(of_ok),
                       hid_correct=len(hid_ok), miss_hid=len(fmh), miss_other_first=len(fmo), miss_other_first_correct=len(fmo_ok),
                       miss_all=miss_all)
        L2 += [f"## {name}", "",
               f"- 穴埋めで答えた {len(fill):,}（全課題の {len(fill) / PER_ARM:.1%}）。うち外れ {len(fm):,}（外れ全体 {miss_all:,}）。", "",
               "| 数 | 穴埋めで答えた（全課題の割合） | うち外れ（外れ全体の割合） |", "|---|---:|---:|",
               f"| 伏せた関係を対応先とする候補があった | {len(hid):,}（{len(hid) / PER_ARM:.2%}） | {len(fmh):,}（{(len(fmh) / miss_all if miss_all else 0):.2%}） |",
               f"| そのうち、並び順で別の候補が先に話された | {len(other_first):,}（{len(other_first) / PER_ARM:.2%}） | {len(fmo):,}（{(len(fmo) / miss_all if miss_all else 0):.2%}） |",
               f"| そのうち、伏せた関係を対応先とする候補が正しかった（研究者の側） | {len(of_ok):,} | {len(fmo_ok):,} |",
               f"| 伏せた関係を対応先とする候補が正しかった（先に話されたかを問わない） | {len(hid_ok):,} | — |", "",
               "- 候補の数の分布（穴埋めで答えた課題）：" + "、".join(f"{k} 個 {v:,}" for k, v in sorted(nc.items())), ""]
        kd = Counter(x[2]["hid_first_k"] for x in hid)
        L2 += ["- 伏せた関係を対応先とする最初の候補の並びの位置（0＝話された）：" + "、".join(f"{k}：{v:,}" for k, v in sorted(kd.items(), key=lambda z: int(z[0]))), ""]
    open(os.path.join(out, "1_答えた席の対応先.md"), "w", encoding="utf-8").write("\n".join(L1) + "\n")
    open(os.path.join(out, "2_穴埋めの候補.md"), "w", encoding="utf-8").write("\n".join(L2) + "\n")
    json.dump(S, open(os.path.join(out, "2_要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(S, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
