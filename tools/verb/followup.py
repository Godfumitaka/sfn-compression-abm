"""2026-10-05の承認範囲：既存30本の黙りの集計と、独立学び手の種1〜5。

台帳と補助記録を読むだけ。模型の予測・学習・世界生成を呼ばない。
例外学び手には語名、問いの有無、見えた/開示された形だけを渡す。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path

from aggregate import fmt, ratio, write_csv
from exception_learner import run_sequence

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent
BASE = ROOT / "stage3_night"
OUTPUT = ROOT / "followup_2026-10-05"
REASONS = ("no_prototype", "no_definition", "below_threshold", "below_tau", "no_projectable_relation", "no_gap_candidate", "ambiguous_projection")


def rates(counts):
    c = {k: counts[k] for k in ("queries", "correct", "REG", "abstain", "other")}
    den = c["correct"] + c["REG"]
    return {**c, "marcus_denominator": den, "marcus_rate": ratio(c["REG"], den), "REG_all_queries_rate": ratio(c["REG"], c["queries"])}


def recovery_step(state, t, label):
    if label == "correct":
        event = [state["correct"], state["REG"], t] if "REG" in state else None
        state.clear()
        state["correct"] = t
        return event
    if label == "REG" and "correct" in state:
        state.setdefault("REG", t)
    return None


def abstain_detail(reason, row, ambig=None, probe=False):
    if reason == "below_tau":
        if probe:
            return "below_tau_gate_details_not_recorded"
        return "below_tau_no_passed_definition" if not row["tau_passed_defs"] else "below_tau_other_definition_passed"
    if reason != "ambiguous_projection":
        return reason
    if ambig is not None:
        if ambig.get("held_tied") == "1" and ambig.get("held_state") in ("F", "H", "U"):
            return "ambiguous_queried_" + ambig["held_state"] + "_tie"
        if int(ambig.get("tied_U_other") or 0):
            return "ambiguous_other_U_tie"
        if int(ambig.get("tied_H_other") or 0):
            return "ambiguous_other_H_tie"
    return "ambiguous_details_not_recorded"


def update_silence(totals, reasons, details, key, answer, reason, detail):
    totals[key]["queries"] += 1
    if answer is None:
        if not reason:
            raise RuntimeError("黙りの理由が記録されていない")
        totals[key]["abstain"] += 1
        reasons[(*key, reason)] += 1
        details[(*key, detail)] += 1
    else:
        if reason:
            raise RuntimeError("回答と黙り理由が同じ行にある")
        totals[key]["answered"] += 1


def score_baseline(seed, records, probes):
    public = [{k: r[k] for k in ("trial", "verb", "past_asked", "observed_past")} for r in records]
    public_probes = [{"t": r["t"], "verb": r["verb"]} for r in probes]
    started = time.monotonic()
    result = run_sequence(public, public_probes)
    counts, exposure, novel = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    recovery = defaultdict(dict)
    events = []
    answer_rows = []
    for rec, pred in zip(records, result["answers"], strict=True):
        t, v = rec["trial"], rec["verb"]
        exposure[(t // 500, v)]["exposure"] += 1
        if not rec["past_asked"]:
            continue
        a = pred["answer"]
        label = "correct" if a == rec["correct_past"] else "REG" if a == "REG" else "other"
        answer_rows.append({"seed": seed, **pred, "correct_past": rec["correct_past"], "class": rec["class"],
                            "hit": int(label == "correct"), "observed_after_answer": rec["observed_past"], "observation_source": rec["observation_source"]})
        if rec["class"] == "irregular":
            counts[(t // 500, v)]["queries"] += 1
            counts[(t // 500, v)][label] += 1
            event = recovery_step(recovery[v], t, label)
            if event:
                events.append({"seed": seed, "verb": v, "correct_before": event[0], "REG_start": event[1], "correct_after": event[2]})
    probe_rows = []
    for rec, pred in zip(probes, result["probes"], strict=True):
        if (rec["t"], rec["verb"]) != (pred["t"], pred["verb"]):
            raise RuntimeError("比べの学び手の試験の並びが違う")
        probe_rows.append({"seed": seed, **pred, "class": rec["class"], "truth": rec["truth"]})
        if rec["class"] == "novel":
            a = pred["answer"]
            cat = "abstain" if a is None else "REG" if a == "REG" else "IRR" if a.startswith("IRR_") else "other"
            novel[(rec["t"], rec["verb"])][cat] += 1
            if cat == "IRR":
                novel[(rec["t"], rec["verb"])][a] += 1
    over = [{"seed": seed, "bin": b, "start": b * 500, "end": (b+1)*500, "verb": f"V{k:02d}",
             "exposure": exposure[(b, f"V{k:02d}")]["exposure"], **rates(counts[(b, f"V{k:02d}")])} for b in range(10) for k in range(33, 41)]
    novel_rows = [{"seed": seed, "t": t, "verb": v, **dict(c)} for (t, v), c in sorted(novel.items())]
    folder = OUTPUT / "baseline" / f"seed{seed:03d}"
    folder.mkdir(parents=True)
    write_csv(folder / "past_answers.csv", answer_rows)
    write_csv(folder / "probe_answers.csv", probe_rows)
    write_csv(folder / "registrations.csv", [{"seed": seed, **r} for r in result["registrations"]])
    write_csv(folder / "public_input.csv", public)
    summary = {"seed": seed, "overregularization": over, "recovery": events, "novel": novel_rows,
               "dictionary": result["dictionary"], "registrations": result["registrations"], "past_queries": len(answer_rows),
               "past_correct": sum(r["hit"] for r in answer_rows), "past_REG": sum(r["answer"] == "REG" for r in answer_rows),
               "probes": len(probe_rows), "learner_seconds": time.monotonic()-started}
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def baseline_tables(summaries):
    output = OUTPUT / "baseline"
    over = [r for s in summaries for r in s["overregularization"]]
    events = [r for s in summaries for r in s["recovery"]]
    novel = [r for s in summaries for r in s["novel"]]
    totals = defaultdict(Counter)
    for row in over:
        totals[(row["bin"], row["verb"])].update({k: row[k] for k in ("exposure", "queries", "correct", "REG", "abstain", "other")})
    pooled = [{"bin": b, "verb": v, "start": b*500, "end": (b+1)*500, "exposure": c["exposure"], **rates(c)} for (b, v), c in sorted(totals.items())]
    by_bin = defaultdict(list)
    for row in pooled:
        by_bin[row["bin"]].append(row)
    bins = []
    for b, rows in sorted(by_bin.items()):
        valid = [r for r in rows if r["marcus_rate"] is not None]
        mass = sum(r["exposure"] for r in valid)
        c = Counter()
        for r in rows:
            c.update({k: r[k] for k in ("exposure", "queries", "correct", "REG", "abstain", "other")})
        bins.append({"arm": "exception_dictionary", "U": "REG_default", "start": b*500, "end": (b+1)*500, **dict(c),
                     "observed_verbs": len(valid), "weight_coverage": ratio(mass, c["exposure"]),
                     "frequency_weighted_full8": sum(r["exposure"]*r["marcus_rate"] for r in valid)/mass if mass and len(valid) == 8 else None,
                     "frequency_weighted_observed": sum(r["exposure"]*r["marcus_rate"] for r in valid)/mass if mass else None,
                     "uniform_full8": sum(r["marcus_rate"] for r in valid)/8 if len(valid) == 8 else None,
                     "uniform_observed": sum(r["marcus_rate"] for r in valid)/len(valid) if valid else None,
                     "pooled_marcus": ratio(c["REG"], c["correct"]+c["REG"]), "REG_all_queries": ratio(c["REG"],c["queries"])})
    nt = defaultdict(Counter)
    for row in novel:
        nt[row["verb"]].update({k: v for k, v in row.items() if k not in ("seed", "t", "verb")})
    nr = []
    for verb, c in sorted(nt.items()):
        n = sum(c[k] for k in ("REG", "IRR", "abstain", "other"))
        nr.append({"verb": verb, "queries": n, **dict(c), **{k+"_rate": ratio(c[k], n) for k in ("REG", "IRR", "abstain", "other")}})
    write_csv(output / "overregularization_per_seed.csv", over)
    write_csv(output / "overregularization_per_verb.csv", pooled)
    write_csv(output / "overregularization_bins.csv", bins)
    # 空の表にも欄名を残す。
    with (output / "recovery_events.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, ("seed", "verb", "correct_before", "REG_start", "correct_after"))
        writer.writeheader()
        writer.writerows(events)
    write_csv(output / "novel_per_time_seed.csv", novel)
    write_csv(output / "novel_per_verb.csv", nr)
    write_csv(output / "seeds.csv", [{k: s[k] for k in ("seed", "past_queries", "past_correct", "past_REG", "probes", "learner_seconds")} | {"dictionary_items": len(s["dictionary"]), "recovery_events": len(s["recovery"])} for s in summaries])
    with (BASE / "aggregate/overregularization_bins.csv").open() as f:
        model = list(csv.DictReader(f))
    write_csv(output / "model_and_baseline_bins.csv", model + bins)
    md = ["### 比べの学び手：例外の辞書＋REG（種1〜5）", "",
          "|学び手|区間|REG／全過去形質問|出現頻度加重（8語）|均等平均（8語）|分母がある語数|", "|---|---|---:|---:|---:|---:|"]
    for r in bins:
        md.append(f"|例外辞書|{r['start']}–{r['end']}|{fmt(r['REG_all_queries'])}|{fmt(r['frequency_weighted_full8'])}|{fmt(r['uniform_full8'])}|{r['observed_verbs']}|")
    md += ["", "|種|過去形質問|正答|REG回答（規則語含む）|崩れ→回復|終点例外辞書の語数|", "|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        md.append(f"|{s['seed']}|{s['past_queries']}|{s['past_correct']}|{s['past_REG']}|{len(s['recovery'])}|{len(s['dictionary'])}|")
    md += ["", "|新語|質問数|REG|IRR名|黙り|その他|", "|---|---:|---:|---:|---:|---:|"]
    for r in nr:
        md.append(f"|{r['verb']}|{r['queries']}|{fmt(r['REG_rate'])}|{fmt(r['IRR_rate'])}|{fmt(r['abstain_rate'])}|{fmt(r['other_rate'])}|")
    md += ["", "区間・分母・欠測・出現頻度の重み・回復エピソードの定義は模型と同じ。保持A/C/DとUの条件はこの学び手には無い。模型6条件と並べた表は model_and_baseline_bins.csv。全48語の試験回答、例外登録時点、公開入力の再生列も種別CSVに保存。", ""]
    (output / "tables.md").write_text("\n".join(md))


def silence_tables(totals, reasons, details):
    rows = []
    all_reasons = sorted(set(REASONS) | {key[-1] for key in reasons})
    for key, c in sorted(totals.items()):
        arm, u, phase, kind = key
        r = {"arm": arm, "U": u, "phase": phase, "verb_class": kind, **dict(c)}
        r.update({reason: reasons[(*key, reason)] for reason in all_reasons})
        r["abstain_rate"] = ratio(c["abstain"], c["queries"])
        if sum(r[reason] for reason in all_reasons) != c["abstain"]:
            raise RuntimeError("理由の件数が黙りの件数と一致しない")
        rows.append(r)
    write_csv(OUTPUT / "silence.csv", rows)
    dr = [{"arm": a, "U": u, "phase": p, "verb_class": k, "detail": d, "count": n} for (a, u, p, k, d), n in sorted(details.items())]
    write_csv(OUTPUT / "silence_details.csv", dr)
    names = {"regular": "規則", "irregular": "不規則", "novel": "新語"}
    md = ["### 黙りの内訳（既存記録のみ）", ""]
    for phase, title in (("training_all", "学習中の全問（過去形以外の質問も含む）"), ("training_past", "学習中の過去形質問"), ("probe_all", "非学習試験（全48語）")):
        md += [f"#### {title}", "", "|保持|U|動詞群|質問|黙り|率|原型無し|定義無し|構造の門|発話の門|投影・穴埋め無し|欠けた席の候補無し|同点・曖昧|", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in rows:
            if r["phase"] == phase:
                vals = [str(r.get(k, 0)) for k in REASONS]
                md.append(f"|{r['arm']}|{r['U']}|{names[r['verb_class']]}|{r['queries']}|{r.get('abstain',0)}|{fmt(r['abstain_rate'])}|"+"|".join(vals)+"|")
    md += ["", "理由名の列順は no_prototype / no_definition / below_threshold / below_tau / no_projectable_relation / no_gap_candidate / ambiguous_projection。no_definitionは照合候補の定義が無い場合、below_tauは選ばれた定義が発話の門を通らない場合。below_tauの『門を通る候補が一つもない／他の候補は通る』は学習中のtau_passed_defsから別記する。", "",
           "#### 同点と発話の門の補助記録", "", "|保持|U|対象|動詞群|記録の細分|件数|", "|---|---|---|---|---|---:|"]
    for r in dr:
        if r["detail"].startswith(("ambiguous", "below_tau")):
            md.append(f"|{r['arm']}|{r['U']}|{r['phase']}|{names[r['verb_class']]}|{r['detail']}|{r['count']}|")
    md += ["", "ambiguous_queried_U_tie / H_tieはambig.csvの『問われた席』の状態と同点印が揃った件。other_U/H_tieは別の席に同点が記録されている件。details_not_recordedはそれ以上の細分が記録から決められない件。非学習試験にはこの補助記録が無いので、U/Hの同点を推定せず未記録に分ける。", ""]
    (OUTPUT / "silence_tables.md").write_text("\n".join(md))


def main():
    global OUTPUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, choices=range(1, 6), help="読み手の小さな実測用。省略すると承認された全30本")
    args = ap.parse_args()
    started = time.monotonic()
    output = OUTPUT if args.seed is None else ROOT / f"followup_check_s{args.seed:02d}"
    OUTPUT = output
    OUTPUT.mkdir(exist_ok=False)
    plan = json.loads((BASE / "plan.json").read_text())
    expected = {(a, u, s) for s in range(1, 6) for a in ("A", "C", "D") for u in ("global", "abstain")}
    if len(plan["runs"]) != 30 or {(r["arm"],r["U"],r["seed"]) for r in plan["runs"]} != expected:
        raise RuntimeError("承認された30本と違う計画")
    totals, reasons, details = defaultdict(Counter), Counter(), Counter()
    tie_names, checks, baseline_summaries = Counter(), [], []
    hashes = {}
    runs = [r for r in plan["runs"] if args.seed is None or r["seed"] == args.seed and r["arm"] == "A" and r["U"] == "global"]
    for run in runs:
        arm, u, seed, label = run["arm"], run["U"], run["seed"], run["label"]
        folder = BASE / label
        if not (folder / "complete.json").exists():
            raise RuntimeError("完走・検査済みの印が無い")
        cell = json.loads((folder / "analysis/summary.json").read_text())["cell"]
        side = folder / "run/side" / cell
        amb = {}
        amb_path = side / f"seed{seed:03d}.ambig.csv"
        if amb_path.exists():
            with amb_path.open() as f:
                amb = {int(r["trial"]): r for r in csv.DictReader(f)}
        digest = hashlib.sha256()
        records = []
        ledger = folder / "run/ledgers/cells" / cell / f"seed{seed:03d}.jsonl.gz"
        with gzip.open(ledger, "rt") as f:
            header = json.loads(next(f))
            if header["run_seed"] != seed or header["trial_count"] != 5000:
                raise RuntimeError("台帳の種か長さが違う")
            for t, line in enumerate(f):
                row = json.loads(line)
                if row["prediction_order"] != t or row["verb_class"] not in ("regular", "irregular"):
                    raise RuntimeError("台帳の試行か動詞群が違う")
                asked, disclosed = bool(row["held_out_is_past"]), bool(row["f_fired"])
                feedback = row["feedback_content"]
                if disclosed != bool(feedback):
                    raise RuntimeError("開示の印と内容が違う")
                if asked and disclosed and feedback["predicate"] != row["correct_past"]:
                    raise RuntimeError("開示された過去形と研究者の記録が違う")
                observed = row["correct_past"] if not asked else feedback["predicate"] if disclosed else None
                rec = {"trial": t, "verb": row["verb_name"], "class": row["verb_class"], "correct_past": row["correct_past"],
                       "past_asked": asked, "disclosed": disclosed, "observed_past": observed,
                       "observation_source": "visible" if not asked else "feedback" if disclosed else "unobserved",
                       "held_predicate": row["held_out_content"]["predicate"]}
                digest.update((json.dumps(rec, sort_keys=True, separators=(",", ":"))+"\n").encode())
                records.append(rec)
                pe = row["predicted_edge"]
                answer = pe["predicate"] if pe else None
                reason = row["abstain_reason"]
                a = amb.get(t)
                if a is not None and (reason != "ambiguous_projection" or a["R"] != row["R_used"]):
                    raise RuntimeError("曖昧さの補助記録が台帳と違う")
                detail = abstain_detail(reason, row, a)
                for phase in ("training_all", "training_past") if asked else ("training_all",):
                    key = (arm, u, phase, row["verb_class"])
                    update_silence(totals, reasons, details, key, answer, reason, detail)
                if detail == "ambiguous_queried_U_tie":
                    slot = int(a["held_slot"])
                    dist = next((d for d in row["candidate_distribution"] if d["slot_index"] == slot), None)
                    if dist is not None:
                        c = dist["candidates"]
                        mx = max((w for _, w in c), default=0)
                        winners = "|".join(sorted(p for p,w in c if w == mx))
                        tie_names[(arm,u,row["verb_class"],asked,winners)] += 1
        if len(records) != 5000:
            raise RuntimeError("台帳の試行数が違う")
        probes, pdigest = [], hashlib.sha256()
        with (side / f"seed{seed:03d}.probe.jsonl").open() as f:
            for line in f:
                p = json.loads(line)
                rec = {"t": p["t"], "verb": p["verb_name"], "class": p["verb_class"], "truth": p["truth"]}
                probes.append(rec)
                pdigest.update((json.dumps(rec, sort_keys=True, separators=(",", ":"))+"\n").encode())
                update_silence(totals, reasons, details, (arm,u,"probe_all",p["verb_class"]), p["answer"], p.get("abstain"), abstain_detail(p.get("abstain"), p, probe=True))
        if len(probes) != 2400 or {(p["t"],p["verb"]) for p in probes} != {(t,f"V{k:02d}") for t in range(100,5001,100) for k in range(1,49)}:
            raise RuntimeError("試験時点・語の並びが計画と違う")
        h = (digest.hexdigest(), pdigest.hexdigest(), header["world_hash"])
        if seed in hashes and hashes[seed] != h:
            raise RuntimeError("同じ種の出現・質問・開示・試験が条件間で違う")
        hashes[seed] = h
        if arm == "A" and u == "global":
            baseline_summaries.append(score_baseline(seed, records, probes))
        checks.append({"arm": arm, "U": u, "seed": seed, "ledger_rows": len(records), "probe_rows": len(probes), "ambig_rows": len(amb),
                       "exposure_query_feedback_sha256": h[0], "probe_design_sha256": h[1], "world_hash": h[2]})
        print(label, "読取完了", len(records), len(probes), flush=True)
    silence_tables(totals, reasons, details)
    baseline_tables(baseline_summaries)
    write_csv(OUTPUT / "sequence_checks.csv", checks)
    write_csv(OUTPUT / "queried_U_tie_names.csv", [{"arm": a,"U": u,"verb_class": k,"past_asked": p,"tied_names": n,"count": c} for (a,u,k,p,n),c in sorted(tie_names.items())])
    allq = sum(c["queries"] for k,c in totals.items() if k[2] == "training_all")
    alla = sum(c["abstain"] for k,c in totals.items() if k[2] == "training_all")
    result = {"model_reruns": 0, "model_ledgers_read": len(runs), "model_trials_read": allq, "model_abstain": alla,
              "model_abstain_rate": ratio(alla,allq), "baseline_seeds": [s["seed"] for s in baseline_summaries],
              "condition_sequence_equal": True, "elapsed_seconds": round(time.monotonic()-started,3),
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "schuler_runs": 0}
    (OUTPUT / "checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
