"""1. 誤りの型の分類（一本ごと）と 2. 選び間違いの診断（世界2 の例外の日のドア課題）。読むだけ。

材料：本番の台帳（日 shop_cue・ドア held_out_is_door・当たり hit・答え predicted_edge・使った定義 R_used）、
      本番の side の shop.jsonl（シールの席＝which が sig の (R, reg, slot)）、
      run_replay.py が残した候補の記録（tools/selcands_sme.py の sme.candidates.jsonl.gz）。
定め方（control/2026-10-05_SME版でlogPの試し_Codex.md と同じ）：
  正解＝hit、黙り＝答えなし、外れ＝それ以外。
  選び間違い＝外れた試行で、門を通って正しく答える定義があった件（候補の記録の correct_gate_passed）。区別の喪失＝無かった件。
診断（control/attn_seal_diagnostic_2026-10-05/ の 136 件と同じ分類）：
  シールの席の区分＝席ごとに 状態[名前]（F は固定の名、H は回数 1 以上の履歴の名を名の順に | でつなぐ、U は名なし）を + でつなぐ。
  シールの席が無い定義は「席が無い」、門を通る正解の候補が無ければ「門上候補なし」。
  門を通る正解の候補のうち一番上：N3 → 分母（F+H の席の数）→ 新しさ（生まれた試行）→ 名前 の順（~/n3sel_out/stage1_tables.py と同じ並べ方）。
使い方：python3.12 tables.py [--redo]
"""
import gzip
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

from common import (ARMS, OUT, REPLAY_DIR, WORK, jdump, ledger_path, ledger_rows, run_dir, side_dir, write_csv)

TAB_DIR = WORK / "tables"
DAY = {"e": "例外", "n": "通常"}


def day_label(cue):
    return DAY.get(cue, "なし" if cue is None else str(cue))


def seat_names(s):
    if s["state"] == "F":
        return [s["fixed_name"]]
    if s["state"] == "H":
        h = s["history"] or {}
        return sorted(k for k, v in h.items() if v >= 1) if isinstance(h, dict) else sorted(h)
    return []


def seal(c, sealkeys):
    if c is None:
        return None
    seats = []
    for s in sorted(c["slots"], key=lambda s: s["slot"]):
        if (c["R"], c["born_trial"], s["slot"]) in sealkeys:
            seats.append({"slot": s["slot"], "state": s["state"], "names": seat_names(s), "history": s["history"] or None})
    return seats


def label(seats):
    if seats is None:
        return "門上候補なし"
    if not seats:
        return "席が無い"
    return "+".join(x["state"] + ("[" + "|".join(x["names"]) + "]" if x["names"] else "") for x in seats)


def rank_key(c):
    return (-c["N3"], -c["denominator"], -c["born_trial"], c["R"])


def describe(prefix, c, sealkeys):
    if c is None:
        return {prefix + k: "" for k in ("R", "born_trial", "N3", "seats_total", "alive_FH", "F", "H", "U", "support",
                                        "gate_passed", "seal_class", "seal_state", "seal_seats")}
    seats = seal(c, sealkeys)
    return {prefix + "R": c["R"], prefix + "born_trial": c["born_trial"], prefix + "N3": c["N3"],
            prefix + "seats_total": len(c["slots"]), prefix + "alive_FH": c["F"] + c["H"],
            prefix + "F": c["F"], prefix + "H": c["H"], prefix + "U": c["U"], prefix + "support": c["support"],
            prefix + "gate_passed": c["gate_passed"], prefix + "seal_class": label(seats),
            prefix + "seal_state": "+".join(x["state"] for x in seats) if seats else "none",
            prefix + "seal_seats": jdump(seats)}


