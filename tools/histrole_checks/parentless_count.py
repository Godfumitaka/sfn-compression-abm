"""親の無い一階の行の数（tools/histrole_checks/birth_paths.py の記録を数える）。★ 数えるだけ。判断しない。
使い方  python3.12 tools/histrole_checks/parentless_count.py <birth_paths の jsonl> <その走行根> <出力 md>
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys


def main():
    src, root, out = sys.argv[1:4]
    births = [json.loads(line) for line in open(src, encoding="utf-8")]
    side = glob.glob(os.path.join(root, "side/*/seed*.jsonl"))[0]
    final = None
    for line in open(side, encoding="utf-8"):
        if line.startswith('{"kind": "final"'):
            final = json.loads(line)
    cons_end = final["constituents_end"]
    sh_end = final["slot_history_end"]
    C = collections.Counter()
    cause = collections.Counter()
    end_state = collections.Counter()
    per_def = collections.Counter()
    last_birth = {}
    for b in births:
        last_birth[b["R"]] = b
    for b in births:
        C["誕生"] += 1
        C["誕生の行"] += len(b["rows"])
        C["誕生で構造上必要な子が欠けて外した行（_drop_childless）"] += b["dropped"]
        n = 0
        for x in b["rows"]:
            if not x["first"]:
                C["高階の行"] += 1
                continue
            C["一階の行"] += 1
            if x["parents_def"]:
                continue
            n += 1
            C["親の無い一階の行"] += 1
            ws = x.get("base_parents") or []
            if not ws:
                cause["土台の場面に親が無い"] += 1
            for w in ws[:1]:
                cause[w["cause"]] += 1
            C["土台の場面で親が二つ以上"] += len(ws) > 1
        per_def[n] += 1
    # 走行末に残っている定義（同じ名前の最後の誕生が今の定義）
    for R, rows in cons_end.items():
        b = last_birth.get(R)
        if b is None:
            C["走行末の定義で誕生の記録が無い"] += 1
            continue
        C["走行末の定義"] += 1
        pl = {x["slot"] for x in b["rows"] if x["first"] and not x["parents_def"]}
        C["走行末の定義で親の無い一階の行を持つもの"] += bool(pl)
        for slot, reg_at, pred, alive in rows:
            if slot in pl:
                st = "F" if alive else ("H" if str(slot) in sh_end.get(R, {}) else "U")
                end_state[st] += 1
                C["走行末の親の無い一階の行"] += 1
    L = ["| 項目 | 数 |", "|---|---:|"]
    for k in ("誕生", "誕生の行", "高階の行", "一階の行", "親の無い一階の行", "土台の場面で親が二つ以上",
              "誕生で構造上必要な子が欠けて外した行（_drop_childless）", "走行末の定義", "走行末の定義で親の無い一階の行を持つもの",
              "走行末の親の無い一階の行", "走行末の定義で誕生の記録が無い"):
        L.append(f"| {k} | {C.get(k, 0):,} |")
    L += ["", "親の無い一階の行の、土台の場面での親が定義に入らなかった理由（誕生の材料と写しから）", "", "| 理由 | 行 |", "|---|---:|"]
    L += [f"| {k} | {v:,} |" for k, v in cause.most_common()]
    L += ["", "定義ごとの親の無い一階の行の数（誕生のとき）", "", "| 親の無い一階の行 | 定義 |", "|---:|---:|"]
    L += [f"| {k} | {v:,} |" for k, v in sorted(per_def.items())]
    L += ["", "走行末の親の無い一階の行の状態", "", "| 状態 | 行 |", "|---|---:|"]
    L += [f"| {k} | {end_state.get(k, 0):,} |" for k in ("F", "H", "U")]
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
