"""穴出しの候補 6：U の席の照合（後づけの集計。走行はしない）。
(A) 同化のときの U の席の照合：side/<セル>/seed<種>.routing.jsonl の kind=m1（同化＝誕生でない m1）で、state_before＝U の席が
    今の場面の見えている関係に写ったとき、その関係の述語が、その席の生まれたときの名（同じ定義の誕生の m1 の hist_after）と同じか違うか。
    比べのため F・H の席も同じ形で数える（F は名が合わないと写らない・H は履歴の名）。
(B) 選ばれる頻度：door.jsonl（--dump-door）の選ばれた定義について、U の席の割合（U＝誕生の席の数 − F＋H）で分け、
    その定義の誕生の場面（今の場面の側）と今の場面の店の型・日（シール）が違う選ばれ方の数と、そのときの正誤。
使い方：c6_u_match.py A <腕の置き場所>… ／ c6_u_match.py B <腕の置き場所> <試行ごとの表 trials.tsv.gz>"""
import glob
import gzip
import json
import os
import sys
from collections import Counter, defaultdict


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


def births_of(sj):
    b = {}
    for line in opn(sj):
        r = json.loads(line)
        if r.get("kind") == "birth":
            b[(r["R"], r["trial"])] = r
    return b


def side_json(p, seed):
    d = os.path.dirname(p)
    return next(q for q in (os.path.join(d, f"seed{seed:03d}.jsonl"), os.path.join(d, f"seed{seed:03d}.jsonl.gz")) if os.path.exists(q))


mode = sys.argv[1]
if mode == "A":
    print("| 腕 | 席の状態（同化の前） | 見えている関係に写った | うち生まれたときの名と同じ | 違う |\n|---|---|---:|---:|---:|")
    EX = []
    for root in sys.argv[2:]:
        arm = os.path.basename(root.rstrip("/"))
        c = Counter()
        for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.routing.jsonl*"))):
            seed = int(os.path.basename(p)[4:7])
            births = births_of(side_json(p, seed))
            born_name = {}
            latest = {}
            for line in opn(p):
                r = json.loads(line)
                if r.get("kind") != "m1":
                    continue
                key = (r["R"], r["trial"])
                if key in births and not r.get("was_extension"):
                    latest[r["R"]] = r["trial"]
                    for s in r["seats"]:
                        h = s.get("hist_after") or {}
                        born_name[(r["R"], r["trial"], s["slot"])] = max(h, key=h.get) if h else None
                    continue
                reg = latest.get(r["R"])
                if reg is None:
                    continue
                for s in r["seats"]:
                    st = s.get("state_before")
                    if st not in ("F", "H", "U") or not s.get("mapped_visible"):
                        continue
                    pr = dict((x[0], x[1]) for x in s.get("position_relations") or [])
                    mp = pr.get(s.get("mapped_to"))
                    bn = born_name.get((r["R"], reg, s["slot"]))
                    if mp is None or bn is None:
                        continue
                    c[(st, "n")] += 1
                    c[(st, "same" if mp == bn else "diff")] += 1
                    if st == "U" and mp != bn and len(EX) < 4:
                        EX.append((arm, seed, r["trial"], r["R"], s["slot"], bn, mp))
        for st in ("F", "H", "U"):
            n = c[(st, "n")]
            if n:
                print(f"| {arm} | {st} | {n:,} | {c[(st, 'same')]:,}（{c[(st, 'same')] / n:.1%}） | {c[(st, 'diff')]:,}（{c[(st, 'diff')] / n:.1%}） |")
    print("\n例（U の席が、生まれたときと違う名の関係に写った同化）：")
    for e in EX:
        print(f"- {e[0]} 種 {e[1]} 試行 {e[2]}：定義 {e[3]} の席 {e[4]}（生まれたときの名 {e[5]}）が、今の場面の {e[6]} の関係に写った")
else:
    root, trials = sys.argv[2], sys.argv[3]
    arm = os.path.basename(root.rstrip("/"))
    TR = {}
    with gzip.open(trials, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            x = line.rstrip("\n").split("\t")
            TR[(int(x[0]), int(x[1]))] = (x[3], x[5] == "1", x[6], x[7])
    agg = defaultdict(Counter)
    for p in sorted(glob.glob(os.path.join(root, "side/*/seed*.door.jsonl*"))):
        seed = int(os.path.basename(p)[4:7])
        births = births_of(side_json(p, seed))
        for line in opn(p):
            r = json.loads(line)
            sel = r["sel"]
            if sel is None or r["out"][0] != "Edge":
                continue
            b = births.get((sel[0], sel[1]))
            if b is None:
                continue
            total = b.get("m_alloc") or 0
            u = max(total - sel[3], 0)
            ub = "U なし" if u == 0 else ("U 半分未満" if u * 2 < total else "U 半分以上")
            o, door, ty, cue = TR[(seed, r["t"])]
            _o, _d, bty, bcue = TR[(seed, sel[1])]
            kind = ("型も日も同じ" if (ty == bty and cue == bcue) else
                    "型が違う" if ty != bty and cue == bcue else "日（シール）が違う" if ty == bty else "型も日も違う")
            agg[(ub, kind)]["n"] += 1
            agg[(ub, kind)][o] += 1
    print(f"#### {arm}：答えた課題の、選ばれた定義の U の席の割合 × 誕生の場面との違い（正解／誤答）\n")
    print("| U の席 | 型も日も同じ | 型が違う | 日（シール）が違う | 型も日も違う |\n|---|---|---|---|---|")
    for ub in ("U なし", "U 半分未満", "U 半分以上"):
        print(f"| {ub} | " + " | ".join(f"{agg[(ub, k)]['n']:,}（{agg[(ub, k)]['c']:,}／{agg[(ub, k)]['w']:,}）"
                                         for k in ("型も日も同じ", "型が違う", "日（シール）が違う", "型も日も違う")) + " |")
    print()
