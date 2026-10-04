"""完走・検査済みの動詞の集計だけをまとめる。比較の学び手は実行しない。"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def ratio(n, d):
    return n / d if d else None


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def fmt(x):
    return "—" if x is None else f"{x:.4f}"


def aggregate(base, plan):
    base = Path(base)
    output = base / "aggregate"
    output.mkdir(exist_ok=True)
    totals = defaultdict(Counter)
    novel_totals = defaultdict(Counter)
    over, novel, events, memories, responses, resources = [], [], [], [], [], []
    classifications, name_states = defaultdict(Counter), defaultdict(Counter)
    completed = []
    for run in plan["runs"]:
        root = base / run["label"]
        if not (root / "complete.json").exists():
            continue
        r = json.loads((root / "analysis/summary.json").read_text())
        meta = {"arm": run["arm"], "U": run["U"], "seed": run["seed"]}
        group = (run["arm"], run["U"])
        completed.append(run["label"])
        for row in r["overregularization"]:
            over.append({**meta, **row})
            totals[(*group, row["bin"], row["verb"])].update({k: row[k] for k in ("queries", "correct", "REG", "abstain", "other", "exposure")})
        for row in r["novel"]:
            novel.append({**meta, **row})
            novel_totals[(*group, row["verb"])].update({k: v for k, v in row.items() if k not in ("t", "verb")})
        events += [{**meta, **row} for row in r["recovery"]]
        memories += [{**meta, **row} for row in r["memory"]]
        responses += [{**meta, **row} for row in r["answering"]]
        classifications[group].update(r["classification"])
        name_states[group].update(r["selected_name_states"])
        res = json.loads((root / "resources.json").read_text())
        resources.append({**meta, **{k: res.get(k) for k in ("model_seconds", "analysis_seconds", "supervised_wall_seconds", "process_peak_rss_bytes_time", "max_aggregate_rss_mib_sampled_1s", "output_bytes")}})
    pooled, bin_totals = [], []
    for (arm, u, b, v), c in sorted(totals.items()):
        den = c["correct"] + c["REG"]
        pooled.append({"arm": arm, "U": u, "bin": b, "verb": v, **dict(c), "marcus_denominator": den,
                       "marcus_rate": ratio(c["REG"], den), "REG_all_queries_rate": ratio(c["REG"], c["queries"])})
    by_bin = defaultdict(list)
    for row in pooled:
        by_bin[(row["arm"], row["U"], row["bin"])].append(row)
    for (arm, u, b), rows in sorted(by_bin.items()):
        valid = [r for r in rows if r["marcus_rate"] is not None]
        mass = sum(r["exposure"] for r in valid)
        c = Counter()
        for r in rows:
            c.update({k: r[k] for k in ("queries", "correct", "REG", "abstain", "other", "exposure")})
        bin_totals.append({"arm": arm, "U": u, "start": b * 500, "end": (b + 1) * 500, **dict(c),
                           "observed_verbs": len(valid), "weight_coverage": ratio(mass, c["exposure"]),
                           "frequency_weighted_full8": sum(r["exposure"] * r["marcus_rate"] for r in valid) / mass if mass and len(valid) == 8 else None,
                           "frequency_weighted_observed": sum(r["exposure"] * r["marcus_rate"] for r in valid) / mass if mass else None,
                           "uniform_full8": sum(r["marcus_rate"] for r in valid) / 8 if len(valid) == 8 else None,
                           "uniform_observed": sum(r["marcus_rate"] for r in valid) / len(valid) if valid else None,
                           "pooled_marcus": ratio(c["REG"], c["correct"] + c["REG"]),
                           "REG_all_queries": ratio(c["REG"], c["queries"])})
    novel_summary = []
    for (arm, u, v), c in sorted(novel_totals.items()):
        n = sum(c[k] for k in ("REG", "IRR", "abstain", "other"))
        novel_summary.append({"arm": arm, "U": u, "verb": v, "queries": n, **dict(c),
                              **{k + "_rate": ratio(c[k], n) for k in ("REG", "IRR", "abstain", "other")}})
    write_csv(output / "overregularization_per_seed.csv", over)
    write_csv(output / "overregularization_per_verb.csv", pooled)
    write_csv(output / "overregularization_bins.csv", bin_totals)
    write_csv(output / "recovery_events.csv", events)
    write_csv(output / "novel_per_time_seed.csv", novel)
    write_csv(output / "novel_per_verb.csv", novel_summary)
    write_csv(output / "memory.csv", memories)
    write_csv(output / "answering.csv", responses)
    write_csv(output / "resources.csv", resources)
    write_csv(output / "classification.csv", [{"arm": a, "U": u, **dict(c)} for (a, u), c in sorted(classifications.items())])
    write_csv(output / "name_seats.csv", [{"arm": a, "U": u, "state": s, "count": n} for (a, u), c in sorted(name_states.items()) for s, n in sorted(c.items())])
    status = {"complete": len(completed), "planned": len(plan["runs"]), "completed_runs": completed,
              "baseline": "design_only", "seeds": sorted({r["seed"] for r in plan["runs"] if r["label"] in completed})}
    (output / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    md = [f"完走・照合済み {len(completed)}/30本。種は1〜5のみ。区間は試行番号0始まり、右端を含まない。", "",
          "|保持|U|区間|REG／全過去形質問|出現頻度加重（8語）|均等平均（8語）|分母がある語数|", "|---|---|---|---:|---:|---:|---:|"]
    for r in bin_totals:
        md.append(f"|{r['arm']}|{r['U']}|{r['start']}–{r['end']}|{fmt(r['REG_all_queries'])}|{fmt(r['frequency_weighted_full8'])}|{fmt(r['uniform_full8'])}|{r['observed_verbs']}|")
    md += ["", "8語全体の平均は、1語でも分母が0なら欠測（—）。観測できた語だけの平均と重みの被覆率はCSVに別記。頻度加重の重みは当区間の動詞の実際の出現数。", "",
           "|保持|U|完走数|崩れ→回復の完了数|選び間違い|区別の喪失|全質問の回答／黙り|終点記憶量の平均bits|", "|---|---|---:|---:|---:|---:|---|---:|"]
    for group in sorted(classifications.keys() | {(r["arm"], r["U"]) for r in resources}):
        a, u = group
        rs = [r for r in resources if (r["arm"], r["U"]) == group]
        ev = [e for e in events if (e["arm"], e["U"]) == group]
        ans = [r for r in responses if (r["arm"], r["U"]) == group]
        answered, silent = sum(r.get("answered", 0) for r in ans), sum(r.get("abstain", 0) for r in ans)
        end = [r["bits"] for r in memories if (r["arm"], r["U"]) == group and r["t"] == 5000 and r["bits"] is not None]
        md.append(f"|{a}|{u}|{len(rs)}|{len(ev)}|{classifications[group]['selection_error']}|{classifications[group]['distinction_loss']}|{answered}/{silent}|{fmt(sum(end)/len(end) if end else None)}|")
    md += ["", "|保持|U|新語質問数|REG|IRR名|黙り|その他|", "|---|---|---:|---:|---:|---:|---:|"]
    for a, u in sorted({(r["arm"], r["U"]) for r in novel_summary}):
        rows = [r for r in novel_summary if r["arm"] == a and r["U"] == u]
        n = sum(r["queries"] for r in rows)
        vals = [fmt(ratio(sum(r.get(k, 0) for r in rows), n)) for k in ("REG", "IRR", "abstain", "other")]
        md.append(f"|{a}|{u}|{n}|" + "|".join(vals) + "|")
    md += ["", "語別・種別・時点別の数、IRR_1〜IRR_8の内訳、各回復の三時点、名前の席、記憶のF/H/Uとbits、一本の時間・RSSは同じフォルダのCSV。候補ごとの生記録はローカルの各本 analysis/cases.jsonl.gz に保存。", ""]
    (output / "tables.md").write_text("\n".join(md))
    return output
