"""異常を数える仕組みの集計（委任書 2026-10-04「異常を数える仕組みの確認」段 2）。★ 走行の記録を読むだけ。コードも記録も変えない。
各走行の根（<根>/manifest.jsonl。tools/v3_run.py が種ごとに 1 行、各モジュールの STATS を rec[<モジュール>] に写したもの。tools/v3_run.py:539〜592・:857）
を読み、モジュール・項目ごとに、全部の種の和・0 でない種の数・最大を出す。数値の項目だけ（真偽・文字列・dict・list は除く）。
「起きたときだけ作られる項目」（STATS.get(k, 0)＋1 の形）は、起きなかった種の manifest には現れないので、現れない種は 0 と数える。
ZERO（下の一覧）に挙げた項目は「0 であるべき」とコードの注釈から読んだもの（control/2026-10-04_異常を数える仕組み_マック.md の表）。
  0 でない値があれば「0 であるべきなのに 0 でない」の表に出す。
使い方  python3.12 tools/stats_audit.py <出力の .md> <走行の根> [<走行の根> …]（種 21〜40 の行は読まない）"""
import json
import os
import sys
from collections import defaultdict

# 注釈に「0 のはず」又は守るべき決まりの違反を数えると書かれている項目（3380344・88e0e38・24b7c74 で同じ）：
#   deathterms.v_mismatch（tools/deathterms.py:7 の注釈「…一致しない数を STATS["v_mismatch"] に数える（0 のはず）」、:53 で増やす）
#   checks_v37.rule1_violations・rule2_violations（tools/checks_v37.py:4,5 の決まり 1・2、:67・:45 で増やす）
#   v32.rn_differ_ident（tools/v32.py:124 の注釈「元の判断を再現するかの確かめ」、:186 で増やす。「0 のはず」とは書かれていない）
ZERO: dict = {"deathterms": {"v_mismatch"}, "checks_v37": {"rule1_violations", "rule2_violations"}, "v32": {"rn_differ_ident"}}


def main():
    out, roots = sys.argv[1], sys.argv[2:]
    md = ["| 走行 | 種の数 | モジュール | 項目 | 全部の種の和 | 0 でない種 | 最大 |", "|---|---:|---|---|---:|---:|---:|"]
    bad = ["| 走行 | モジュール | 項目 | 全部の種の和 | 0 でない種 | 最大 |", "|---|---|---|---:|---:|---:|"]
    for root in roots:
        name = os.path.basename(root.rstrip("/"))
        rows = []
        for line in open(os.path.join(root, "manifest.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if not (1 <= int(r.get("seed", 0)) <= 20 or int(r.get("seed", 0)) >= 1000):
                continue
            rows.append(r)
        agg = defaultdict(lambda: [0, 0, None])
        for r in rows:
            for mod, v in r.items():
                if not isinstance(v, dict):
                    continue
                for k, x in v.items():
                    if isinstance(x, bool) or not isinstance(x, (int, float)):
                        continue
                    a = agg[(mod, k)]
                    a[0] += x
                    a[1] += int(x != 0)
                    a[2] = x if a[2] is None else max(a[2], x)
        for (mod, k), (s, nz, mx) in sorted(agg.items()):
            md.append(f"| {name} | {len(rows)} | {mod} | {k} | {s} | {nz} | {mx} |")
            if k in ZERO.get(mod, ()) and nz:
                bad.append(f"| {name} | {mod} | {k} | {s} | {nz} | {mx} |")
        mods = {m for r in rows for m, v in r.items() if isinstance(v, dict)}
        for mod, ks in ZERO.items():
            for k in ks:
                if (mod, k) in agg:
                    continue
                if mod in mods:
                    md.append(f"| {name} | {len(rows)} | {mod} | {k}（モジュールは記録にあり、この項目は無い） | — | — | — |")
                else:
                    md.append(f"| {name} | {len(rows)} | {mod} | {k}（モジュールが記録に無い＝その旗が切れていて測っていない） | — | — | — |")
    open(out, "w", encoding="utf-8").write("\n".join(["## 0 であるべきなのに 0 でない項目", ""] + bad + ["", "## 全部の項目", ""] + md) + "\n")
    print("\n".join(bad))


if __name__ == "__main__":
    main()
