"""欠けた位置にだけ答える：走り終わったあとの表（委任書「欠けた位置にだけ答える」の 5）。★ 数えるだけ。判断しない。
腕ごとに、旗あり（--answer-gap）と旗なし（今日の 11 腕、同じ機械）を並べる。
  表 1：全課題（腕ごと 34,800）を分母にした正解・誤答・棄権。棄権の理由別（no_gap_candidate を分ける）。
  表 2：話した席の対応先 (i)(ii)(iii) × 当たり外れ × 出どころ（roletarget の CSV。今日の 1 と同じ）。
  表 3：「欠けた位置が本人に分かる課題」（伏せた関係の ID が、見えている関係のどれかの引数に入る課題。今日の 3 で 27,725）だけを分母にした正解・誤答・棄権。
材料：台帳（ledgers/cells/*/seed*.jsonl.gz の hit・predicted_edge・abstain_reason）、side の answers.csv（出どころ）、
      roletarget の CSV（tools/roletarget_recompute.py の出力）、今日の 3 の集計（345.json の「ぶら下がり無しの試行」、世界の指紋も比べる）。
使い方  python3.12 tools/answergap_tables.py <345.json> <出力の場所> <腕名>=<旗ありの走行根>,<旗ありの roletarget>,<旗なしの走行根>,<旗なしの roletarget>[,<345.json での腕名>] …"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import sys
from collections import Counter

PER_ARM = 34800


def ledger_rows(root):
    out = {}
    hashes = {}
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz"))):
        s = int(os.path.basename(p)[4:7])
        if not 1 <= s <= 20 or not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            hashes[s] = json.loads(next(f))["world_hash"]
            for line in f:
                r = json.loads(line)
                if r.get("record_type", "trial") != "trial":
                    continue
                out[(s, r["prediction_order"])] = (r.get("predicted_edge") is not None, bool(r.get("hit")), r.get("abstain_reason"))
    return out, hashes


def rt_rows(d):
    out = {}
    for p in glob.glob(os.path.join(d, "*.roletarget.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["answered"] == "1":
                out[(int(r["seed"]), int(r["trial"]))] = r
    return out


def outcome(rows, keys=None):
    c = Counter()
    for k, (spoke, hit, why) in rows.items():
        if keys is not None and k not in keys:
            continue
        c["正解" if spoke and hit else "誤答" if spoke else "棄権"] += 1
        if not spoke:
            c[f"棄権：{why}"] += 1
    return c


def main():
    j345 = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    L1 = ["# 表 1：全課題を分母にした正解・誤答・棄権（旗あり／旗なし）", "", f"分母：全課題（腕ごと {PER_ARM:,}）。", ""]
    L2 = ["# 表 2：話した席の対応先 × 当たり外れ × 出どころ（旗あり／旗なし）", ""]
    L3 = ["# 表 3：欠けた位置が本人に分かる課題だけを分母にした正解・誤答・棄権", "",
          "「欠けた位置が本人に分かる課題」＝伏せた関係の ID が、見えている関係のどれかの引数に入る課題（今日の 3、345.json）。", ""]
    summ = {}
    reasons_all = set()
    data = {}
    for spec in sys.argv[3:]:
        name, rest = spec.split("=", 1)
        parts = rest.split(",")
        on_root, on_rt, off_root, off_rt = parts[:4]
        a345 = parts[4] if len(parts) > 4 else name
        none = {(int(s), t) for s, ts in j345[a345]["ぶら下がり無しの試行"].items() for t in ts}
        wh = {int(s): h for s, h in j345[a345]["world_hash"].items()}
        d = {}
        for tag, root, rt in (("旗あり", on_root, on_rt), ("旗なし", off_root, off_rt)):
            rows, hashes = ledger_rows(root)
            bad = [s for s, h in hashes.items() if wh.get(s) != h]
            known = {k for k in rows if k not in none}
            d[tag] = {"rows": rows, "rt": rt_rows(rt), "known": known, "world_mismatch": bad, "n_runs": len(hashes)}
            reasons_all |= {r[2] for r in rows.values() if not r[0]}
        data[name] = d
    reasons = sorted(x for x in reasons_all if x)
    for name, d in data.items():
        L1 += [f"## {name}", "", "| | 旗あり | 旗なし |", "|---|---:|---:|"]
        c = {t: outcome(d[t]["rows"]) for t in d}
        for k in ["正解", "誤答", "棄権"] + [f"棄権：{r}" for r in reasons]:
            L1.append(f"| {k} | {c['旗あり'][k]:,}（{c['旗あり'][k] / PER_ARM:.1%}） | {c['旗なし'][k]:,}（{c['旗なし'][k] / PER_ARM:.1%}） |")
        L1 += [f"| 走行の本数・世界の指紋が今日の 3 と違う種 | {d['旗あり']['n_runs']}・{d['旗あり']['world_mismatch'] or 'なし'} | "
               f"{d['旗なし']['n_runs']}・{d['旗なし']['world_mismatch'] or 'なし'} |", ""]
        L3 += [f"## {name}", "", "| | 旗あり | 旗なし |", "|---|---:|---:|"]
        c3 = {t: outcome(d[t]["rows"], d[t]["known"]) for t in d}
        n3 = {t: len(d[t]["known"]) for t in d}
        L3.append(f"| 分母 | {n3['旗あり']:,} | {n3['旗なし']:,} |")
        for k in ["正解", "誤答", "棄権"] + [f"棄権：{r}" for r in reasons]:
            L3.append(f"| {k} | {c3['旗あり'][k]:,}（{c3['旗あり'][k] / max(n3['旗あり'], 1):.1%}） | "
                      f"{c3['旗なし'][k]:,}（{c3['旗なし'][k] / max(n3['旗なし'], 1):.1%}） |")
        L3.append("")
        L2 += [f"## {name}", "", "| 出どころ | 対応先 | 当たり外れ | 旗あり | 旗なし |", "|---|---|---|---:|---:|"]
        cc = {}
        for t in d:
            cc[t] = Counter((r["source"], r["cls"], "当たり" if r["hit"] == "1" else "外れ") for r in d[t]["rt"].values())
        for k in sorted(set(cc["旗あり"]) | set(cc["旗なし"])):
            L2.append(f"| {k[0]} | {k[1]} | {k[2]} | {cc['旗あり'][k]:,} | {cc['旗なし'][k]:,} |")
        n_rt = {t: len(d[t]["rt"]) for t in d}
        n_sp = {t: sum(1 for v in d[t]["rows"].values() if v[0]) for t in d}
        L2 += ["", f"- 話した答えの数（台帳）と roletarget の行の数：旗あり {n_sp['旗あり']:,}・{n_rt['旗あり']:,}、旗なし {n_sp['旗なし']:,}・{n_rt['旗なし']:,}", ""]
        summ[name] = {t: {**dict(c[t]), "分かる課題": {**dict(c3[t]), "分母": n3[t]}} for t in d}
    for fn, L in (("1_正解誤答棄権.md", L1), ("2_対応先.md", L2), ("3_分かる課題.md", L3)):
        open(os.path.join(out, fn), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(summ, open(os.path.join(out, "要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out)


if __name__ == "__main__":
    main()
