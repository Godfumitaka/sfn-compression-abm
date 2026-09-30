"""外挿の印の表（委任書 3 の 1〜5）。★ 数えるだけ。判断しない。tools/extrap_marks.py の行（全課題）を、腕ごとにまとめる。
使い方  python3.12 tools/extrap_tables.py <出力の .md> <腕名>=<腕の走行根> [<腕名>=<腕の走行根> …]
  各腕の side/<セル>/seed<種>.extrap.csv が無ければ作る（extrap_marks、並列 8）。種は走行根にある .done の種すべて。
表：
  1 全課題を、主の印（確かめる機会がまだなかった／あった／判定不能）× 答えたか × 課題の成績 × 世界の真偽。粗い・細かい。走行ごとの数は .json。
  2 答えた課題の外れと世界について偽の答えを、エージェントの経験 × 定義の経験（主：証拠が席に届いたか）で。
    「エージェントは中身も確認済みなのに、この定義のこの席には届いていなかった」外れの数。
  3 外れを、覚えているかの四つ（逐語／定義の役割／答えを作れる／実際に使える）で。
  4 答えの出どころ別に、1〜3 の主な数。
  5 粗い・細かいで印が食い違う課題の数。
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool


def _mark_one(args):
    root, cell, seed, out = args
    sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.path.dirname(os.path.abspath(__file__))]
    import extrap_marks
    return extrap_marks.main(root, cell, seed, out)


def rows_of(root):
    jobs = []
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.done"))):
        cell = os.path.basename(os.path.dirname(p))
        seed = int(os.path.basename(p)[4:7])
        out = os.path.join(root, "side", cell, f"seed{seed:03d}.extrap.csv")
        if not os.path.exists(out):
            jobs.append((root, cell, seed, out))
    if jobs:
        with Pool(8) as pool:
            pool.map(_mark_one, jobs)
    rows = []
    for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.extrap.csv"))):
        rows.extend(csv.DictReader(open(p, encoding="utf-8", newline="")))
    return rows


def md_table(title, counter, cols, rows_keys):
    L = [f"#### {title}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for k in rows_keys:
        v = counter.get(k, 0)
        L.append("| " + " | ".join(str(x) for x in (k if isinstance(k, tuple) else (k,))) + f" | {v:,} |")
    return L + [""]


GN = {"粗": "粗い", "細": "細かい"}


def arm_tables(name, rows):
    L = [f"## {name}", "", f"- 課題 {len(rows):,}（走行 {len({r['seed'] for r in rows})} 本）。答えた {sum(r['answered'] == '1' for r in rows):,}。", ""]
    per_run = {}
    for g in ("粗", "細"):
        c = Counter((r[f"{g}_印"], "答えた" if r["answered"] == "1" else "答えない", r["task"], r["world"] or "—") for r in rows)
        L += [f"### 表 1（{GN[g]}状況）：主の印 × 答えたか × 課題 × 世界", "", "| 主の印 | 答えたか | 課題 | 世界 | 数 |", "|---|---|---|---|---:|"]
        for k in sorted(c):
            L.append("| " + " | ".join(k) + f" | {c[k]:,} |")
        L.append("")
        pr = defaultdict(Counter)
        for r in rows:
            pr[r["seed"]][(r[f"{g}_印"], r["task"], r["world"] or "—")] += 1
        per_run[g] = {s: {" / ".join(k): v for k, v in cc.items()} for s, cc in pr.items()}
    ans = [r for r in rows if r["answered"] == "1"]
    for g in ("粗", "細"):
        bad = [r for r in ans if r["task"] == "外れ" or r["world"] == "偽"]
        c = Counter((r[f"{g}_経験"], {"1": "届いた", "0": "届いていない", "": "—"}[r.get(f"{g}_証拠が届いた", "")],
                     r["task"], r["world"]) for r in bad)
        L += [f"### 表 2（{GN[g]}状況）：外れ・世界について偽の答え × エージェントの経験 × 証拠が答えの出どころの席に届いたか", "",
              "| エージェントの経験 | 証拠が席に | 課題 | 世界 | 数 |", "|---|---|---|---|---:|"]
        for k in sorted(c):
            L.append("| " + " | ".join(k) + f" | {c[k]:,} |")
        n_key = sum(1 for r in ans if r["task"] == "外れ" and r[f"{g}_経験"] == "中身も確認済み" and r.get(f"{g}_証拠が届いた") == "0")
        L += ["", f"- 中身も確認済み（エージェント）なのに、この定義のこの席には届いていなかった外れ：{n_key:,}", ""]
        c2 = Counter((r.get(f"{g}_証拠が届いた", ""), r.get(f"{g}_名が保存されている", "")) for r in bad)
        L += [f"- 別の列（{g}）：外れ・偽の答えの（証拠が届いた, 名が保存されている）＝ " +
              "、".join(f"({a or '—'}, {b or '—'}) {v:,}" for (a, b), v in sorted(c2.items())), ""]
    for g in ("粗", "細"):
        miss = [r for r in ans if r["task"] == "外れ"]
        c = Counter((r[f"{g}_逐語"], r[f"{g}_定義の役割"], r.get("答えを作れる", ""), r.get("実際に使える", "")) for r in miss)
        L += [f"### 表 3（{GN[g]}状況）：外れ × 覚えているか", "", "| 逐語 | 定義の役割 | 答えを作れる | 実際に使える | 数 |", "|---|---|---|---|---:|"]
        for k in sorted(c):
            L.append("| " + " | ".join(x if x != "" else "—" for x in k) + f" | {c[k]:,} |")
        L.append("")
    srcs = sorted({r.get("source") or "—" for r in ans})
    L += ["### 表 4：答えの出どころ別（細かい状況）", "",
          "| 出どころ | 答え | 当たり | 外れ | 世界で偽 | 外れのうち確かめる機会がまだなかった | 外れのうち証拠が席に届いていない | 外れのうち答えを作れる |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s in srcs:
        rs = [r for r in ans if (r.get("source") or "—") == s]
        ms = [r for r in rs if r["task"] == "外れ"]
        L.append(f"| {s} | {len(rs):,} | {sum(r['task'] == '当たり' for r in rs):,} | {len(ms):,} | {sum(r['world'] == '偽' for r in rs):,} | "
                 f"{sum(r['細_印'] == '確かめる機会がまだなかった' for r in ms):,} | {sum(r.get('細_証拠が届いた') == '0' for r in ms):,} | "
                 f"{sum(r.get('答えを作れる') == '1' for r in ms):,} |")
    L.append("")
    diff = Counter((r["粗_印"], r["細_印"]) for r in rows if r["粗_印"] != r["細_印"])
    L += ["### 表 5：粗い・細かいで印が食い違う課題", "", f"- 食い違い {sum(diff.values()):,}（全課題 {len(rows):,}）", ""]
    for (a, b), v in sorted(diff.items()):
        L.append(f"  - 粗い「{a}」・細かい「{b}」：{v:,}")
    L.append("")
    return L, per_run


def main():
    out = sys.argv[1]
    L = []
    runs = {}
    for spec in sys.argv[2:]:
        name, root = spec.split("=", 1)
        rows = rows_of(root)
        t, pr = arm_tables(name, rows)
        L += t
        runs[name] = pr
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(runs, open(out[:-3] + "_走行ごと.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out)


if __name__ == "__main__":
    main()
