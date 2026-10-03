"""段 1：分類の表の書き出し（2026-10-03 の委任書）。記録を読むだけ。使い方：stage1_tables.py <組 n3l|ch>  → 標準出力に markdown。
各腕：例外の日のドア・通常の日のドアの正解・外れ・黙り（試行ごとの表 trials.tsv.gz、全 20 種）と、
  外れのうち選び間違い・区別の喪失（selcands の候補の記録：例外の日は全部の答え、通常の日は外れだけを作り直したもの）、
  選び間違いのうち、選ばれた定義と正しく答える定義が同点だった件数。
定め方：
  選び間違い＝候補の中に「その定義を使えば門を通り、正しく答える」定義がある外れ。区別の喪失＝無い外れ（マックの定め方と同じ）。
  選ばれた定義：N3 の腕（flag の select_n3）は N3 の並べ方（N3 → 席の数 → 新しさ → 名前）の一位、今の規則の腕は今の規則の順位 1。
    （作り直しの確かめで、どちらも本物の選びと全件一致している。）
  正しく答える定義のうち一番上：同じ並べ方で一番上のもの。
  同点：N3 の腕は N3 の値が同じ（浮動小数で一致）、今の規則の腕は支持の割合が同じ。"""
import glob
import gzip
import json
import os
import sys
from collections import Counter

H = os.path.expanduser("~")
GROUP = sys.argv[1]
if GROUP == "n3l":
    ARMS = [(f"n3l_w2_{r}_lam{l}", f"{H}/n3lgrid", f"{H}/n3sel_out") for r in ("A", "C") for l in ("0.0187", "0.03", "0.045", "0.065", "0.099", "0.15")]
else:
    ARMS = [(f"ch_w2_{r}_{k}", f"{H}/chance", f"{H}/chance_sel") for k in ("init0", "uabs") for r in ("A", "C")]


def load(d):
    by = {}
    for p in sorted(glob.glob(os.path.join(d, "seed*.cands.jsonl.gz"))):
        for l in gzip.open(p, "rt", encoding="utf-8"):
            c = json.loads(l)
            by.setdefault((c["seed"], c["trial"]), []).append(c)
    return by


def classify(by, n3):
    key = (lambda c: (-c["N3"], -c["分母"], -c["生まれた試行"], c["R"])) if n3 else (lambda c: c["今の規則の順位"])
    val = (lambda c: c["N3"]) if n3 else (lambda c: c["割合"])
    out = Counter()
    for v in by.values():
        if v[0]["本物の当たり"]:
            continue
        v = sorted(v, key=key)
        good = [c for c in v if c["その定義での答え"]["当たり"] and c["その定義での答え"]["門を通る"]]
        out["外れ（作り直した）"] += 1
        if good:
            out["選び間違い"] += 1
            out["同点"] += abs(val(good[0]) - val(v[0])) < 1e-12
        else:
            out["区別の喪失"] += 1
    return out


def cwa(rows):
    c = sum(r[3] == "c" for r in rows)
    w = sum(r[3] == "w" for r in rows)
    return c, w, len(rows) - c - w


print("| 腕 | 選び方 | 例外の日のドア 正解・外れ・黙り | 外れ：選び間違い・区別の喪失 | 選び間違いのうち同点 | 通常の日のドア 正解・外れ・黙り | 外れ：選び間違い・区別の喪失 | 選び間違いのうち同点 |")
print("|---|---|---|---|---:|---|---|---:|")
for arm, run, sel in ARMS:
    tp = f"{run}/tables/{arm}/trials.tsv.gz"
    if not os.path.exists(tp):
        continue
    rows = [l.rstrip("\n").split("\t") for l in gzip.open(tp, "rt", encoding="utf-8")][1:]
    fl = json.load(open(f"{run}/{arm}/flag.json", encoding="utf-8"))
    n3 = bool(fl.get("select_n3"))
    cells = []
    for cue, sd in (("e", "selcands"), ("n", "selcands_n")):
        c, w, a = cwa([r for r in rows if r[5] == "1" and r[7] == cue])
        d = f"{sel}/{sd}/{arm}"
        if os.path.isdir(d):
            k = classify(load(d), n3)
            chk = "" if k["外れ（作り直した）"] == w else f"（★ 作り直した外れ {k['外れ（作り直した）']}）"
            cells += [f"{c:,}・{w:,}・{a:,}", f"{k['選び間違い']:,}・{k['区別の喪失']:,}{chk}", f"{k['同点']:,}"]
        else:
            cells += [f"{c:,}・{w:,}・{a:,}", "（分類なし）", "—"]
    print(f"| {arm} | {'N3' if n3 else '今の規則'} | " + " | ".join(cells) + " |")
