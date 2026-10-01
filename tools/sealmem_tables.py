"""誤りの印と記憶の量の表（委任書 2026-10-02 朝）。★ tools/sealmem.py の出力を読むだけ。数を並べるだけで、解釈はしない。
出力：<出力>/印.md（問い 1）、<出力>/記憶の量.md（問い 2）、<出力>/表.json。
問い 1 の決め方（仮の決定。結果を見る前に固定）：
- 支持の割合の区間：1、[0.9, 1)、[0.75, 0.9)、[0.5, 0.75)、[0, 0.5)。
- U の席の割合は、正解と外れのそれぞれで、最小・第 1 四分位・中央値・第 3 四分位・最大。
- 答え方 P1「支持 1 のときだけ答える」：支持の割合 < 1 なら黙る。
- 答え方 P2「選ばれた定義のシールの席が U なら黙る」：シールの席の分類が U なら黙る（U は席の状態で決まるので、照合で決めても名前で決めても同じ）。
- 答え方 P3「U の席の割合が q 以上なら黙る」：q は同じ腕の種 1〜10 の答えた全課題で決め、種 11〜20 で評価する。q の候補は種 1〜10 に出た
  U の席の割合の値と「黙らない」。決め方は二つ（どちらも仮の決定。両方出す）：
    (a) 避けた外れ − 失った正解 が最大（同点なら q の大きい方）
    (b) 避けた外れの割合 − 失った正解の割合 が最大（同点なら q の大きい方）
  世界 1 には、同じ腕（同じ A・C と λ）の世界 2 で決めた q と、世界 1 の種 1〜10 で決めた q の両方を当てる。
- 無作為に黙らせた期待値：同じ群（全課題・ドアの通常・例外）の中で、同じ数を無作為に黙らせたときの、避ける外れ k×W/N と失う正解 k×C/N。
- P1・P2 は、種 11〜20 と、種 1〜20 の両方で出す。
問い 2：
- 種ごとの平均の記憶のビット＝その走行の全試行の C_end の平均。例外の日のドアの外れ＝答えたドアの課題で、例外の日に外れた数。
- 174 試行ごとの区間（10 区間）：各量を、走行ごとに区間の中で平均（数は区間の中の和）し、20 走行で平均する。
  定義一本あたりの記憶のビット＝（骨組み S ＋ 席の 2 ビット ＋ H の中身 ＋ F の中身）÷ 定義の数（試行ごと。定義が 0 の試行は除く）。
- 分解：全試行・20 走行の平均で、C＝G＋Idef＋S＋seat2＋Hc＋Fc の各項の F − A。さらに「定義の部分」D＝S＋seat2＋Hc＋Fc を、
  D＝n×b（n：定義の数、b：一本あたり）として、ΔD＝b̄Δn＋n̄Δb（b̄・n̄ は A と F の平均。対称の分け方。仮の決定）に分ける。
使い方  python3.12 tools/sealmem_tables.py <sealmem の出力の場所> <出力の場所>"""
import csv
import glob
import json
import os
import random
import sys
from collections import Counter, defaultdict
from statistics import mean, median, quantiles

ARMS1 = ["A_lam0187", "A_lam0990", "A_lam020", "C_lam0187", "C_lam0990", "C_lam020"]
SR_BINS = [("1", 1.0, 1.01), ("0.9〜1", 0.9, 1.0), ("0.75〜0.9", 0.75, 0.9), ("0.5〜0.75", 0.5, 0.75), ("0〜0.5", 0.0, 0.5)]
GROUPS = [("全課題", lambda r: True), ("ドア・通常", lambda r: r["door"] == 1 and r["shop_cue"] == "n"), ("ドア・例外", lambda r: r["door"] == 1 and r["shop_cue"] == "e")]
SEAL_ORDER = ["F で合った", "H で合った", "F で合わなかった（対応先なし）", "H で合わなかった（対応先なし）", "F で別の関係に写った", "H で別の関係に写った",
              "F で名前が違って合わなかった", "H で名前が違って合わなかった", "U", "シールの席なし"]