def process(arm, seed):
    t0, c0 = time.monotonic(), time.process_time()
    rep = json.loads((REPLAY_DIR / arm / f"seed{seed:03d}" / "replay.json").read_text())
    prod = run_dir(arm, seed)
    sd = side_dir(prod)
    events = [json.loads(l) for l in open(sd / f"seed{seed:03d}.shop.jsonl", encoding="utf-8")]
    sealkeys = {(e["R"], e["reg"], e["slot"]) for e in events if e.get("which") == "sig"}
    by_time = defaultdict(list)
    for e in events:
        if e.get("which") == "sig":
            by_time[e["trial"]].append(e)
    expected = {}
    cands = gzip.open(REPLAY_DIR / arm / f"seed{seed:03d}" / "sme.candidates.jsonl.gz", "rt", encoding="utf-8")
    counts = Counter()
    cases = []
    checks = Counter()
    for row in ledger_rows(ledger_path(prod, seed)):
        if row.get("record_type", "trial") != "trial":
            continue
        t = row["prediction_order"]
        cr = json.loads(next(cands))
        assert cr["trial"] == t, (cr["trial"], t)
        hit = bool(row["hit"])
        if cr["original_hit"] != hit:
            checks["候補の記録と台帳の当たりが違う"] += 1
        edge = row["predicted_edge"]
        if (edge is None) != ("abstain_reason" in cr["prediction"]):
            checks["候補の記録と台帳の答えの有無が違う"] += 1
        outcome = "correct" if hit else "silent" if edge is None else "wrong"
        d = day_label(row.get("shop_cue"))
        door = bool(row.get("held_out_is_door"))
        kind = None
        if outcome == "wrong":
            kind = "selection_error" if cr["correct_gate_passed"] else "distinction_loss"
        for scope in ("全課題",) + (("ドア課題",) if door else ()):
            counts[(scope, d, "tasks")] += 1
            counts[(scope, d, outcome)] += 1
            if kind:
                counts[(scope, d, kind)] += 1
        if kind == "selection_error" and arm.startswith("w2_") and row.get("shop_cue") == "e" and door:
            sel = [c for c in cr["candidates"] if c["selected"]]
            if len(sel) != 1 or sel[0]["R"] != row["R_used"] or cr["chosen_R"] != row["R_used"]:
                checks["選ばれた定義が台帳の R_used と違う"] += 1
            s = sel[0] if sel else None
            correct = sorted((c for c in cr["candidates"] if c["hit"] and c["gate_passed"]), key=rank_key)
            best = correct[0] if correct else None
            # シールの席の状態を shop.jsonl の出来事と突き合わせる（136 件の抽出と同じ確かめ）
            for c in [s] + correct:
                for x in seal(c, sealkeys) or []:
                    exp = expected.get((c["R"], c["born_trial"], x["slot"]))
                    checks["シールの席の状態の突き合わせ"] += 1
                    if exp != x["state"]:
                        checks["シールの席の状態が出来事の記録と違う"] += 1
            truth = row["held_out_content"]
            any_c = cr["any_correct"]
            item = {"arm": arm, "seed": seed, "trial": t, "shop": row.get("shop_type"), "day": "exception",
                    "baseline_class": "selection_error",
                    "availability": "above" if cr["correct_gate_passed"] else "below" if any_c else "absent",
                    "truth": jdump([truth["predicate"], truth["arguments"]]),
                    "answer": jdump([edge["predicate"], edge["arguments"]]),
                    **describe("selected_", s, sealkeys),
                    "correct_candidates_above_gate": len(correct),
                    "best_tied_at_top_N3": sum(c["N3"] == best["N3"] for c in correct) if best else 0,
                    **describe("best_correct_", best, sealkeys),
                    "N3_gap_best_minus_selected": (best["N3"] - s["N3"]) if best and s else "",
                    "all_correct_above_gate": jdump([{"R": c["R"], "N3": c["N3"], "seal_class": label(seal(c, sealkeys))}
                                                    for c in correct])}
            cases.append(item)
        for e in by_time.get(t, []):
            key = (e["R"], e["reg"], e["slot"])
            if e["to"] == "定義ごと消えた":
                expected.pop(key, None)
            else:
                expected[key] = e["to"]
    assert next(cands, None) is None, "候補の記録が台帳より長い"
    res = {"arm": arm, "seed": seed, "run_commit": rep["run_commit"], "replay_status": rep["status"],
           "replay_mismatches": rep.get("replay_mismatches"), "counts": [[*k, v] for k, v in sorted(counts.items())],
           "cases": cases, "checks": dict(checks), "started": datetime.now().isoformat(timespec="seconds"),
           "wall_seconds": round(time.monotonic() - t0, 2), "cpu_seconds": round(time.process_time() - c0, 2),
           "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    return res


ET_FIELDS = ["arm", "seed", "run_commit", "scope", "day", "tasks", "correct", "wrong", "silent",
             "selection_error", "distinction_loss", "replay_status", "replay_mismatches"]
CASE_FIELDS = None


def main():
    redo = "--redo" in sys.argv
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        for p in sorted((REPLAY_DIR / arm).glob("seed*/replay.json")) if (REPLAY_DIR / arm).exists() else []:
            seed = int(p.parent.name[4:])
            rep = json.loads(p.read_text())
            dest = TAB_DIR / arm / f"seed{seed:03d}.json"
            if rep["status"] != "ok" or (dest.exists() and not redo):
                continue
            r = process(arm, seed)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{arm} 種{seed}：選び間違いの診断 {len(r['cases'])} 件、確かめ {r['checks']}、{r['wall_seconds']}秒", flush=True)
    all_classes = []
    timing = []
    for arm in ARMS:
        reps = {int(p.parent.name[4:]): json.loads(p.read_text())
                for p in sorted((REPLAY_DIR / arm).glob("seed*/replay.json"))} if (REPLAY_DIR / arm).exists() else {}
        tabs = {int(p.stem[4:]): json.loads(p.read_text())
                for p in sorted((TAB_DIR / arm).glob("seed*.json"))} if (TAB_DIR / arm).exists() else {}
        if not reps:
            continue
        rows = []
        total = Counter()
        keys = set()
        for seed in sorted(reps):
            rep = reps[seed]
            timing.append({"arm": arm, "seed": seed, "step": "replay(selcands_sme)", "wall_seconds": rep.get("wall_seconds"),
                           "peak_rss_mb": rep.get("peak_rss_mb"), "started": rep.get("started"), "status": rep.get("status")})
            if seed not in tabs:
                rows.append({"arm": arm, "seed": seed, "run_commit": rep.get("run_commit"), "scope": "", "day": "",
                             "replay_status": rep["status"], "replay_mismatches": rep.get("replay_mismatches")})
                continue
            tb = tabs[seed]
            timing.append({"arm": arm, "seed": seed, "step": "tables", "wall_seconds": tb["wall_seconds"],
                           "peak_rss_mb": tb["peak_rss_mb"], "started": tb["started"], "status": "ok"})
            c = {(s, d, k): v for s, d, k, v in tb["counts"]}
            for (s, d, k), v in c.items():
                total[(s, d, k)] += v
                keys.add((s, d))
            for s, d in sorted({(s, d) for s, d, _ in c}, key=lambda x: (x[0] != "全課題", x[1] != "例外", x[1])):
                rows.append({"arm": arm, "seed": seed, "run_commit": tb["run_commit"], "scope": s, "day": d,
                             **{k: c.get((s, d, k), 0) for k in ("tasks", "correct", "wrong", "silent", "selection_error", "distinction_loss")},
                             "replay_status": tb["replay_status"], "replay_mismatches": tb["replay_mismatches"]})
        seeds_ok = [s for s in sorted(tabs)]
        for s, d in sorted(keys, key=lambda x: (x[0] != "全課題", x[1] != "例外", x[1])):
            rows.append({"arm": arm, "seed": "計", "run_commit": "種 " + ",".join(map(str, seeds_ok)), "scope": s, "day": d,
                         **{k: total.get((s, d, k), 0) for k in ("tasks", "correct", "wrong", "silent", "selection_error", "distinction_loss")},
                         "replay_status": "ok" if all(reps[x]["status"] == "ok" for x in seeds_ok) else "一部 failed",
                         "replay_mismatches": sum(1 for x in reps if reps[x]["status"] != "ok")})
        write_csv(OUT / f"error_types_{arm}.csv", rows, ET_FIELDS)
        # 2. 診断（世界2）
        if arm.startswith("w2_") and tabs:
            cases = [c for s in sorted(tabs) for c in tabs[s]["cases"]]
            fields = list(cases[0]) if cases else ["arm", "seed", "trial"]
            write_csv(OUT / f"selection_error_diagnostic_{arm}.csv", cases, fields)
            cls = Counter((c["day"], c["availability"], c["selected_seal_class"], c["best_correct_seal_class"]) for c in cases)
            st = Counter((c["day"], c["availability"], c["selected_seal_state"], c["best_correct_seal_state"] or "no_above_candidate") for c in cases)
            crow = [{"arm": arm, "seeds": ",".join(map(str, sorted(tabs))), "day": k[0], "availability": k[1],
                     "selected_class": k[2], "best_correct_class": k[3], "trials": n} for k, n in sorted(cls.items())]
            all_classes += crow
            write_csv(OUT / f"selection_error_class_counts_{arm}.csv", crow,
                      ["arm", "seeds", "day", "availability", "selected_class", "best_correct_class", "trials"])
            write_csv(OUT / f"selection_error_state_counts_{arm}.csv",
                      [{"arm": arm, "seeds": ",".join(map(str, sorted(tabs))), "day": k[0], "availability": k[1],
                        "selected_state": k[2], "best_correct_state": k[3], "trials": n} for k, n in sorted(st.items())],
                      ["arm", "seeds", "day", "availability", "selected_state", "best_correct_state", "trials"])
            chk = Counter()
            for s in tabs.values():
                chk.update(s["checks"])
            (OUT / f"checks_{arm}.json").write_text(json.dumps({"seeds": sorted(tabs), "checks": dict(chk)}, ensure_ascii=False, indent=1) + "\n")
        elif tabs:
            chk = Counter()
            for s in tabs.values():
                chk.update(s["checks"])
            (OUT / f"checks_{arm}.json").write_text(json.dumps({"seeds": sorted(tabs), "checks": dict(chk)}, ensure_ascii=False, indent=1) + "\n")
    if all_classes:
        write_csv(OUT / "selection_error_class_counts_all.csv", all_classes,
                  ["arm", "seeds", "day", "availability", "selected_class", "best_correct_class", "trials"])
    # 記憶の比べの時間も同じ表に
    from common import MEM_DIR
    for arm in ARMS:
        if (MEM_DIR / arm).exists():
            for p in sorted((MEM_DIR / arm).glob("seed*.json")):
                m = json.loads(p.read_text())
                timing.append({"arm": arm, "seed": m["seed"], "step": "memcompare", "wall_seconds": m.get("wall_seconds"),
                               "peak_rss_mb": m.get("peak_rss_mb"), "started": m.get("started"), "status": m.get("status")})
    if timing:
        write_csv(OUT / "timing.csv", sorted(timing, key=lambda r: (ARMS.index(r["arm"]), r["seed"], r["step"])),
                  ["arm", "seed", "step", "wall_seconds", "peak_rss_mb", "started", "status"])


if __name__ == "__main__":
    main()
