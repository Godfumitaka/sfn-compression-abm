"""直す前と後の、走行末の H の席の履歴（委任書「…席の履歴の直し…」の 3）。★ 数えるだけ。判断しない。
H の席＝走行末に死んでいる行で、席の履歴の鍵があるもの（tools/v39.py seat_state）。
席ごとに：一階か高階か（台帳の登録の記録の arg_kinds：引数に同じ定義の関係を含めば高階）、生まれたときの述語（その定義の最後の誕生の記録）、
  履歴の述語の種類数（回数 1 以上）、履歴の回数の和、その席の元の述語の回数の割合。
使い方  python3.12 tools/histrole_checks/hist_compare.py <出力 md> <名前=走行根> ...   （走行根の ledgers/cells/*/seed*.jsonl.gz と side/*/seed*.jsonl）
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import statistics
import sys


STATE_N = {}


def one(root):
    import collections
    STATE_N[root] = collections.Counter()
    led = sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz")))[0]
    cell = os.path.basename(os.path.dirname(led))
    sd = os.path.basename(led)[:-len(".jsonl.gz")]
    side = os.path.join(root, "side", cell, f"{sd}.jsonl")
    birth = {}   # R → {slot: (述語, 一階か)}
    with gzip.open(led, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            reg = r.get("registration_event")
            if reg and not reg.get("was_extension"):
                birth[reg["R"]] = {c["slot_index"]: (c["predicate"], all(k == "entity" for k in c["arg_kinds"]))
                                   for c in reg["constituents"]}
    final = None
    for line in open(side, encoding="utf-8"):
        if line.startswith('{"kind": "final"'):
            final = json.loads(line)
    sh = final["slot_history_end"]
    seats = []
    for R, rows in final["constituents_end"].items():
        for slot, reg_at, pred, alive in rows:
            h = sh.get(R, {}).get(str(slot))
            STATE_N[root][("一階" if birth[R][slot][1] else "高階", "F" if alive else ("H" if h is not None else "U"))] += 1
            if h is None:
                continue
            bp, first = birth[R][slot]
            counts = h if isinstance(h, dict) else {p: 1 for p in h}
            tot = sum(counts.values())
            seats.append({"R": R, "slot": slot, "状態": "F" if alive else "H", "一階": first, "元の述語": bp, "種類": sum(1 for v in counts.values() if v >= 1),
                          "回数": tot, "元の述語の割合": (counts.get(bp, 0) / tot) if tot else None,
                          "履歴": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))})
    return seats


def summ(seats):
    if not seats:
        return {"席": 0}
    k = [s["種類"] for s in seats]
    sh = [s["元の述語の割合"] for s in seats if s["元の述語の割合"] is not None]
    return {"席": len(seats), "種類の平均": statistics.mean(k), "種類の中央値": statistics.median(k), "種類の最大": max(k),
            "種類が1の席": sum(1 for x in k if x == 1), "履歴が空の席": sum(1 for s in seats if s["回数"] == 0),
            "元の述語の割合の平均": statistics.mean(sh) if sh else None, "元の述語の割合の中央値": statistics.median(sh) if sh else None,
            "元の述語が1位の席": sum(1 for s in seats if s["回数"] and s["履歴"].get(s["元の述語"], 0) == max(s["履歴"].values())),
            "元の述語が無い席": sum(1 for s in seats if s["回数"] and s["履歴"].get(s["元の述語"], 0) == 0)}


def main():
    out = sys.argv[1]
    runs = [x.split("=", 1) for x in sys.argv[2:]]
    data = {n: one(r) for n, r in runs}
    L = ["| 走行 | 階 | H の席 | 種類の平均 | 種類の中央値 | 種類の最大 | 種類が 1 の席 | 履歴が空の席 | 元の述語の割合の平均 | 同・中央値 | 元の述語が 1 位の席 | 元の述語が無い席 |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    f = lambda v: "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else f"{v:,}")  # noqa: E731
    for n, seats in data.items():
        for lab, sel in (("一階", True), ("高階", False)):
            s = summ([x for x in seats if x["一階"] == sel and x["状態"] == "H"])
            L.append(f"| {n} | {lab} | {f(s.get('席'))} | {f(s.get('種類の平均'))} | {f(s.get('種類の中央値'))} | {f(s.get('種類の最大'))} | "
                     f"{f(s.get('種類が1の席'))} | {f(s.get('履歴が空の席'))} | {f(s.get('元の述語の割合の平均'))} | {f(s.get('元の述語の割合の中央値'))} | "
                     f"{f(s.get('元の述語が1位の席'))} | {f(s.get('元の述語が無い席'))} |")
    L += ["", "参考（記録だけ）：走行末に生きている席（F）のうち、席の履歴の鍵があるもの。F→H のときにこの履歴が H の答えになる。", "", L[0].replace("H の席", "F の席（履歴あり）"), L[1]]
    for n, seats in data.items():
        for lab, sel in (("一階", True), ("高階", False)):
            s = summ([x for x in seats if x["一階"] == sel and x["状態"] == "F"])
            L.append(f"| {n} | {lab} | {f(s.get('席'))} | {f(s.get('種類の平均'))} | {f(s.get('種類の中央値'))} | {f(s.get('種類の最大'))} | "
                     f"{f(s.get('種類が1の席'))} | {f(s.get('履歴が空の席'))} | {f(s.get('元の述語の割合の平均'))} | {f(s.get('元の述語の割合の中央値'))} | "
                     f"{f(s.get('元の述語が1位の席'))} | {f(s.get('元の述語が無い席'))} |")
    L += ["", "参考（記録だけ）：走行末の席の状態の数（走行末に残っている定義の全行）", "", "| 走行 | 階 | F | H | U |", "|---|---|---:|---:|---:|"]
    for (n, r) in runs:
        for lab in ("一階", "高階"):
            c = STATE_N[r]
            L.append(f"| {n} | {lab} | {c[(lab, 'F')]:,} | {c[(lab, 'H')]:,} | {c[(lab, 'U')]:,} |")
    L += ["", "H の席ごとの一覧（階・定義・席の順。履歴は回数の多い順）", ""]
    names = list(data)
    L.append("| " + " | ".join(f"{n}：階・定義・席・元の述語・種類・元の述語の割合・履歴" for n in names) + " |")
    L.append("|" + "---|" * len(names))
    cols = [sorted((s for s in data[n] if s["状態"] == "H"), key=lambda s: (not s["一階"], s["R"], s["slot"])) for n in names]
    for i in range(max(len(c) for c in cols)):
        cells = []
        for c in cols:
            if i < len(c):
                s = c[i]
                sh = "—" if s["元の述語の割合"] is None else f"{s['元の述語の割合']:.3f}"
                hist = "、".join(f"{p} {v:g}" for p, v in s["履歴"].items())
                cells.append(f"{'一階' if s['一階'] else '高階'}・{s['R']}・{s['slot']}・{s['元の述語']}・{s['種類']}・{sh}・{hist}")
            else:
                cells.append("")
        L.append("| " + " | ".join(cells) + " |")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(data, open(out.replace(".md", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(L[:2 + 2 * len(names)] + L[2 + 2 * len(names):6 + 4 * len(names)]))


if __name__ == "__main__":
    main()