def load_ans(base, arm):
    rows = []
    for p in sorted(glob.glob(os.path.join(base, arm, "seed*.answers.csv"))):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            rows.append({"seed": int(r["seed"]), "trial": int(r["trial"]), "door": int(r["door"]), "shop_cue": r["shop_cue"], "shop_type": r["shop_type"],
                         "hit": int(r["hit"]), "sr": float(r["support_ratio"]), "u": float(r["u_ratio"]), "seal_map": r["seal_map"], "seal_name": r["seal_name"],
                         "seal_seats": int(r["seal_seats"])})
    return rows


def q4(xs):
    if not xs:
        return None
    if len(xs) == 1:
        return [round(xs[0], 3)] * 5
    q = quantiles(xs, n=4, method="inclusive")
    return [round(v, 3) for v in (min(xs), q[0], q[1], q[2], max(xs))]


def evaluate(rows, abstain):
    out = {}
    for g, f in GROUPS:
        rs = [r for r in rows if f(r)]
        N, C = len(rs), sum(r["hit"] for r in rs)
        Wn = N - C
        ab = [r for r in rs if abstain(r)]
        k = len(ab)
        out[g] = {"答えた数": N, "正解": C, "外れ": Wn, "黙らせた数": k, "避けた外れ": sum(1 - r["hit"] for r in ab), "失った正解": sum(r["hit"] for r in ab),
                  "無作為の期待値：避けた外れ": round(k * Wn / N, 2) if N else 0.0, "無作為の期待値：失った正解": round(k * C / N, 2) if N else 0.0}
    return out


def choose_q(rows):
    vals = sorted({r["u"] for r in rows}) + [9.0]
    C = sum(r["hit"] for r in rows)
    Wn = len(rows) - C
    best = {}
    for q in vals:
        ab = [r for r in rows if r["u"] >= q]
        aw = sum(1 - r["hit"] for r in ab)
        lc = sum(r["hit"] for r in ab)
        sa = aw - lc
        sb = (aw / Wn if Wn else 0.0) - (lc / C if C else 0.0)
        for key, s in (("a", sa), ("b", sb)):
            if key not in best or s > best[key][0] or (s == best[key][0] and q > best[key][1]):
                best[key] = (s, q)
    return {k: v[1] for k, v in best.items()}


