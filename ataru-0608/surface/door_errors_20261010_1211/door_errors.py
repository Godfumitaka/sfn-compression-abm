"""例外の日のドアの課題の選び間違いを一件ずつ並べる（受け箱の指示 77、探りの数え、主張には使わない）。読むだけ。

定義は ~/surface/wave1.py と同じ（本の選び方も同じ：~/surface/wave1_view/selection.tsv と ~/surface/wave1_view/<行>/q<行>_w<世界>/seedNNN）：
  - 課題＝台帳（ledgers/cells/*/seedNNN.jsonl.gz）の record_type が trial の行。試行の番号は prediction_order。
  - 例外の日＝台帳の shop_cue が "e"（通常の日は "n"）。ドアの課題＝台帳の held_out_is_door が真。
  - 誤答＝hit が偽で predicted_edge が null でない。capable＝注意の記録の同じ試行の candidates に gate_passed かつ hit の候補が一つ以上ある。
  - 選び間違い＝誤答で capable。
  - 台帳と注意の記録の試行の番号の集まりが合わない本は、wave1.py と同じく数えない（理由を書く）。
一件ごとの欄（選んだ定義＝注意の記録の selected_R、正答の候補＝gate_passed かつ hit の候補）：
  - 印の席（seal）：注意の記録の候補の seal（状態 F/H/U、F なら名前、H なら履歴の名前と数）。
    side/*/seedNNN.shop.jsonl（shop_seat、which=sig）の移り変わりから、その試行より前（trial < 試行）の最後の状態も並べる（突き合わせ用）。
  - q＝q_numerator / q_denominator、注意の費用＝Σ a_before[k]·m[k]（k の並びは名前順、attnsme.py と同じ）、z＝ln q − 注意の費用（q>0 のときだけ。attnsme.py・attnratio.log_scores と同じ式）。
使い方：nice -n 15 python3 door_errors.py --out DIR [--workers 3]
"""
import argparse
import csv
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

V = Path.home() / "surface/wave1_view"
PER_RUN = Path.home() / "v33prod/results/ataru-0608/surface/wave1_20261010_0600/per_run.csv"
WORLD = 2
GROUPS = ("1", "7", "5")
EXPECTED = {"1": (218, 612), "7": (21, 612), "5": (169, 431)}
CELLS = (("ドア", "例外"), ("ドア", "通常"), ("ドア以外", "例外"), ("ドア以外", "通常"))
DAY = {"e": "例外", "n": "通常"}


