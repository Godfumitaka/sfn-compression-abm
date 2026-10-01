"""D-最小の外れの中身（2026-10-01 夕方の委任書）の段 3 の表。後づけの集計だけ（模型は動かさない）。
使い方：door_tables.py <腕> <記録の走行の置き場所（side に door.jsonl）> <試行ごとの表 trials.tsv.gz（段 1）>  → 標準出力に markdown。

研究者の側の量の作り方（仮の決定）
  場面の型：試行ごとの店の型（甲／乙）と日（通常 n／例外 e）は台帳（段 1 の試行ごとの表）から。
  定義の材料の場面：side の誕生の記録（試行 t、土台の場面 base_written_at）→ 場面 {t, base}。同化の記録（試行 t、R、base）→ 場面 {t, base}。
    同化の記録の R は、その時点で生きている同じ名前の定義（その名前の一番新しい誕生）に足す。各試行の時点では、その試行より前の材料だけを使う。
  定義の分け方（段 3 の 4）：誕生の材料の二つの場面の日で「両方通常」「一方が例外」「両方例外」。「例外の日の場面から生まれた」＝一方又は両方が例外。
  例外の定義（段 3 の 2 の (a)(b)）：誕生の材料に例外の日の場面がある、又は材料の場面全体のうち例外の日の場面が半分以上。
  外れの経路（例外の日のドアの誤答）：
    (c) 選ばれた定義の材料（誕生・同化）に例外の日の場面が一つでもある（混ざった定義）
    (b) (c) でなく、その時点の記憶に例外の定義があった（選ばれなかった）
    (a) (c) でも (b) でもない（例外の定義が記憶に一つも無かった）
  支持の割合＝選ばれた定義の 支持 ÷ F＋H（1 ＝ 支持 = F＋H）。
  手続きを変えたら（段 3 の 3）：答えた課題で
    P1「支持の割合が 1 のときだけ答える」：割合 < 1 の答えを黙りにする。
    P2「シールの席が名前の違いで合わなかったら黙る」：選ばれた定義のシールの席（F・H）のどれかが「名が違う」なら黙りにする。
    無作為に黙った場合（比べ）：同じ組で、同じ件数 k を答えた課題から無作為に黙りにしたときの期待値（乱数は使わない）：
      避けられた誤答 k × 誤答／答えた、失った正解 k × 正解／答えた。
  例外に正しく答える定義が以前あったか（例外の日のドアの誤答・棄権）：同じ種で、その試行より前に、例外の日のドアに正しく答えた定義
    （答えた定義＝選ばれた定義、名前＋生まれた試行で見分ける）があったか。あれば、その試行の時点で記憶に残っているか。店の型を問わない数と、同じ店の型に限った数。
  外れの答えの出どころ：誤答の答えの出どころ（F_proj＝F の投影、F_fill・H_fill・U_fill＝その状態の席の穴埋め）。
    参考 P3：シールの席（F・H）のどれかが「合った」以外（名が違う・対応先なし・伏せた位置）なら黙りにする（委任書には無い。P2 が 0 件だったときのために並べる）。
    避けられた誤答＝黙りにした誤答、失った正解＝黙りにした正解。
"""
import glob
import gzip
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

ARM, DOOR, TRIALS = sys.argv[1:4]


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


# 試行ごとの表（段 1）
TR = {}
with gzip.open(TRIALS, "rt", encoding="utf-8") as f:
    next(f)
    for line in f:
        x = line.rstrip("\n").split("\t")
        TR[(int(x[0]), int(x[1]))] = {"outcome": x[3], "reason": x[4], "door": x[5] == "1", "type": x[6], "cue": x[7]}

T1 = Counter()          # 段 3 の 1
SEALX = Counter()
ROUTE = Counter()       # 段 3 の 2
ROUTE_A = Counter()     # 参考：例外の日のドアの棄権
B_ROWS = []
C_ROWS = []
P = defaultdict(Counter)    # 段 3 の 3
LIVE = defaultdict(lambda: [0, 0])   # (分け方, 区間) → [生きている数の和, 試行の数]
LIFE = defaultdict(list)
CENS = Counter()
NTR = Counter()
PRIOR = Counter()
SRC = Counter()