def part1(base):
    res = {}
    md = ["# 問い 1：外れに、本人に見える印があるか", ""]
    qs = {}
    for w in (2, 1):
        for a in ARMS1:
            arm = f"cw{w}_{a}"
            rows = load_ans(base, arm)
            if not rows:
                continue
            r1 = {}
            # 表 1：例外の日（と通常の日）のドア
            for cue, cname in (("e", "例外"), ("n", "通常")):
                rs = [r for r in rows if r["door"] == 1 and r["shop_cue"] == cue]
                t1 = {}
                for hv, hname in ((1, "正解"), (0, "外れ")):
                    x = [r for r in rs if r["hit"] == hv]
                    t1[hname] = {"数": len(x),
                                 "支持の割合": {b: sum(1 for r in x if lo <= r["sr"] < hi) for b, lo, hi in SR_BINS},
                                 "U の席の割合（最小・Q1・中央値・Q3・最大）": q4([r["u"] for r in x]),
                                 "シールの席（照合で）": dict(Counter(r["seal_map"] for r in x)),
                                 "シールの席（名前で）": dict(Counter(r["seal_name"] for r in x)),
                                 "シールの席が二つ以上": sum(1 for r in x if r["seal_seats"] >= 2)}
                r1[f"表1 ドア・{cname}"] = t1
            # 表 2：答え方
            tr, te = [r for r in rows if r["seed"] <= 10], [r for r in rows if r["seed"] >= 11]
            q = choose_q(tr)
            qs[arm] = q
            pol = {"P1 支持 1 のときだけ答える（種 11〜20）": evaluate(te, lambda r: r["sr"] < 1.0),
                   "P1 支持 1 のときだけ答える（種 1〜20）": evaluate(rows, lambda r: r["sr"] < 1.0),
                   "P2 シールの席が U なら黙る（種 11〜20）": evaluate(te, lambda r: r["seal_map"] == "U"),
                   "P2 シールの席が U なら黙る（種 1〜20）": evaluate(rows, lambda r: r["seal_map"] == "U")}
            for key in ("a", "b"):
                pol[f"P3({key}) U の席の割合 ≥ q（q＝{q[key]:.4g}、この腕の種 1〜10 で決めた。種 11〜20）"] = evaluate(te, lambda r, qq=q[key]: r["u"] >= qq)
                if w == 1:
                    q2 = qs.get(f"cw2_{a}", {}).get(key)
                    if q2 is not None:
                        pol[f"P3({key}) U の席の割合 ≥ q（q＝{q2:.4g}、世界 2 の同じ腕で決めた。種 11〜20）"] = evaluate(te, lambda r, qq=q2: r["u"] >= qq)
                        pol[f"P3({key}) U の席の割合 ≥ q（q＝{q2:.4g}、世界 2 の同じ腕で決めた。種 1〜20）"] = evaluate(rows, lambda r, qq=q2: r["u"] >= qq)
            r1["表2 答え方"] = pol
            # 表 3：種ごと
            per = {}
            for s in range(1, 21):
                x = [r for r in rows if r["seed"] == s and r["door"] == 1 and r["hit"] == 0]
                xe = [r for r in x if r["shop_cue"] == "e"]
                per[s] = {"ドアの外れ": len(x), "例外の日のドアの外れ": len(xe),
                          "外れのうちシールの席が U": sum(1 for r in x if r["seal_map"] == "U"),
                          "例外の日の外れのうちシールの席が U": sum(1 for r in xe if r["seal_map"] == "U")}
            r1["表3 種ごと"] = per
            res[arm] = r1
            # 書き出し
            md += [f"## {arm}", ""]
            for cname in ("例外", "通常"):
                t1 = r1[f"表1 ドア・{cname}"]
                md += [f"### 表 1 ドア・{cname}の日（答えた課題）", "",
                       "| | 数 | 支持 1 | 0.9〜1 | 0.75〜0.9 | 0.5〜0.75 | 0〜0.5 | U の席の割合（最小・Q1・中央値・Q3・最大） | シールの席が二つ以上 |",
                       "|---|---:|---:|---:|---:|---:|---:|---|---:|"]
                for hname in ("正解", "外れ"):
                    x = t1[hname]
                    md.append(f"| {hname} | {x['数']} | " + " | ".join(str(x["支持の割合"][b]) for b, _l, _h in SR_BINS)
                              + f" | {x['U の席の割合（最小・Q1・中央値・Q3・最大）']} | {x['シールの席が二つ以上']} |")
                md += ["", "| シールの席 | 正解（照合で） | 外れ（照合で） | 正解（名前で） | 外れ（名前で） |", "|---|---:|---:|---:|---:|"]
                for k in SEAL_ORDER:
                    v = [t1["正解"]["シールの席（照合で）"].get(k, 0), t1["外れ"]["シールの席（照合で）"].get(k, 0),
                         t1["正解"]["シールの席（名前で）"].get(k, 0), t1["外れ"]["シールの席（名前で）"].get(k, 0)]
                    if sum(v):
                        md.append(f"| {k} | " + " | ".join(map(str, v)) + " |")
                md.append("")
            md += ["### 表 2 答え方（避けた外れ／失った正解。かっこは同じ数を無作為に黙らせた期待値）", "",
                   "| 答え方 | 全課題 | ドア・通常 | ドア・例外 |", "|---|---|---|---|"]
            for pn, ev in pol.items():
                md.append(f"| {pn} | " + " | ".join(f"黙 {ev[g]['黙らせた数']}：外れ {ev[g]['避けた外れ']}（{ev[g]['無作為の期待値：避けた外れ']}）／正解 {ev[g]['失った正解']}（{ev[g]['無作為の期待値：失った正解']}）"
                                                     for g, _f in GROUPS) + " |")
            md += ["", f"答えた数（種 11〜20）：全課題 {pol[next(iter(pol))]['全課題']['答えた数']}（外れ {pol[next(iter(pol))]['全課題']['外れ']}）、"
                   f"ドア・例外 {pol[next(iter(pol))]['ドア・例外']['答えた数']}（外れ {pol[next(iter(pol))]['ドア・例外']['外れ']}）", ""]
            md += ["### 表 3 種ごと（ドアの外れ、うちシールの席が U（照合で））", "", "| 種 | ドアの外れ | うち U | 例外の日のドアの外れ | うち U |", "|---:|---:|---:|---:|---:|"]
            for s, v in per.items():
                md.append(f"| {s} | {v['ドアの外れ']} | {v['外れのうちシールの席が U']} | {v['例外の日のドアの外れ']} | {v['例外の日の外れのうちシールの席が U']} |")
            ex = [v for v in per.values() if v["例外の日のドアの外れ"]]
            fr = [v["例外の日の外れのうちシールの席が U"] / v["例外の日のドアの外れ"] for v in ex]
            md += ["", f"例外の日のドアの外れがあった種：{len(ex)}。その種の「U の割合」：{q4(fr) if fr else '—'}（最小・Q1・中央値・Q3・最大）。", ""]
            r1["表3 U の割合の散らばり"] = q4(fr) if fr else None
    res["q"] = qs
    return res, md


