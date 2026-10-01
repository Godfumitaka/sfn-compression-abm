"""格子の集計（予約の委任書の 6）。★ 読むだけ。数を数えて並べるだけで、読み取り・解釈はしない。
出力：<出力の場所>/集計.json、集計.md、メモの全文.md（各系列の 10・20・30・40 場面の後のメモ：LLM が書いた全文と保存した文字列）。
分け方（仮の決定）：
- 学習中は 10 場面ずつ（1〜10、11〜20、21〜30、31〜40 場面目）。ドアの通常＝ドアを伏せた場面でシールが通常、例外＝同じく例外。
- 誤答率＝誤答 ÷ その問いの数（黙り・形の崩れ・上限で切れたも分母に入れる）。「最もありそうな答えが外れ」＝答えが読めて、最もありそうな答えが正しくない数。
- 確信の区切り：[0, 0.5)、[0.5, 0.7)、[0.7, 0.9)、[0.9, 1]。答えが読めた問い（学習と試験の「元」）で、最もありそうな答えが正しい割合。
  確信の高い誤り＝確信 0.9 以上で、最もありそうな答えが正しくない。
- 書き戻しの比べ：ドアの問いのうち、書き戻した店（組 1 は乙）の 2 問と、もう一方の店の 2 問で、判定が「正解」の数の差。
使い方  python3.12 llm_trial/memo_grid_report.py <出力の場所> <費用の控え>"""
import json
import os
import sys
from collections import Counter, defaultdict
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import writeback as wb  # noqa: E402

