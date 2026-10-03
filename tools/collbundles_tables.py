"""集団化：例外の日の場面から来た束の表（2026-10-03 の追加）。★ tools/collbundles.py の出力を読むだけ。数を並べるだけ。
使い方  python3.12 tools/collbundles_tables.py <collbundles の出力の場所（A・C の下に集団ごとの .json）>"""
import glob
import json
import os
import sys
from collections import Counter

K1 = ["例外の答え", "通常の答え（神話）", "その他", "ドアでない関係の答え", "束から外された", "答え無し"]
K1B = ["例外の答え（話し手の答え）", "通常の答え（神話）（話し手の答え）", "例外の答え（見えた関係）", "通常の答え（神話）（見えた関係）", "ドアの関係が無い"]
K3 = ["例外の答えだけ", "通常の答えだけ", "両方", "ドアの席が無い（又は U だけ）", "定義が無い", "取り込まれていない"]


def main():
    base = sys.argv[1]
    res, md = {}, []
    for arm in ("A", "C"):
        bs = [b for p in sorted(glob.glob(os.path.join(base, arm, "pilot_w2_recvA_g0*.json"))) for b in json.load(open(p, encoding="utf-8"))["束"]]
        n = len(glob.glob(os.path.join(base, arm, "pilot_w2_recvA_g0*.json")))
        res[arm] = {"集団": n, "束": len(bs),
                    "1": dict(Counter(b["1 話し手の答え"] for b in bs)), "1b": dict(Counter(b["1b 束の中のドアの関係"] for b in bs)),
                    "2": dict(Counter("・".join(b["2 束のシールの述語"]) or "シール無し" for b in bs)),
                    "2 Codex の has_sig_e": dict(Counter(str(b["has_sig_e"]) for b in bs)),
                    "3": dict(Counter(b["3 取り込んだ定義のドアの答え"] for b in bs)),
                    "1×3": dict(Counter(f"{b['1 話し手の答え']}→{b['3 取り込んだ定義のドアの答え']}" for b in bs)),
                    "2×3": dict(Counter(f"{'・'.join(b['2 束のシールの述語']) or 'シール無し'}→{b['3 取り込んだ定義のドアの答え']}" for b in bs))}
    md += ["## 1. 束の中の話し手の答え（例外の日の場面から来て受け手に届いた束。世界 2、通信あり、集団の種 1〜20、二体の和）", "",
           "| 腕 | 集団 | 束 | " + " | ".join(K1) + " |", "|---|---:|---:|" + "---:|" * len(K1)]
    for arm, v in res.items():
        md.append(f"| {arm} | {v['集団']} | {v['束']} | " + " | ".join(str(v["1"].get(k, 0)) for k in K1) + " |")
    md += ["", "束の中のドアの関係（述語 hold・hold_b の関係）：", "", "| 腕 | " + " | ".join(K1B) + " |", "|---|" + "---:|" * len(K1B)]
    for arm, v in res.items():
        md.append(f"| {arm} | " + " | ".join(str(v["1b"].get(k, 0)) for k in K1B) + " |")
    md += ["", "## 2. 束にシールの関係が入っていたか", "", "| 腕 | 束の関係の述語 | Codex の has_sig_e |", "|---|---|---|"]
    for arm, v in res.items():
        md.append(f"| {arm} | {v['2']} | {v['2 Codex の has_sig_e']} |")
    md += ["", "## 3. 受け手が取り込んだ定義のドアの席の答え（受け取った試行の終わりの状態）", "", "| 腕 | " + " | ".join(K3) + " |", "|---|" + "---:|" * len(K3)]
    for arm, v in res.items():
        md.append(f"| {arm} | " + " | ".join(str(v["3"].get(k, 0)) for k in K3) + " |")
    md += ["", "### 1 × 3（話し手の答え → 取り込んだ定義のドアの答え）", "", "| 腕 | 組み合わせ | 件数 |", "|---|---|---:|"]
    for arm, v in res.items():
        for k, c in sorted(v["1×3"].items(), key=lambda kv: -kv[1]):
            md.append(f"| {arm} | {k} | {c} |")
    md += ["", "### 2 × 3（束のシール → 取り込んだ定義のドアの答え）", "", "| 腕 | 組み合わせ | 件数 |", "|---|---|---:|"]
    for arm, v in res.items():
        for k, c in sorted(v["2×3"].items(), key=lambda kv: -kv[1]):
            md.append(f"| {arm} | {k} | {c} |")
    json.dump(res, open(os.path.join(base, "表.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(base, "表.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
