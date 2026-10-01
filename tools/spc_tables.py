"""段 6 の表（2026-10-01 午前の返事「--strict-pc の続き」の報告、予約の委任書「手がかりの世界」の 6 節）。★ 数えるだけ。判断しない。
使い方  python3.12 tools/spc_tables.py <出力の場所> <走行の根 ~/v310spcprod> <比べる相手の根 ~/v310gapprod> <roletarget の根>
読むもの：各腕の台帳（hit・predicted_edge・abstain_reason・shop の 4 欄）、side の answers.csv・probe.jsonl・shop.jsonl・cfvalue.jsonl、
  roletarget の CSV（tools/roletarget_recompute.py の出力。話した席の対応先）。
表：
  S1 お店の世界：全課題の正解・誤答・棄権（理由別、no_gap_candidate を分ける）
  S2 お店の世界：ドアの課題（伏せた関係がドア）を、店 × シールで、正解・誤答・棄権と、答えた席の対応先 (i)(ii)(iii)
  S3 お店の世界：対になった試験（時点ごと、甲・乙それぞれ）：シールを替えると答えが変わった割合・両方正しい割合（棄権は別に数える）
  S4 お店の世界：シールと link の席の状態（F・H・U）の時間変化（時点ごとの席の数）と、状態が変わった試行の分布
  S6 お店の世界：共有部分の試験の正解・誤答・棄権
  C1 今の世界：--strict-pc あり（~/v310spcprod の spc_*）となし（~/v310gapprod の v310gap_*、どちらも --answer-gap）の正解・誤答・棄権、話した席の出どころ
  V1 --cf-value：席の種類 × 腕ごとの利益の分布（中央値・四分位・正・0・負の数）、「今の B の点数（V）が 0 なのに利益が正」の席の数と割合、利益が負の席の数
  V2 お店の世界：シールの席の利益の時間変化（100 試行ごとの平均と正の割合。世界 1 と世界 2 を並べる）"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

TS = list(range(100, 1701, 100))


def ledger(root):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "ledgers/cells/*/seed*.jsonl.gz"))):
        s = int(os.path.basename(p)[4:7])
        if not 1 <= s <= 20 or not os.path.exists(p[:-len(".jsonl.gz")] + ".done"):
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            next(f)
            for line in f:
                r = json.loads(line)
                if r.get("record_type", "trial") != "trial":
                    continue
                out[(s, r["prediction_order"])] = {"spoke": r.get("predicted_edge") is not None, "hit": bool(r.get("hit")),
                                                   "why": r.get("abstain_reason"), "type": r.get("shop_type"), "cue": r.get("shop_cue"),
                                                   "door": r.get("held_out_is_door")}
    return out


def side_rows(root, kind):
    for p in sorted(glob.glob(os.path.join(root, f"side/*/seed*.{kind}"))):
        s = int(os.path.basename(p)[4:7])
        if not 1 <= s <= 20:
            continue
        if kind.endswith(".csv"):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                yield s, r
        else:
            for line in open(p, encoding="utf-8"):
                yield s, json.loads(line)


def outcome(rows):
    c = Counter()
    for v in rows:
        c["正解" if v["spoke"] and v["hit"] else "誤答" if v["spoke"] else "棄権"] += 1
        if not v["spoke"]:
            c[f"棄権：{v['why']}"] += 1
    return c


def q(xs):
    xs = sorted(xs)
    if not xs:
        return "—"
    f = lambda p: xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]  # noqa: E731
    return f"{f(0.5):.3g}〔{f(0.25):.3g}–{f(0.75):.3g}〕"


def table(title, head, rows):
    L = [f"### {title}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    L += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return L + [""]


def main():
    out, root, gaproot, rtroot = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)
    arms = sorted(os.path.basename(p) for p in glob.glob(os.path.join(root, "*")) if os.path.isdir(p) and os.path.exists(os.path.join(p, "flag.json")))
    S, C, V = ["# お店の世界の表（S1〜S6）", ""], ["# 今の世界：--strict-pc の有無（C1）", ""], ["# --cf-value（V1・V2）", ""]
    summ = {}
    reasons_all = set()
    led = {a: ledger(os.path.join(root, a)) for a in arms}
    for a in arms:
        reasons_all |= {v["why"] for v in led[a].values() if not v["spoke"]}
    reasons = sorted(x for x in reasons_all if x)
    v2 = {}
    for a in arms:
        rt = {(s, int(r["trial"])): r for s, r in side_rows(os.path.join(rtroot, a), "roletarget.csv")} if os.path.isdir(os.path.join(rtroot, a)) else {}
        # roletarget の CSV はファイル名が <セル>_seed<種>.roletarget.csv
        if not rt:
            for p in glob.glob(os.path.join(rtroot, a, "*.roletarget.csv")):
                for r in csv.DictReader(open(p, encoding="utf-8")):
                    rt[(int(r["seed"]), int(r["trial"]))] = r
        L = led[a]
        n = len(L)
        c = outcome(L.values())
        summ[a] = {"全課題": n, **dict(c)}
        if a.startswith("shop_"):
            S += [f"## {a}", ""]
            S += table("S1 全課題", ["", "数", "割合"], [[k, f"{c[k]:,}", f"{c[k] / n:.1%}"] for k in ["正解", "誤答", "棄権"] + [f"棄権：{r}" for r in reasons] if c[k] or k in ("正解", "誤答", "棄権")])
            dr = []
            for typ in ("甲", "乙"):
                for cue in ("n", "e"):
                    ks = [k for k, v in L.items() if v["door"] and v["type"] == typ and v["cue"] == cue]
                    cc = outcome([L[k] for k in ks])
                    cls = Counter(rt[k]["cls"].split("：")[0] for k in ks if k in rt and rt[k].get("answered") == "1")
                    dr.append([f"{typ}・{cue}", len(ks), cc["正解"], cc["誤答"], cc["棄権"], cls.get("(i) 伏せた関係", 0), cls.get("(ii) 見えている関係", 0), cls.get("(iii) 対応先なし", 0)])
            S += table("S2 ドアの課題（店・シール）", ["店・シール", "課題", "正解", "誤答", "棄権", "(i)", "(ii)", "(iii)"], dr)
            pr = defaultdict(dict)
            shared = Counter()
            for s, r in side_rows(os.path.join(root, a), "probe.jsonl"):
                kind = r.get("shop_probe")
                if kind == "対":
                    pr[(s, r["t"], r["shop_type"])][r["shop_cue"]] = r
                elif kind == "共有":
                    shared[("答えた" if r.get("answer") else "棄権", "正しい" if r.get("answer_is_truth") and r.get("oracle") else "—" if not r.get("answer") else "誤り")] += 1
            rows3 = []
            for t in TS + [1740]:
                for typ in ("甲", "乙"):
                    xs = [v for (s, tt, ty), v in pr.items() if tt == t and ty == typ and "n" in v and "e" in v]
                    both = [v for v in xs if v["n"].get("answer") and v["e"].get("answer")]
                    chg = sum(1 for v in both if v["n"]["answer"] != v["e"]["answer"])
                    ok2 = sum(1 for v in both if v["n"].get("answer_is_truth") and v["e"].get("answer_is_truth") and v["n"].get("oracle") and v["e"].get("oracle"))
                    ab = sum(1 for v in xs if not (v["n"].get("answer") and v["e"].get("answer")))
                    rows3.append([t, typ, len(xs), len(both), f"{chg / len(both):.0%}" if both else "—", f"{ok2 / len(both):.0%}" if both else "—", ab])
            S += table("S3 対になった試験（両方答えた対の中での割合。棄権を含む対は別に数える）",
                       ["時点", "店", "対", "両方答えた", "シールで答えが変わった", "両方正しい", "どちらかが棄権"], rows3)
            st = defaultdict(dict)
            trans = Counter()
            ttimes = defaultdict(list)
            for s, r in side_rows(os.path.join(root, a), "shop.jsonl"):
                if r.get("kind") != "shop_seat":
                    continue
                key = (s, r["R"], r["reg"], r["slot"])
                st[key][r["trial"]] = (r["which"], r["to"])
                trans[(r["which"], r["from"], r["to"])] += 1
                if r["from"] not in ("生まれた",) and r["to"] in ("H", "U"):
                    ttimes[(r["which"], f"{r['from']}→{r['to']}")].append(r["trial"])
            rows4 = []
            for t in TS + [1739]:
                cnt = Counter()
                for key, ev in st.items():
                    last = None
                    for tt in sorted(ev):
                        if tt > t:
                            break
                        last = ev[tt]
                    if last and last[1] in ("F", "H", "U"):
                        cnt[(last[0], last[1])] += 1
                rows4.append([t] + [cnt[(w, x)] for w in ("sig", "link") for x in ("F", "H", "U")])
            S += table("S4 シールと link の席の数（その時点の終わり、20 走行の和）", ["時点", "シール F", "シール H", "シール U", "link F", "link H", "link U"], rows4)
            S += table("S4 状態の移り（回数）", ["席", "前", "後", "回数"], [[k[0], k[1], k[2], v] for k, v in sorted(trans.items())])
            S += table("S4 状態が変わった試行（中央値〔四分位〕）", ["席", "移り", "回数", "試行"], [[k[0], k[1], len(v), q(v)] for k, v in sorted(ttimes.items())])
            S += table("S6 共有部分の試験（全時点の和）", ["答え", "正しさ", "数"], [[k[0], k[1], v] for k, v in sorted(shared.items())])
        else:
            g = os.path.join(gaproot, a.replace("spc_", "v310gap_"))
            Lg = ledger(g) if os.path.isdir(g) else {}
            cg = outcome(Lg.values())
            src = Counter(r["source"] for _s, r in side_rows(os.path.join(root, a), "answers.csv"))
            srcg = Counter(r["source"] for _s, r in side_rows(g, "answers.csv")) if Lg else Counter()
            C += [f"## {a}（比べる相手：{os.path.basename(g)}）", ""]
            C += table("C1 正解・誤答・棄権", ["", "--strict-pc あり", "なし（--answer-gap だけ）"],
                       [[k, f"{c[k]:,}", f"{cg[k]:,}"] for k in ["正解", "誤答", "棄権"] + [f"棄権：{r}" for r in reasons] if c[k] or cg[k] or k in ("正解", "誤答", "棄権")])
            C += table("C1 話した席の出どころ", ["出どころ", "あり", "なし"], [[k, src[k], srcg[k]] for k in sorted(set(src) | set(srcg))])
        # V1
        rows = [r for _s, r in side_rows(os.path.join(root, a), "cfvalue.jsonl")]
        byk = defaultdict(list)
        for r in rows:
            for k in r["kinds"]:
                byk[k].append(r)
        vr = []
        for k in ("答えた席", "答えた席の親", "根", "T 階", "シール", "link"):
            xs = byk.get(k, [])
            if not xs:
                continue
            b = [x["benefit"] for x in xs]
            v0 = [x for x in xs if x.get("V") is not None and abs(x["V"]) < 1e-12]
            v0p = sum(1 for x in v0 if x["benefit"] > 0)
            vr.append([k, len(xs), q(b), sum(1 for v in b if v > 0), sum(1 for v in b if v == 0), sum(1 for v in b if v < 0),
                       f"{v0p}／{len(v0)}（{v0p / len(v0):.0%}）" if v0 else "—", sum(1 for x in xs if x.get("V") is None)])
        V += [f"## {a}", ""] + table("V1 席の種類ごとの利益（開示のあった試行、選ばれた定義の席）",
                                      ["席の種類", "行", "利益 中央値〔四分位〕", "正", "0", "負", "V＝0 のうち利益が正", "候補にならない席（V なし）"], vr)
        if a.startswith("shop_"):
            sig = byk.get("シール", [])
            v2[a] = [[t, len([x for x in sig if t - 100 < x["trial"] <= t]),
                      (sum(x["benefit"] for x in sig if t - 100 < x["trial"] <= t) / max(1, len([x for x in sig if t - 100 < x["trial"] <= t]))),
                      sum(1 for x in sig if t - 100 < x["trial"] <= t and x["benefit"] > 0)] for t in TS + [1800]]
    # V2：世界 1 と世界 2 を並べる
    V += ["## V2 シールの席の利益の時間変化（100 試行ごと：行・平均・正の数）", ""]
    pairs = sorted({a.replace("shop_w1_", "").replace("shop_w2_", "") for a in v2})
    for p in pairs:
        a1, a2 = f"shop_w1_{p}", f"shop_w2_{p}"
        rows = []
        for i, t in enumerate(TS + [1800]):
            x1 = v2.get(a1, [[t, 0, 0, 0]] * 18)[i]
            x2 = v2.get(a2, [[t, 0, 0, 0]] * 18)[i]
            rows.append([f"〜{min(t, 1739)}", x1[1], f"{x1[2]:.2f}", x1[3], x2[1], f"{x2[2]:.2f}", x2[3]])
        V += table(p, ["試行", "世界 1 行", "世界 1 平均", "世界 1 正", "世界 2 行", "世界 2 平均", "世界 2 正"], rows)
    for fn, L in (("お店の世界.md", S), ("strict-pcの有無.md", C), ("cf-value.md", V)):
        open(os.path.join(out, fn), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(summ, open(os.path.join(out, "要約.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", out)


if __name__ == "__main__":
    main()