def load_mem(base, arm):
    out = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(base, arm, "seed*.mem.csv"))):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            out[int(r["seed"])].append(r)
    return out


NUM = ["G", "Idef", "S", "seat2", "Hc", "Fc", "total", "defs", "nF", "nH", "nU", "C_end", "births", "assims", "released", "R_B", "R_E",
       "defs_sealF", "defs_sealH", "defs_sealU", "defs_seal無し", "assim_sealF", "assim_sealH", "assim_sealU", "assim_seal無し", "assim_seal新",
       "birth_sealF", "birth_sealH", "birth_sealU", "birth_seal無し"]


def part2(base):
    res = {}
    md = ["# 問い 2：シールを守ると記憶が少なくなる理由（λ＝0.0187）", ""]
    for w in (2, 1):
        arms = {k: f"cw{w}_{k}_lam0187" for k in ("A", "F", "C")}
        mem = {k: load_mem(base, a) for k, a in arms.items()}
        ans = {k: load_ans(base, a) for k, a in arms.items()}
        if not mem["A"] or not mem["F"]:
            continue
        r2 = {}
        # 表 1：種ごとの差
        per = {}
        for k in arms:
            for s, rows in mem[k].items():
                per.setdefault(s, {})[f"{k} 平均の記憶のビット"] = mean(float(r["C_end"]) for r in rows)
                per[s][f"{k} 例外の日のドアの外れ"] = sum(1 for r in ans[k] if r["seed"] == s and r["door"] == 1 and r["shop_cue"] == "e" and r["hit"] == 0)
        diffs = {}
        for k in ("F", "C"):
            db = [per[s][f"{k} 平均の記憶のビット"] - per[s]["A 平均の記憶のビット"] for s in sorted(per)]
            de = [per[s][f"{k} 例外の日のドアの外れ"] - per[s]["A 例外の日のドアの外れ"] for s in sorted(per)]
            diffs[f"{k} − A"] = {"記憶のビット（最小・Q1・中央値・Q3・最大）": q4(db), f"{k} の方が少ない種（記憶のビット）": sum(1 for x in db if x < 0),
                                "例外の日のドアの外れ（最小・Q1・中央値・Q3・最大）": q4(de), f"{k} の方が少ない種（外れ）": sum(1 for x in de if x < 0),
                                "同じ種（外れ）": sum(1 for x in de if x == 0)}
        r2["表1 種ごと"] = {"種ごと": per, "差": diffs}
        # 表 2：174 試行ごと
        win = {}
        for k in arms:
            tab = []
            for b in range(10):
                runs = []
                for s, rows in mem[k].items():
                    x = [r for r in rows if b * 174 <= int(r["trial"]) < (b + 1) * 174]
                    if not x:
                        continue
                    v = {"生きている定義の本数": mean(int(r["defs"]) for r in x),
                         "定義一本あたりの記憶のビット": mean((int(r["S"]) + int(r["seat2"]) + int(r["Hc"]) + int(r["Fc"])) / int(r["defs"]) for r in x if int(r["defs"]) > 0) if any(int(r["defs"]) > 0 for r in x) else 0.0,
                         "記憶のビット": mean(int(r["C_end"]) for r in x),
                         "F の席": mean(int(r["nF"]) for r in x), "H の席": mean(int(r["nH"]) for r in x), "U の席": mean(int(r["nU"]) for r in x),
                         "誕生（区間の和）": sum(int(r["births"]) for r in x), "手放し（区間の和）": sum(int(r["released"]) for r in x),
                         "同化（区間の和）": sum(int(r["assims"]) for r in x),
                         "E 新しく作る（区間の和）": sum(1 for r in x if r["E"] == "新しく作る"), "E 既存にまとめる（区間の和）": sum(1 for r in x if r["E"] == "既存にまとめる"),
                         "R_B（区間の和）": sum(float(r["R_B"]) for r in x), "R_E（区間の和）": sum(float(r["R_E"]) for r in x),
                         "シールの席が F の定義": mean(int(r["defs_sealF"]) for r in x), "シールの席が H の定義": mean(int(r["defs_sealH"]) for r in x),
                         "シールの席が U の定義": mean(int(r["defs_sealU"]) for r in x), "シールの席の無い定義": mean(int(r["defs_seal無し"]) for r in x)}
                    runs.append(v)
                tab.append({kk: round(mean(v[kk] for v in runs), 2) for kk in runs[0]})
            win[k] = tab
        r2["表2 174 試行ごと（20 走行の平均）"] = win
        # 表 3：分解
        comp = {}
        for k in arms:
            allr = [r for rows in mem[k].values() for r in rows]
            m = {c: mean(float(r[c]) for r in allr) for c in ("G", "Idef", "S", "seat2", "Hc", "Fc", "total", "C_end", "defs", "nF", "nH", "nU")}
            m["D"] = m["S"] + m["seat2"] + m["Hc"] + m["Fc"]
            m["b"] = m["D"] / m["defs"] if m["defs"] else 0.0
            # 席の状態ごとの中身の一席あたり
            m["H の中身／H の席"] = m["Hc"] / m["nH"] if m["nH"] else 0.0
            m["F の中身／F の席"] = m["Fc"] / m["nF"] if m["nF"] else 0.0
            comp[k] = {kk: round(v, 2) for kk, v in m.items()}
        dec = {}
        for k in ("F", "C"):
            a, f = comp["A"], comp[k]
            nb, bb = (a["defs"] + f["defs"]) / 2, (a["b"] + f["b"]) / 2
            dec[f"{k} − A"] = {"C_end": round(f["C_end"] - a["C_end"], 2), **{c: round(f[c] - a[c], 2) for c in ("G", "Idef", "S", "seat2", "Hc", "Fc")},
                              "定義の部分 D": round(f["D"] - a["D"], 2), "うち 本数の差 × 平均の一本あたり": round(bb * (f["defs"] - a["defs"]), 2),
                              "うち 平均の本数 × 一本あたりの差": round(nb * (f["b"] - a["b"]), 2),
                              "席の数の差（F・H・U）": [round(f["nF"] - a["nF"], 2), round(f["nH"] - a["nH"], 2), round(f["nU"] - a["nU"], 2)]}
        r2["表3 分解"] = {"平均": comp, "差": dec}
        # 表 4：確かめられる候補の材料（全試行・20 走行の和を走行の数で割る）
        mat = {}
        for k in arms:
            allr = [r for rows in mem[k].values() for r in rows]
            nrun = len(mem[k])
            dt = defaultdict(float)
            for r in allr:
                for c in ("defs_sealF", "defs_sealH", "defs_sealU", "defs_seal無し", "assim_sealF", "assim_sealH", "assim_sealU", "assim_seal無し", "assim_seal新",
                          "birth_sealF", "birth_sealH", "birth_sealU", "birth_seal無し", "births", "released", "assims"):
                    dt[c] += float(r[c])
            mat[k] = {"一走行あたり：誕生": round(dt["births"] / nrun, 1), "手放し": round(dt["released"] / nrun, 1), "同化": round(dt["assims"] / nrun, 1),
                      "E 新しく作る": round(sum(1 for r in allr if r["E"] == "新しく作る") / nrun, 1), "E 既存にまとめる": round(sum(1 for r in allr if r["E"] == "既存にまとめる") / nrun, 1),
                      "誕生した定義のシールの席（F・H・U・無し）": [round(dt[f"birth_seal{x}"] / nrun, 1) for x in ("F", "H", "U", "無し")],
                      "同化された定義のシールの席（F・H・U・無し・新）": [round(dt[f"assim_seal{x}"] / nrun, 1) for x in ("F", "H", "U", "無し", "新")],
                      "定義・試行の数（シールの席 F・H・U・無し）": [round(dt[f"defs_seal{x}"] / nrun, 1) for x in ("F", "H", "U", "無し")],
                      "定義・試行あたりの同化（シールの席 F・H・U・無し）": [round(dt[f"assim_seal{x}"] / dt[f"defs_seal{x}"], 4) if dt[f"defs_seal{x}"] else None for x in ("F", "H", "U", "無し")]}
        r2["表4 候補の材料"] = mat
        res[f"世界 {w}"] = r2
        # 書き出し
        md += [f"## 世界 {w}", "", "### 表 1 種ごとの差（種 1〜20 の同じ種どうし）", "",
               "| 比べ | 記憶のビットの差（最小・Q1・中央値・Q3・最大） | 少ない種 | 例外の日のドアの外れの差（同） | 少ない種 | 同じ種 |", "|---|---|---:|---|---:|---:|"]
        for kk, v in diffs.items():
            k0 = kk[0]
            md.append(f"| {kk} | {v['記憶のビット（最小・Q1・中央値・Q3・最大）']} | {v[f'{k0} の方が少ない種（記憶のビット）']} | {v['例外の日のドアの外れ（最小・Q1・中央値・Q3・最大）']} | {v[f'{k0} の方が少ない種（外れ）']} | {v['同じ種（外れ）']} |")
        md += ["", "| 種 | A ビット | F ビット | C ビット | A 外れ | F 外れ | C 外れ |", "|---:|---:|---:|---:|---:|---:|---:|"]
        for s in sorted(per):
            v = per[s]
            md.append(f"| {s} | {v['A 平均の記憶のビット']:.0f} | {v['F 平均の記憶のビット']:.0f} | {v.get('C 平均の記憶のビット', 0):.0f} | {v['A 例外の日のドアの外れ']} | {v['F 例外の日のドアの外れ']} | {v.get('C 例外の日のドアの外れ', 0)} |")
        md += ["", "### 表 2 174 試行ごと（20 走行の平均。数は区間の中の和の平均）", ""]
        keys = list(win["A"][0])
        md += ["| 量 | 腕 | " + " | ".join(f"{b * 174}〜{b * 174 + 173}" for b in range(10)) + " |", "|---|---|" + "---:|" * 10]
        for kk in keys:
            for k in arms:
                md.append(f"| {kk} | {k} | " + " | ".join(str(win[k][b][kk]) for b in range(10)) + " |")
        md += ["", "### 表 3 記憶のビットの分解（全試行・20 走行の平均）", "",
               "| 腕 | C_end | G | Idef | S | seat2 | Hc | Fc | 定義の本数 | 一本あたり b | F 席 | H 席 | U 席 | H の中身／H 席 | F の中身／F 席 |", "|---|" + "---:|" * 14]
        for k in arms:
            c = comp[k]
            md.append(f"| {k} | {c['C_end']} | {c['G']} | {c['Idef']} | {c['S']} | {c['seat2']} | {c['Hc']} | {c['Fc']} | {c['defs']} | {c['b']} | {c['nF']} | {c['nH']} | {c['nU']} | {c['H の中身／H の席']} | {c['F の中身／F の席']} |")
        md += ["", "| 差 | C_end | G | Idef | S | seat2 | Hc | Fc | 定義の部分 D | うち 本数の差 × 平均の一本あたり | うち 平均の本数 × 一本あたりの差 | 席の数の差（F・H・U） |", "|---|" + "---:|" * 10 + "---|"]
        for kk, v in dec.items():
            md.append(f"| {kk} | {v['C_end']} | {v['G']} | {v['Idef']} | {v['S']} | {v['seat2']} | {v['Hc']} | {v['Fc']} | {v['定義の部分 D']} | {v['うち 本数の差 × 平均の一本あたり']} | {v['うち 平均の本数 × 一本あたりの差']} | {v['席の数の差（F・H・U）']} |")
        md += ["", "### 表 4 候補の材料（一走行あたり）", "", "| 腕 | " + " | ".join(mat["A"]) + " |", "|---|" + "---|" * len(mat["A"])]
        for k in arms:
            md.append(f"| {k} | " + " | ".join(str(v) for v in mat[k].values()) + " |")
        md.append("")
    return res, md


def main():
    base, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    r1, m1 = part1(base)
    r2, m2 = part2(base)
    json.dump({"問い 1": r1, "問い 2": r2}, open(os.path.join(out, "表.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "印.md"), "w", encoding="utf-8").write("\n".join(m1) + "\n")
    open(os.path.join(out, "記憶の量.md"), "w", encoding="utf-8").write("\n".join(m2) + "\n")


if __name__ == "__main__":
    main()