def rows_gz(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def one(d, pat):
    p = sorted(Path(d).glob(pat))
    return p[0] if len(p) == 1 else None


def fmtf(x):
    return "NA" if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else repr(float(x))


def seal_fields(c):
    """候補の seal（印の席）の欄。席が複数なら | で区切る。席が無ければ「なし」。"""
    seal = c.get("seal")
    if seal is None:
        return dict(state="NA", name="NA", history="NA", history_total="NA", slots="NA")
    if not seal:
        return dict(state="なし", name="", history="", history_total="", slots="")
    st, nm, hi, ht, sl = [], [], [], [], []
    for s in seal:
        st.append(str(s.get("state")))
        nm.append(s.get("name") or "")
        h = s.get("history") or {}
        if s.get("state") == "H":
            hi.append(",".join(f"{k}:{v}" for k, v in sorted(h.items())) if h else "{}")
            ht.append(str(sum(h.values())))
        else:
            hi.append("")
            ht.append("")
        sl.append(str(s.get("slot")))
    return dict(state="|".join(st), name="|".join(nm), history="|".join(hi), history_total="|".join(ht), slots="|".join(sl))


def side_state(shop, R, slots, t):
    """shop.jsonl の which=sig の移り変わりで、試行 t より前の最後の状態。"""
    if shop is None:
        return "NA"
    out = []
    for s in slots:
        ev = [e for e in shop.get((R, s), []) if e[0] < t]
        out.append(ev[-1][1] if ev else "記録なし")
    return "|".join(out)


def score(c, a):
    q = Fraction(int(c["q_numerator"]), int(c["q_denominator"]))
    pen = 0.
    for k, m in sorted((c.get("m") or {}).items()):
        pen += a.get(k, 0.) * m
    z = math.log(float(q)) - pen if q > 0 else None
    return q, pen, z


def one_run(job):
    row, world, seed, run_name, version = job
    rd = V / row / f"q{row}_w{world}" / f"seed{seed:03d}"
    res = dict(row=row, world=world, seed=seed, run=run_name, version=version, status="", cases=[], cells={}, trials=0,
               side_checked=0, side_agree=0, side_disagree=[])
    led = one(rd, f"ledgers/cells/*/seed{seed:03d}.jsonl.gz")
    att = one(rd, f"attention/*/seed{seed:03d}.jsonl.gz")
    shp = one(rd, f"side/*/seed{seed:03d}.shop.jsonl")
    if led is None:
        res["status"] = "NA：台帳が無い"
        return res
    if att is None:
        res["status"] = "NA：注意の記録が無い"
        return res
    # 台帳：試行ごとの結果・日・ドア
    L = {}
    seen = []
    horizon = None
    for r in rows_gz(led):
        if r.get("record_type") == "run_header":
            horizon = int(r["trial_count"])
        if r.get("record_type", "trial") != "trial":
            continue
        t = r["prediction_order"]
        seen.append(t)
        outcome = "correct" if r["hit"] else "silent" if r["predicted_edge"] is None else "wrong"
        pe = r["predicted_edge"]
        L[t] = dict(outcome=outcome, cue=r.get("shop_cue"), door=bool(r.get("held_out_is_door")),
                    R_used=r.get("R_used"), pred=(pe or {}).get("predicate") if isinstance(pe, dict) else None,
                    truth=(r.get("held_out_content") or {}).get("predicate") if isinstance(r.get("held_out_content"), dict) else None)
    targets = {t for t, x in L.items() if x["outcome"] == "wrong" and x["door"] and x["cue"] == "e"}
    cap = {}
    keep = {}
    for r in rows_gz(att):
        t = r.get("trial")
        if t is None or t in cap:
            res["status"] = f"NA：注意の記録の試行の番号が無いか重なる（{t}）"
            return res
        cands = r.get("candidates") or []
        cap[t] = any(c.get("gate_passed") and c.get("hit") for c in cands)
        if t in targets and cap[t]:
            a = r.get("a_before") or {}
            sc = []
            for c in cands:
                q, pen, z = score(c, a)
                sc.append(dict(R=c.get("R"), gate_passed=c.get("gate_passed"), hit=c.get("hit"), q=q, pen=pen, z=z,
                               seal=seal_fields(c), seal_raw=c.get("seal"), answer=c.get("answer")))
            keep[t] = dict(selected=r.get("selected_R"), actual_R=(r.get("actual") or {}).get("R_used"),
                           door_task=r.get("door_task"), shop_cue=r.get("shop_cue"), hit=r.get("hit"), cands=sc,
                           all_pen_zero=all(x["pen"] == 0. for x in sc), a_nonzero=sum(1 for v in a.values() if v != 0))
    if len(seen) != len(cap) or sorted(seen) != sorted(cap):
        res["status"] = f"NA：突き合わせの誤り（台帳 {len(seen)} 試行、注意の記録 {len(cap)} 試行）"
        return res
    shop = None
    if shp is not None:
        shop = defaultdict(list)
        with open(shp, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("kind") == "shop_seat" and e.get("which") == "sig":
                    shop[(e["R"], e["slot"])].append((e["trial"], e["to"]))
    # 課題の種類ごとの数（5a の分け）
    cells = Counter()
    for t, x in L.items():
        door = "ドア" if x["door"] else "ドア以外"
        day = DAY.get(x["cue"], "なし")
        se = x["outcome"] == "wrong" and cap[t]
        for key in ((door, day), ("全課題", "全日")):
            cells[key + ("tasks",)] += 1
            cells[key + ("selection_error",)] += int(se)
    res["cells"] = {"/".join(k): v for k, v in cells.items()}
    res["trials"] = len(seen)
    for t in sorted(targets):
        if not cap[t]:
            continue
        k = keep[t]
        x = L[t]
        chosen = next((c for c in k["cands"] if c["R"] == k["selected"]), None)
        correct = [c for c in k["cands"] if c["gate_passed"] and c["hit"]]
        case = dict(row=row, world=world, seed=seed, run=run_name, version=version, trial=t,
                    trial_count=horizon if horizon is not None else "NA",
                    half=("NA" if horizon is None else "前半" if t < horizon / 2 else "後半"),
                    truth_predicate=x["truth"] or "NA", predicted_predicate=x["pred"] or "NA",
                    ledger_R_used=x["R_used"] if x["R_used"] is not None else "NA",
                    selected_R=k["selected"] if k["selected"] is not None else "NA",
                    attention_door_task=k["door_task"], attention_shop_cue=k["shop_cue"],
                    n_candidates=len(k["cands"]), n_correct=len(correct),
                    all_penalties_zero=k["all_pen_zero"], a_before_nonzero_keys=k["a_nonzero"])
        if chosen is None:
            why = "NA：selected_R が null" if k["selected"] is None else "NA：selected_R が候補に無い"
            for f in ("gate_passed", "hit", "seal_slots", "seal_state", "seal_name", "seal_history", "seal_history_total",
                      "seal_state_side", "q", "q_exact", "penalty", "z"):
                case[f"chosen_{f}"] = why
        else:
            s = chosen["seal"]
            case.update(chosen_gate_passed=chosen["gate_passed"], chosen_hit=chosen["hit"],
                        chosen_seal_slots=s["slots"], chosen_seal_state=s["state"], chosen_seal_name=s["name"],
                        chosen_seal_history=s["history"], chosen_seal_history_total=s["history_total"],
                        chosen_seal_state_side=side_state(shop, chosen["R"], [z["slot"] for z in (chosen["seal_raw"] or [])], t),
                        chosen_q=fmtf(chosen["q"]), chosen_q_exact=f"{chosen['q'].numerator}/{chosen['q'].denominator}",
                        chosen_penalty=fmtf(chosen["pen"]),
                        chosen_z=fmtf(chosen["z"]) if chosen["z"] is not None else "NA：q が 0（ln q が無い）")
        j = lambda f: ";".join(f(c) for c in correct)
        case.update(correct_R=j(lambda c: c["R"]),
                    correct_seal_slots=j(lambda c: c["seal"]["slots"]), correct_seal_state=j(lambda c: c["seal"]["state"]),
                    correct_seal_name=j(lambda c: c["seal"]["name"]), correct_seal_history=j(lambda c: c["seal"]["history"]),
                    correct_seal_history_total=j(lambda c: c["seal"]["history_total"]),
                    correct_seal_state_side=j(lambda c: side_state(shop, c["R"], [z["slot"] for z in (c["seal_raw"] or [])], t)),
                    correct_q=j(lambda c: fmtf(c["q"])), correct_penalty=j(lambda c: fmtf(c["pen"])),
                    correct_z=j(lambda c: fmtf(c["z"]) if c["z"] is not None else "NA：q が 0"))
        zs = [c["z"] for c in correct if c["z"] is not None]
        qs = [c["q"] for c in correct]
        case["correct_best_z"] = fmtf(max(zs)) if zs else "NA：正答の候補の q がどれも 0"
        case["correct_best_q"] = fmtf(max(qs)) if qs else "NA"
        if chosen is not None and chosen["z"] is not None and zs:
            case["z_chosen_minus_best_correct"] = fmtf(chosen["z"] - max(zs))
        else:
            case["z_chosen_minus_best_correct"] = "NA：選んだ定義か正答の候補の z が無い"
        case["q_chosen_minus_best_correct"] = fmtf(float(chosen["q"] - max(qs))) if chosen is not None and qs else "NA"
        # 突き合わせ：印の席の状態（注意の記録 対 side の shop.jsonl）
        for c in ([chosen] if chosen else []) + correct:
            for zz in (c["seal_raw"] or []):
                if shop is None:
                    continue
                ss = side_state(shop, c["R"], [zz["slot"]], t)
                res["side_checked"] += 1
                if ss == zz["state"]:
                    res["side_agree"] += 1
                else:
                    res["side_disagree"].append(f"{row} s{seed} t{t} {c['R']} 席{zz['slot']}：注意の記録 {zz['state']}、side {ss}")
        res["cases"].append(case)
    res["status"] = "ok"
    return res


def mean(v):
    v = [a for a in v if a is not None and not math.isnan(a)]
    return sum(v) / len(v) if v else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", help="試しに一本だけ（例 1a,1）")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sel = list(csv.DictReader(open(V / "selection.tsv"), delimiter="\t"))
    pr = {(r["row"], int(r["world"]), int(r["seed"])): r for r in csv.DictReader(open(PER_RUN, encoding="utf-8"))}
    jobs, absent, sel_vs_perrun = [], [], []
    for s in sel:
        if s["row"][0] not in GROUPS or int(s["world"]) != WORLD:
            continue
        key = (s["row"], int(s["world"]), int(s["seed"]))
        p = pr.get(key)
        if p is None or p["run"] != s["run"]:
            sel_vs_perrun.append(f"{key}：selection.tsv {s['run']!r}、per_run.csv {None if p is None else p['run']!r}")
        if not s["run"]:
            absent.append(f"{s['row']} 種 {s['seed']}：未完（持ち帰っていない）")
            continue
        jobs.append((s["row"], int(s["world"]), int(s["seed"]), s["run"], s["version"]))
    if a.only:
        r, sd = a.only.split(",")
        jobs = [j for j in jobs if j[0] == r and j[2] == int(sd)]
    with Pool(a.workers) as pool:
        results = pool.map(one_run, jobs, chunksize=1)
    results.sort(key=lambda r: (r["row"][0] != "1", r["row"][0] != "7", r["row"], r["seed"]))
    # 一件ずつの表
    cases = [c for r in results for c in r["cases"]]
    fields = list(cases[0].keys()) if cases else []
    with open(out / "door_errors_cases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cases)
    # まとめの表（行の組ごとの数）
    summ = []
    tot = {}
    for g in GROUPS:
        rs = [r for r in results if r["row"][0] == g and r["status"] == "ok"]
        cs = [c for c in cases if c["row"][0] == g]
        n_tasks = sum(r["cells"].get("ドア/例外/tasks", 0) for r in rs)
        n_se = sum(r["cells"].get("ドア/例外/selection_error", 0) for r in rs)
        tot[g] = (n_se, n_tasks, len(rs))
        lab = f"{g}a/{g}b"
        add = lambda item, cat, n, note="": summ.append(dict(row=lab, item=item, category=cat, count=n, note=note))
        add("読めた本の数", "", len(rs), "種 " + ",".join(str(r["seed"]) for r in rs))
        add("例外の日のドアの課題の数", "", n_tasks, f"wave1_20261010_0600 の数 {EXPECTED[g][1]}")
        add("選び間違いの数", "", n_se, f"wave1_20261010_0600 の数 {EXPECTED[g][0]}")
        add("一件の表の行の数", "", len(cs))
        for k, v in sorted(Counter(c["half"] for c in cs).items()):
            add("試行の前半・後半", k, v, "前半＝試行の番号 < trial_count/2")
        for k, v in sorted(Counter(c["chosen_seal_state"] for c in cs).items()):
            add("選んだ定義の印の席の状態", k, v)
        for k, v in sorted(Counter((c["chosen_seal_state"], c["chosen_seal_name"]) for c in cs).items()):
            add("選んだ定義の印の席の状態と名前", f"{k[0]} {k[1]}".strip(), v)
        cor = Counter()
        for c in cs:
            for st, nm in zip(c["correct_seal_state"].split(";"), c["correct_seal_name"].split(";")):
                cor[f"{st} {nm}".strip()] += 1
        for k, v in sorted(cor.items()):
            add("正答の候補の印の席の状態と名前（候補ごと）", k, v)
        for k, v in sorted(Counter(c["n_correct"] for c in cs).items()):
            add("正答の候補の数（一件あたり）", str(k), v)
        def sign(x):
            try:
                y = float(x)
            except ValueError:
                return "NA"
            return "選んだ定義のほうが大きい" if y > 0 else "同じ" if y == 0 else "正答の候補のほうが大きい"
        for k, v in sorted(Counter(sign(c["z_chosen_minus_best_correct"]) for c in cs).items()):
            add("z：選んだ定義 対 正答の候補の最大", k, v)
        for k, v in sorted(Counter(sign(c["q_chosen_minus_best_correct"]) for c in cs).items()):
            add("q：選んだ定義 対 正答の候補の最大", k, v)
        for k, v in sorted(Counter(str(c["all_penalties_zero"]) for c in cs).items()):
            add("全候補の注意の費用が 0（選びが q だけ）", k, v)
        for k, v in sorted(Counter(str(c["chosen_gate_passed"]) for c in cs).items()):
            add("選んだ定義の gate_passed", k, v)
        for k, v in sorted(Counter(str(c["selected_R"] == c["ledger_R_used"]) for c in cs).items()):
            add("selected_R と台帳の R_used が同じ", k, v)
        add("印の席の状態の突き合わせ（注意の記録 対 side shop.jsonl）", "照らした席", sum(r["side_checked"] for r in rs))
        add("印の席の状態の突き合わせ（注意の記録 対 side shop.jsonl）", "同じ", sum(r["side_agree"] for r in rs))
    with open(out / "door_errors_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row", "item", "category", "count", "note"])
        w.writeheader()
        w.writerows(summ)
    # 5a の分け（課題の種類ごと）。5 の種がある種だけ、同じ種の 1 を並べる。
    by = {(r["row"][0], r["seed"]): r for r in results if r["status"] == "ok"}
    seeds5 = sorted(s for (g, s) in by if g == "5" and ("1", s) in by)
    bf = ["seed", "cell", "5_tasks", "5_selection_error", "5_rate_in_cell", "5_contribution_to_overall",
          "1_tasks", "1_selection_error", "1_rate_in_cell", "1_contribution_to_overall", "contribution_diff_5_minus_1"]
    brows = []
    acc = defaultdict(lambda: defaultdict(list))
    for s in seeds5:
        for cell in CELLS + (("全課題", "全日"),):
            rr = dict(seed=s, cell="×".join(cell))
            for g in ("5", "1"):
                c = by[(g, s)]["cells"]
                n = c.get("/".join(cell) + "/tasks", 0)
                e = c.get("/".join(cell) + "/selection_error", 0)
                N = c.get("全課題/全日/tasks", 0)
                ri = e / n if n else float("nan")
                co = e / N if N else float("nan")
                rr.update({f"{g}_tasks": n, f"{g}_selection_error": e, f"{g}_rate_in_cell": fmtf(ri),
                           f"{g}_contribution_to_overall": fmtf(co)})
                acc[rr["cell"]][f"{g}_ri"].append(ri)
                acc[rr["cell"]][f"{g}_co"].append(co)
                acc[rr["cell"]][f"{g}_n"].append(n)
                acc[rr["cell"]][f"{g}_e"].append(e)
            rr["contribution_diff_5_minus_1"] = fmtf(float(rr["5_contribution_to_overall"]) - float(rr["1_contribution_to_overall"]))
            brows.append(rr)
    for cell in CELLS + (("全課題", "全日"),):
        k = "×".join(cell)
        d = acc[k]
        brows.append({"seed": f"平均（{len(seeds5)} 種）", "cell": k,
                      "5_tasks": sum(d["5_n"]), "5_selection_error": sum(d["5_e"]), "5_rate_in_cell": fmtf(mean(d["5_ri"])),
                      "5_contribution_to_overall": fmtf(mean(d["5_co"])),
                      "1_tasks": sum(d["1_n"]), "1_selection_error": sum(d["1_e"]), "1_rate_in_cell": fmtf(mean(d["1_ri"])),
                      "1_contribution_to_overall": fmtf(mean(d["1_co"])),
                      "contribution_diff_5_minus_1": fmtf(mean(d["5_co"]) - mean(d["1_co"]))})
    with open(out / "5a_breakdown.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=bf)
        w.writeheader()
        w.writerows(brows)
    na_runs = [f"{r['row']} 種 {r['seed']}（{r['run']}）：{r['status']}" for r in results if r["status"] != "ok"]
    na_fields = Counter()
    for c in cases:
        for k, v in c.items():
            if isinstance(v, str) and v.startswith("NA"):
                na_fields[f"{k}：{v}"] += 1
    meta = dict(
        made_at=datetime.now().isoformat(timespec="seconds"), rule="受け箱の指示 77（探りの数え、主張には使わない）",
        script="door_errors.py", world=WORLD, rows="1a/1b・7a/7b・5a/5b（wave1.py と同じく a と b を合わせ、種 1〜20）",
        selection="~/surface/wave1_view/selection.tsv（wave1.py と同じ本）。per_run.csv（wave1_20261010_0600）の run と照らした",
        selection_vs_per_run_mismatch=sel_vs_perrun or "なし",
        runs_absent=absent, runs_na=na_runs or "なし",
        totals={f"{g}a/{g}b": dict(selection_error=tot[g][0], door_exception_tasks=tot[g][1], runs=tot[g][2],
                                   expected_selection_error=EXPECTED[g][0], expected_tasks=EXPECTED[g][1],
                                   same=(tot[g][0], tot[g][1]) == EXPECTED[g]) for g in GROUPS},
        definitions={
            "課題": "台帳の record_type が trial の行（試行の番号 prediction_order）",
            "例外の日": "台帳の shop_cue が e（通常の日は n）",
            "ドアの課題": "台帳の held_out_is_door が真",
            "誤答": "台帳の hit が偽で predicted_edge が null でない",
            "capable": "注意の記録の同じ試行の candidates に gate_passed かつ hit の候補が一つ以上ある",
            "選び間違い": "誤答で capable（wave1.py と同じ）",
            "選んだ定義": "注意の記録の selected_R の候補",
            "正答の候補": "注意の記録の candidates のうち gate_passed かつ hit",
            "前半・後半": "試行の番号 < trial_count/2 を前半（trial_count は台帳の run_header）",
            "q": "候補の q_numerator / q_denominator（smeshared.select_definition の n3＝2·SES/(S_dd+S_xx)、選びの第一の鍵）。1・7 は match_cstar が真（C* の照合）、5 は flag.json で match_cstar・match_cstar_e が偽",
            "penalty（注意の費用）": "Σ_k a_before[k]·m[k]、k は候補の m の名前順（tools/attnsme.py の penalties と同じ足し順）",
            "z": "ln(q) − penalty（tools/attnsme.py の choices、tools/attnratio.py の log_scores と同じ式。q=0 の候補は z が無い）。ドアの課題で全候補の penalty が 0 のときは、選びは z でなく q の大小（all_penalties_zero 欄）",
            "印の席（seal）": "注意の記録の候補の seal（attnsme.py が shopworld.IDS で sig の席を選んだもの）。状態 F/H/U、F は name、H は history（名前:数）。H で履歴の表が空のものは {}（v39.seat_state：空の表も H）",
            "印の席の状態（side）": "side/*/seedNNN.shop.jsonl の kind=shop_seat・which=sig の移り変わりのうち、trial < その試行の最後の to。無ければ「記録なし」",
        },
        fields={
            "row,world,seed,run,version": "~/surface/wave1_view/selection.tsv",
            "trial": "台帳 ledgers/cells/*/seedNNN.jsonl.gz の prediction_order（注意の記録の trial と同じ番号）",
            "trial_count": "台帳の run_header の trial_count",
            "half": "trial と trial_count から",
            "truth_predicate": "台帳の held_out_content.predicate",
            "predicted_predicate": "台帳の predicted_edge.predicate",
            "ledger_R_used": "台帳の R_used",
            "selected_R": "注意の記録 attention/*/seedNNN.jsonl.gz の selected_R",
            "attention_door_task,attention_shop_cue": "注意の記録の door_task・shop_cue（台帳との突き合わせ用）",
            "n_candidates": "注意の記録の candidates の数",
            "n_correct": "candidates のうち gate_passed かつ hit の数",
            "all_penalties_zero": "注意の記録の a_before と各候補の m から計算",
            "a_before_nonzero_keys": "注意の記録の a_before の 0 でない鍵の数",
            "chosen_gate_passed,chosen_hit": "注意の記録の選んだ候補の gate_passed・hit",
            "*_seal_slots,*_seal_state,*_seal_name,*_seal_history,*_seal_history_total": "注意の記録の候補の seal（slot・state・name・history）",
            "*_seal_state_side": "side/*/seedNNN.shop.jsonl（shop_seat、which=sig）の R・slot・trial・to",
            "*_q,chosen_q_exact": "注意の記録の候補の q_numerator・q_denominator",
            "*_penalty": "注意の記録の a_before と候補の m",
            "*_z": "q と penalty から",
            "correct_best_z,correct_best_q": "正答の候補の z・q の最大",
            "z_chosen_minus_best_correct,q_chosen_minus_best_correct": "選んだ定義の z（q）− 正答の候補の z（q）の最大",
            "5a_breakdown の tasks・selection_error": "台帳（held_out_is_door・shop_cue・hit・predicted_edge）と注意の記録（capable）",
            "5a_breakdown の rate_in_cell": "その種類の選び間違い ÷ その種類の課題",
            "5a_breakdown の contribution_to_overall": "その種類の選び間違い ÷ 全課題（wave1.py の率の分母）。4 種類の和が全課題の率",
        },
        multi_value_format="一つの候補に印の席が複数あれば | で区切る。正答の候補が複数あれば ; で区切る（並びは candidates の順）",
        na_values_in_cases=dict(na_fields) or "なし",
        side_seal_check={f"{g}a/{g}b": dict(checked=sum(r["side_checked"] for r in results if r["row"][0] == g),
                                            agree=sum(r["side_agree"] for r in results if r["row"][0] == g),
                                            disagree_examples=[x for r in results if r["row"][0] == g for x in r["side_disagree"]][:30])
                         for g in GROUPS},
        source_code="計算の式は ~/sfn/sfn-compression-abm の tools/attnsme.py・tools/attnratio.py・tools/smeshared.py・tools/v39.py（c7921598・4ceadf63・c57467ea・e9ed84a で attnsme.py は同じ中身）を読んで合わせた",
        not_read="side の sme.states.jsonl.gz・routing.jsonl・stage2・evictions は読んでいない",
    )
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for g in GROUPS:
        print(g, tot[g], EXPECTED[g])
    print("NA の本：", na_runs)


if __name__ == "__main__":
    sys.exit(main())