for side in sorted(glob.glob(os.path.join(DOOR, "side/*/seed*.door.jsonl*"))):
    seed = int(os.path.basename(side)[4:7])
    sdir = os.path.dirname(side)
    sj = next(p for p in (os.path.join(sdir, f"seed{seed:03d}.jsonl"), os.path.join(sdir, f"seed{seed:03d}.jsonl.gz")) if os.path.exists(p))
    births = {}          # (R, reg) → (t, base)
    assim = defaultdict(list)   # (R, reg) → [(t, base)]
    latest = {}
    ev = []
    for line in opn(sj):
        r = json.loads(line)
        if r.get("kind") in ("birth", "assim"):
            ev.append(r)
    for r in sorted(ev, key=lambda r: (r["trial"], r["kind"] != "birth")):
        if r["kind"] == "birth":
            births[(r["R"], r["trial"])] = (r["trial"], r["base_written_at"])
            latest[r["R"]] = r["trial"]
        else:
            reg = latest.get(r["R"])
            if reg is not None:
                assim[(r["R"], reg)].append((r["trial"], r["base_written_at"]))

    def cue(t):
        return TR[(seed, t)]["cue"]

    def birth_class(k):
        b = births.get(k)
        if b is None:
            return None
        e = (cue(b[0]) == "e") + (b[1] is not None and cue(b[1]) == "e")
        return ("両方通常", "一方が例外", "両方例外")[e]

    def material(k, t):
        b = births.get(k)
        sc = [] if b is None else [b[0]] + ([b[1]] if b[1] is not None else [])
        for ta, ba in assim.get(k, []):
            if ta < t:
                sc += [ta] + ([ba] if ba is not None else [])
        return sc

    def is_exc_def(k, t):
        b = births.get(k)
        if b is None:
            return False
        if cue(b[0]) == "e" or (b[1] is not None and cue(b[1]) == "e"):
            return True
        sc = material(k, t)
        return bool(sc) and sum(cue(s) == "e" for s in sc) * 2 >= len(sc)

    rows = [json.loads(l) for l in opn(side)]
    seen_live = {}
    good = {}    # 例外の日のドアに正しく答えた定義 → 店の型の集合（その試行までに）
    for r in rows:
        t = r["t"]
        info = TR[(seed, t)]
        live = {(R, reg) for R, reg, _n in r["live"]}
        b = min(t // 174, 9)
        for k in live:
            c = birth_class(k)
            if c is not None:
                LIVE[(c, b)][0] += 1
            seen_live.setdefault(k, t)
        for c in ("両方通常", "一方が例外", "両方例外"):
            LIVE[(c, b)][1] += 1
        r["_live"] = live
        sel = r["sel"]
        ratio = None if sel is None else (1.0 if sel[2] == sel[3] else sel[2] / sel[3])
        seal = r["seal"] or []
        seal_fh = [x for x in seal if x[1] in ("F", "H")]
        name_mis = any(x[2] == "名が違う" for x in seal_fh)
        not_ok = any(x[2] != "合った" for x in seal_fh)
        o = info["outcome"]
        if o == "w":
            SRC[("全課題", r["out"][2])] += 1
            if info["door"]:
                SRC[("ドア・例外" if info["cue"] == "e" else "ドア・通常", r["out"][2])] += 1
        if info["door"] and info["cue"] == "e" and o in ("w", "a"):
            any_k = [k for k in good]
            same_k = [k for k, ty in good.items() if info["type"] in ty]
            for lab, ks in (("型を問わない", any_k), ("同じ店の型", same_k)):
                PRIOR[(o, lab, "無かった" if not ks else ("今も記憶にある" if any(k in live for k in ks) else "もう消えた"))] += 1
        if info["door"] and info["cue"] == "e" and o == "c" and sel is not None:
            good.setdefault((sel[0], sel[1]), set()).add(info["type"])
        # 段 3 の 1
        if info["door"] and info["cue"] == "e":
            rk = "選ばれた定義なし" if sel is None else ("1" if ratio == 1.0 else "1 未満")
            T1[(o, rk)] += 1
            sk = "シールの席なし" if not seal else "／".join(sorted({f"{x[1]}:{x[2]}" if x[1] == "U" else x[2] for x in seal}))
            SEALX[(o, sk)] += 1
            if o in ("w", "a") and sel is not None:
                k = (sel[0], sel[1])
                exc_live = [kk for kk in live if is_exc_def(kk, t)]
                mat = material(k, t)
                if any(cue(s) == "e" for s in mat):
                    route = "(c)"
                    if o == "w":
                        C_ROWS.append((birth_class(k), sum(cue(s) == "e" for s in mat) / len(mat), len(mat)))
                elif exc_live:
                    route = "(b)"
                else:
                    route = "(a)"
                (ROUTE if o == "w" else ROUTE_A)[route] += 1
                if route == "(b)" and o == "w":
                    rk_map = {(x[0], x[1]): x for x in r["rank"]}
                    best = max(((rk_map[kk][2] if kk in rk_map else None, kk) for kk in exc_live), key=lambda z: (-1 if z[0] is None else z[0]))
                    B_ROWS.append((seed, t, sel[2], sel[3], ratio, best[0], len(exc_live)))
            elif o in ("w", "a"):
                (ROUTE if o == "w" else ROUTE_A)["選ばれた定義なし"] += 1
        # 段 3 の 3
        if o in ("c", "w"):
            grp = ["全課題", ("ドア・例外" if info["cue"] == "e" else "ドア・通常") if info["door"] else "ドア以外"]
            for g in grp:
                P[g]["答えた"] += 1
                P[g][f"答えた_{o}"] += 1
                if ratio is not None and ratio < 1.0:
                    P[g][f"P1_{o}"] += 1
                if name_mis:
                    P[g][f"P2_{o}"] += 1
                if not_ok:
                    P[g][f"P3_{o}"] += 1
    # 段 3 の 4：寿命（名前を失う＝記憶から消える試行 − 生まれた試行）
    last = rows[-1]["t"]
    present = defaultdict(list)
    for r in rows:
        for k in r["_live"]:
            present[k].append(r["t"])
    for k, ts in present.items():
        c = birth_class(k)
        if c is None:
            continue
        gone = ts[-1] + 1
        if ts[-1] == last:
            CENS[c] += 1
        else:
            LIFE[c].append(gone - k[1])
    NTR[seed] = len(rows)

nseed = len(NTR)
print(f"## {ARM}（種 {nseed}）\n")
print("### 1 例外の日のドアの課題：正誤 × 支持の割合\n")
print("| 支持の割合 | 正解 | 誤答 | 棄権 |\n|---|---:|---:|---:|")
for rk in ("1", "1 未満", "選ばれた定義なし"):
    print(f"| {rk} | {T1[('c', rk)]:,} | {T1[('w', rk)]:,} | {T1[('a', rk)]:,} |")
print("\n選ばれた定義のシールの席の照合（例外の日のドア。席が二つ以上なら / で並べる）\n")
print("| シールの席の照合 | 正解 | 誤答 | 棄権 |\n|---|---:|---:|---:|")
for sk in sorted({k for _, k in SEALX}):
    print(f"| {sk} | {SEALX[('c', sk)]:,} | {SEALX[('w', sk)]:,} | {SEALX[('a', sk)]:,} |")
print("\n### 2 外れの経路（例外の日のドアの誤答。参考に棄権も）\n")
print("| 経路 | 誤答 | 棄権（参考） |\n|---|---:|---:|")
for k in ("(a)", "(b)", "(c)", "選ばれた定義なし"):
    print(f"| {k} | {ROUTE[k]:,} | {ROUTE_A[k]:,} |")
if B_ROWS:
    sel_r = [x[4] for x in B_ROWS]
    exc_r = [x[5] for x in B_ROWS if x[5] is not None]
    print(f"\n(b) の誤答 {len(B_ROWS)} 件：選ばれた定義の支持の割合の中央値 {statistics.median(sel_r):.3f}（1 の件数 {sum(r == 1.0 for r in sel_r)}）、"
          f"記憶にあった例外の定義の支持の割合の最大の中央値 {statistics.median(exc_r) if exc_r else float('nan'):.3f}"
          f"（照合できなかった件数 {sum(x[5] is None for x in B_ROWS)}）。")
    print("\n| 種 | 試行 | 選ばれた定義の支持／F＋H | 割合 | 例外の定義の割合の最大 | 例外の定義の数 |\n|---:|---:|---|---:|---:|---:|")
    for x in B_ROWS[:15]:
        print(f"| {x[0]} | {x[1]} | {x[2]}／{x[3]} | {x[4]:.3f} | {'照合なし' if x[5] is None else f'{x[5]:.3f}'} | {x[6]} |")
    if len(B_ROWS) > 15:
        print(f"\n（最初の 15 件。全件は同じ道具で出せる）")
if C_ROWS:
    sh = [x[1] for x in C_ROWS]
    print(f"\n(c) の誤答 {len(C_ROWS)} 件：選ばれた定義の誕生の分け方 " + "、".join(f"{k} {v}" for k, v in Counter(x[0] for x in C_ROWS).most_common()) +
          f"。材料の場面のうち例外の日の割合：中央値 {statistics.median(sh):.3f}、25%／75% 点 {sorted(sh)[len(sh)//4]:.3f}／{sorted(sh)[3*len(sh)//4]:.3f}、"
          f"材料の場面の数の中央値 {statistics.median([x[2] for x in C_ROWS])}。")
print("\n例外に正しく答える定義が、その試行より前にあったか（例外の日のドアの誤答・棄権）\n")
print("| 課題 | 数え方 | 無かった | あった・今も記憶にある | あった・もう消えた |\n|---|---|---:|---:|---:|")
for o, on in (("w", "誤答"), ("a", "棄権")):
    for lab in ("型を問わない", "同じ店の型"):
        print(f"| {on} | {lab} | {PRIOR[(o, lab, '無かった')]:,} | {PRIOR[(o, lab, '今も記憶にある')]:,} | {PRIOR[(o, lab, 'もう消えた')]:,} |")
print("\n外れの答えの出どころ（誤答）\n")
srcs = sorted({k for _, k in SRC}, key=str)
print("| 課題 | " + " | ".join(str(k) for k in srcs) + " |\n|---|" + "---:|" * len(srcs))
for g in ("全課題", "ドア・通常", "ドア・例外"):
    print(f"| {g} | " + " | ".join(f"{SRC[(g, k)]:,}" for k in srcs) + " |")
print("\n### 3 手続きを変えたら（答えた課題）\n")
print("避けられた誤答・失った正解。かっこの中は、同じ件数を無作為に黙りにしたときの期待値。\n")
print("| 課題 | 答えた（正解／誤答） | P1 黙りにした数 | P1 避けられた誤答 | P1 失った正解 | P2 黙りにした数 | P2 避けられた誤答 | P2 失った正解 | 参考 P3 黙りにした数 | 参考 P3 避けられた誤答 | 参考 P3 失った正解 |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for g in ("全課題", "ドア・通常", "ドア・例外", "ドア以外"):
    q = P[g]
    n = q["答えた"] or 1
    cells = []
    for pp in ("P1", "P2", "P3"):
        k = q[f"{pp}_w"] + q[f"{pp}_c"]
        cells += [f"{k:,}", f"{q[f'{pp}_w']:,}（{k * q['答えた_w'] / n:.1f}）", f"{q[f'{pp}_c']:,}（{k * q['答えた_c'] / n:.1f}）"]
    print(f"| {g} | {q['答えた']:,}（{q['答えた_c']:,}／{q['答えた_w']:,}） | " + " | ".join(cells) + " |")
print("\n### 4 定義の数と寿命（誕生の材料の二つの場面の日で分ける）\n")
print("生きている定義の数（種あたり・試行あたりの平均、174 試行ずつ）\n")
print("| 分け方 | " + " | ".join(f"{b*174}〜" for b in range(10)) + " |\n|---|" + "---:|" * 10)
for c in ("両方通常", "一方が例外", "両方例外"):
    print(f"| {c} | " + " | ".join(f"{LIVE[(c, b)][0] / LIVE[(c, b)][1]:.2f}" if LIVE[(c, b)][1] else "—" for b in range(10)) + " |")
print("\n| 分け方 | 記憶から消えた定義 | 消えるまでの試行数の中央値 | 最後まで残った定義 |\n|---|---:|---:|---:|")
for c in ("両方通常", "一方が例外", "両方例外"):
    v = LIFE[c]
    print(f"| {c} | {len(v):,} | {statistics.median(v) if v else '—'} | {CENS[c]:,} |")
print()