CONDS = ["full", "L1000", "L400", "L250", "L150", "L100", "c150"]
KINDS = ["正解", "誤答", "黙り", "形の崩れ", "上限で切れた"]
BINS = [(0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
SHOP = wb.shop_for(1)


def tally(rs):
    c = Counter(r["判定"] for r in rs)
    d = {k: c.get(k, 0) for k in KINDS}
    d["数"] = len(rs)
    d["最もありそうな答えが外れ"] = sum(1 for r in rs if "answer" in r and not r.get("最もありそうな答えが正しい"))
    d["誤答率"] = round(d["誤答"] / len(rs), 3) if rs else None
    return d


def group(r):
    if r.get("問の種類") == "共有" or (r["段"] == "学習" and not r["ドアを伏せた"]):
        return "ドア以外"
    return "ドア・通常" if r["場合"].endswith("n") else "ドア・例外"


def series(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    learn = [r for r in rows if r["段"] == "学習"]
    test = [r for r in rows if r["段"] == "試験" and r["k"] >= 0]
    out = {"学習の場面の数": len(learn), "学習": {}, "試験": {}}
    for b in range(4):
        rs = [r for r in learn if b * 10 <= r["i"] < b * 10 + 10]
        out["学習"][f"{b * 10 + 1}〜{b * 10 + 10}"] = {"全課題": tally(rs), **{g: tally([r for r in rs if group(r) == g]) for g in ("ドア・通常", "ドア・例外", "ドア以外")}}
    out["学習"]["全体"] = {"全課題": tally(learn), **{g: tally([r for r in learn if group(r) == g]) for g in ("ドア・通常", "ドア・例外", "ドア以外")}}
    for t in (10, 20, 30, 40):
        rs = [r for r in test if r["t"] == t and r["種類"] == "元"]
        if not rs:
            continue
        out["試験"][t] = {"全課題": tally(rs), "ドア 4 問": tally([r for r in rs if r["問の種類"] == "ドア"]),
                         "ドアの一問ずつ": {r["場合"]: r["判定"] for r in rs if r["問の種類"] == "ドア"},
                         "共有 2 問": tally([r for r in rs if r["問の種類"] == "共有"])}
        nwb = [r for r in rows if r["段"] == "試験" and r["t"] == t and r["種類"] == "書き戻し" and r["k"] < 0]
        if nwb:
            out["試験"][t]["書き戻し"] = "実施できなかった：" + nwb[0]["理由"]
        elif any(r["t"] == t and r["種類"] == "書き戻し" for r in test):
            cmp = {}
            for shop in (SHOP, "甲" if SHOP == "乙" else "乙"):
                v = {kind: sum(1 for r in test if r["t"] == t and r["種類"] == kind and r["問の種類"] == "ドア" and r["場合"].startswith(shop)
                               and r["判定"] == "正解") for kind in ("元", "書き戻し", "対照")}
                cmp[("書き戻した店" if shop == SHOP else "もう一方の店") + f"（{shop}）"] = {
                    "正解の数（2 問中）": v, "書き戻し − 元": v["書き戻し"] - v["元"], "対照 − 元": v["対照"] - v["元"], "書き戻し − 対照": v["書き戻し"] - v["対照"],
                    "一問ずつ": {kind: {r["場合"]: r["判定"] for r in test if r["t"] == t and r["種類"] == kind and r["問の種類"] == "ドア" and r["場合"].startswith(shop)}
                               for kind in ("元", "書き戻し", "対照")}}
            out["試験"][t]["書き戻しの比べ"] = cmp
    # メモの長さ
    recs = [r["書き直し"] for r in learn if "書き直し" in r]
    if recs:
        sv = [x["保存のトークン数"] for x in recs]
        fl = [x["全文のトークン数"] for x in recs if "全文のトークン数" in x]
        cut = [x for x in recs if x.get("切った")]
        out["メモ"] = {"書き直しの数": len(recs), "保存した長さ（最小・中央値・最大）": [min(sv), median(sv), max(sv)],
                     "LLM が書いた長さ（最小・中央値・最大）": [min(fl), median(fl), max(fl)] if fl else None,
                     "切った数": len(cut), "切った割合": round(len(cut) / len(recs), 3),
                     "切った位置が関係式の途中": sum(1 for x in cut if x["関係式の途中"]), "切った位置が文の途中": sum(1 for x in cut if x["文の途中"]),
                     "形の崩れ（前のメモのまま）": sum(1 for x in recs if x["結果"] == "形の崩れ"),
                     "一度書き直させた（比べの条件）": sum(1 for x in recs if x.get("書き直しの回数") == 2),
                     "保存した長さの並び": sv}
    # 確信
    ans = [r for r in learn + [r for r in test if r["種類"] == "元"] if "answer" in r]
    cal = {}
    for lo, hi in BINS:
        rs = [r for r in ans if lo <= r["confidence"] < hi]
        cal[f"{lo}〜{min(hi, 1)}"] = {"数": len(rs), "最もありそうな答えが正しい割合": round(sum(r["最もありそうな答えが正しい"] for r in rs) / len(rs), 3) if rs else None}
    out["確信"] = {"区切り": cal, "確信 0.9 以上の誤り": sum(1 for r in ans if r["confidence"] >= 0.9 and not r["最もありそうな答えが正しい"]),
                 "答えが読めた数": len(ans)}
    # 推論・上限
    tries = [t for r in learn + test for t in r["試み"]]
    out["予測の出力"] = {"問い合わせの数": len(tries), "出力のトークン（中央値・最大）": [median(t["使用量"]["output_tokens"] for t in tries), max(t["使用量"]["output_tokens"] for t in tries)],
                     "推論の文字数（中央値）": median(t["推論の文字数"] for t in tries), "上限で切れた": sum(1 for t in tries if t["上限で切れた"])}
    wt = [t for x in recs for t in x["試み"]]
    if wt:
        out["書き直しの出力"] = {"問い合わせの数": len(wt), "出力のトークン（中央値・最大）": [median(t["使用量"]["output_tokens"] for t in wt), max(t["使用量"]["output_tokens"] for t in wt)],
                          "推論の文字数（中央値）": median(t["推論の文字数"] for t in wt), "上限で切れた": sum(1 for t in wt if t["上限で切れた"])}
    return out, learn


def costs(ledger):
    c = defaultdict(float)
    for l in open(ledger, encoding="utf-8"):
        d = json.loads(l)
        p = d["what"].split()
        if p[0] != "格子":
            continue
        c[(p[1], p[2], p[3])] += d["cost"]
    return c


def main():
    out, ledger = sys.argv[1], sys.argv[2]
    res, texts = {}, []
    for world in (2, 1):
        for cond in CONDS:
            p = os.path.join(out, f"w{world}_{cond}.jsonl")
            if not os.path.exists(p):
                continue
            s, learn = series(p)
            res[f"w{world}_{cond}"] = s
            for r in learn:
                if r["i"] + 1 in (10, 20, 30, 40) and "書き直し" in r:
                    x = r["書き直し"]
                    texts += [f"## 世界 {world}・{cond}・{r['i'] + 1} 場面の後（{x['結果']}、保存 {x['保存のトークン数']} トークン"
                              + (f"、LLM が書いた全文 {x['全文のトークン数']} トークン" if "全文のトークン数" in x else "") + "）", "",
                              "保存した文字列：", "", "```", x["保存"], "```", ""]
                    if x.get("切った"):
                        texts += ["LLM が書いた全文：", "", "```", x["全文"], "```", ""]
    dp = os.path.join(out, "w2_diag.jsonl")
    if os.path.exists(dp):
        rows = [json.loads(l) for l in open(dp, encoding="utf-8")]
        info = json.load(open(os.path.join(out, "w2_diag_メモ.json"), encoding="utf-8")) if os.path.exists(os.path.join(out, "w2_diag_メモ.json")) else {}
        res["診断"] = {m: {"メモ": info.get(m), "全体": tally([r for r in rows if r["メモ"] == m]),
                         "場合ごと": {c: tally([r for r in rows if r["メモ"] == m and r["場合"] == c]) for c in ("甲・n", "甲・e", "乙・n", "乙・e")}}
                     for m in ("A", "B")}
    c = costs(ledger)
    res["費用"] = {" ".join(k): round(v, 4) for k, v in sorted(c.items())}
    res["費用の合計（格子）"] = round(sum(c.values()), 4)
    json.dump(res, open(os.path.join(out, "集計.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "メモの全文.md"), "w", encoding="utf-8").write("# 各時点のメモの全文（記録）\n\n" + "\n".join(texts))
    print(json.dumps({k: v for k, v in res.items()}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
