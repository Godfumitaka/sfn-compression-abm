"""全履歴の段階の集計（委任書 2026-10-02 朝）。★ 記録を読んで数えるだけ。研究者の解釈は加えない。
出力：<出力の場所>/集計.json、集計.md、推論の抜き書き.md。
- 最後の試験の 16 問：場合ごとの正解・誤答・黙り・形の崩れ・上限で切れた、最もありそうな答えが正しい数、確信（場合ごと・正誤ごと）。
- 答え方の型（仮の決定）：場合ごとに最も多く答えた記号（4 問の最頻。同数なら記号の名の順で先）の四つ組で分ける。
  ・正しい表：四つとも世界の表どおり
  ・いつも同じ記号：四つとも同じ
  ・店だけで答える：甲・通常＝甲・例外、乙・通常＝乙・例外、甲≠乙
  ・シールだけで答える：甲・通常＝乙・通常、甲・例外＝乙・例外、通常≠例外
  ・その他
  あわせて、16 問の答えの一覧を場合ごとに残す。
- 推論の抜き書き：最後の試験の各問の、推論の中身の最後の 800 文字（記録として。要約はしない）。
- 費用：段階ごと（学習と最後の試験）の入力・出力のトークン、推論のトークン（見積もり：出力 − 本文）、費用（ドル）。
使い方  python3.12 llm_trial/fullhist_report.py <出力の場所>"""
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world as w  # noqa: E402

CASES = ["甲・n", "甲・e", "乙・n", "乙・e"]


def pattern(modal, truth):
    a, b, c, d = (modal[k] for k in CASES)
    if all(modal[k] == truth[k] for k in CASES):
        return "正しい表"
    if a == b == c == d:
        return "いつも同じ記号"
    if a == b and c == d and a != c:
        return "店だけで答える"
    if a == c and b == d and a != b:
        return "シールだけで答える"
    return "その他"


def main():
    out = sys.argv[1]
    res, md, ex = {}, ["# 全履歴の段階の集計", ""], ["# 最後の試験の推論の抜き書き（各問の推論の最後の 800 文字。記録として残す）", ""]
    for p in sorted(glob.glob(os.path.join(out, "段階*_w*.jsonl"))):
        tag = os.path.basename(p)[:-6]
        world = int(tag.split("_w")[1])
        voc = w.vocab(1)
        truth = {f"{t}・{c}": voc[w.door_pred(world, t, c)] for t, c in w.CASES}
        rows = [json.loads(l) for l in open(p, encoding="utf-8")]
        fin = [r for r in rows if r["段"] == "最後の試験"]
        learn = [r for r in rows if r["段"] == "学習"]
        per = {}
        for k in CASES:
            rs = [r for r in fin if r["場合"] == k]
            per[k] = {"判定": dict(Counter(r["判定"] for r in rs)), "最もありそうな答えが正しい": sum(1 for r in rs if r.get("最もありそうな答えが正しい")),
                      "答え": [r.get("answer") for r in rs], "確信": [r.get("confidence") for r in rs], "正解の記号": truth[k]}
        modal = {k: (sorted(Counter(a for a in per[k]["答え"] if a).items(), key=lambda x: (-x[1], x[0])) or [(None, 0)])[0][0] for k in CASES}
        cost = {}
        for name, rs in (("学習", learn), ("最後の試験", fin)):
            ts = [t for r in rs for t in r["試み"]]
            cost[name] = {"問い合わせ": len(ts), "入力のトークン": sum(t["使用量"].get("input_tokens", 0) for t in ts),
                          "出力のトークン": sum(t["使用量"].get("output_tokens", 0) for t in ts),
                          "推論のトークン（見積もり）": sum(t.get("推論のトークン数（見積もり）", 0) for t in ts),
                          "費用（ドル）": round(sum(t["費用"] for t in ts), 4), "上限で切れた": sum(1 for t in ts if t["上限で切れた"])}
        lc = Counter(r["判定"] for r in learn)
        ld = Counter(r["判定"] for r in learn if r["ドアを伏せた"])
        res[tag] = {"場合ごと": per, "最頻の答え": modal, "答え方の型": pattern(modal, truth),
                    "最もありそうな答えが正しい（16 問）": sum(v["最もありそうな答えが正しい"] for v in per.values()),
                    "通過": sum(v["最もありそうな答えが正しい"] for v in per.values()) >= 15 and all(v["最もありそうな答えが正しい"] >= 3 for v in per.values()),
                    "学習（全課題）": dict(lc), "学習（ドア）": dict(ld), "学習の場面の数": len(learn), "費用": cost}
        md += [f"## {tag}（学習 {len(learn)} 場面）", "",
               f"- 最もありそうな答えが正しい：{res[tag]['最もありそうな答えが正しい（16 問）']} / 16。通過：{'通った' if res[tag]['通過'] else '通らない'}。",
               f"- 答え方の型（場合ごとの最頻の答え）：{res[tag]['答え方の型']}（甲・通常 {modal['甲・n']}、甲・例外 {modal['甲・e']}、乙・通常 {modal['乙・n']}、乙・例外 {modal['乙・e']}）。",
               f"- 学習中の判定（全課題）：{dict(lc)}。ドアの場面：{dict(ld)}。", "",
               "| 場合 | 正解の記号 | 正しい（4 問中） | 判定 | 答え | 確信 |", "|---|---|---:|---|---|---|"]
        for k in CASES:
            v = per[k]
            md.append(f"| {k} | {v['正解の記号']} | {v['最もありそうな答えが正しい']} | {v['判定']} | {v['答え']} | {v['確信']} |")
        md += ["", "| 部分 | 問い合わせ | 入力のトークン | 出力のトークン | 推論のトークン（見積もり） | 費用（ドル） | 上限で切れた |", "|---|---:|---:|---:|---:|---:|---:|"]
        for name, c in cost.items():
            md.append(f"| {name} | {c['問い合わせ']} | {c['入力のトークン']:,} | {c['出力のトークン']:,} | {c['推論のトークン（見積もり）']:,} | {c['費用（ドル）']} | {c['上限で切れた']} |")
        md.append("")
        ex += [f"## {tag}", ""]
        for r in fin:
            th = r["試み"][-1].get("推論の中身") or ""
            ex += [f"### 問 {r['i']}（{r['場合']}、正解 {truth[r['場合']]}、答え {r.get('answer')}、確信 {r.get('confidence')}、{r['判定']}）", "", "```", th[-800:], "```", ""]
    json.dump(res, open(os.path.join(out, "集計.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "集計.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    open(os.path.join(out, "推論の抜き書き.md"), "w", encoding="utf-8").write("\n".join(ex) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
