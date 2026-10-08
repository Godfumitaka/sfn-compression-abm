"""動詞の台帳だけを逐次集計する。候補の答え直しは既存 selcands と同じ手順。

読み直しの状態・世界・予測の一致を検査し、不一致なら集計を確定しない。
模型の予測や状態へ集計値を戻さない。種は明示された1〜20の一本だけ。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from random import Random

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "tools"), str(REPO), str(Path(__file__).parent)]
import replay_state as sr

BIN = 500


def count_answer(counts, answer, correct):
    counts["queries"] += 1
    if answer is None:
        counts["abstain"] += 1
    elif answer == correct:
        counts["correct"] += 1
    elif answer == "REG":
        counts["REG"] += 1
    else:
        counts["other"] += 1


def rates(counts):
    c = {key: counts.get(key, 0) for key in ("queries", "correct", "REG", "abstain", "other")}
    den = c["correct"] + c["REG"]
    return {**c, "marcus_denominator": den,
            "marcus_rate": c["REG"] / den if den else None,
            "REG_all_queries_rate": c["REG"] / c["queries"] if c["queries"] else None}


def recovery_step(state, t, label):
    """同じ語の正答/REGの部分列の、重ならない完了エピソード。黙り等は飛ばす。"""
    if label == "correct":
        event = [state["correct"], state["REG"], t] if "REG" in state else None
        state.clear()
        state["correct"] = t
        return event
    if label == "REG" and "correct" in state:
        state.setdefault("REG", t)
    return None


def make_task(root, cell, seed, scratch):
    import sweep
    fl = json.loads((root / "flag.json").read_text())
    cfg = json.loads((REPO / fl["config"]).read_text())
    cfg["trial_count"] = int(fl.get("horizon") or cfg["trial_count"])
    cfg["seed_file"] = fl["effective_seed_file"]
    cfg["output"]["dir"] = str(scratch / "ledgers")
    cfg["fixed"]["nsim_threshold"] = fl["nsim"]
    cfg["axes"]["verbatim_theta"] = [fl["vt"]]
    runs = [r for r in sweep.enumerate_runs(cfg) if r["seed"] == seed and r["cell"] == cell]
    if len(runs) != 1:
        raise RuntimeError("読み直しのセルが一意でない")
    task = {**fl, **runs[0], "cfg": cfg, "code_commit": fl["commit"], "out_root": str(scratch),
            "orig_dir": None, "prune": fl["greedy"], "compare": False,
            "v39_budget": None if fl["v39_budget"] == "inf" else int(fl["v39_budget"])}
    # 記録だけの包みは外す。C/Dの保持規則はそのまま入れ、更新は実行しない。
    for key in ("dump_answers", "dump_routing", "probe_world", "select_log", "cf_value", "dump_slot_history", "use_forget_dump_s", "verb_timing"):
        task[key] = False
    return task, cfg


def answer_with(d, graph, al, support, n, st, ai, config, rng_seed):
    """selcands.answer_with と同じ、門→F投影→穴埋め→答え選択。"""
    import abm.agent_runtime as ar
    import abm.sme as sme
    import v39
    from abm.domains import Abstain
    if support < ar._need(config.tau_acc, n):
        return Abstain(reason="below_tau"), False
    f_ids = {r.relation.relation_id for r in d.constituents if r.alive}
    al = replace(al, candidate_projections=tuple(x for x in al.candidate_projections if x in f_ids))
    pred = sme.project(al, graph, ai.target_graph_partial, prototype_prior_weight=0.0)
    filling = v39.fill_v39(d, ai.target_graph_partial, al.entity_mapping, al.relation_mapping, st.slot_history,
                          st.p_hat, config.fill_selection, Random(rng_seed),
                          higher_order_predicates=config.higher_order_predicates, local_lambda=config.local_lambda)
    pred, _ = v39.fill_decision(pred, filling, None)
    return pred, True


def candidate_case(pre, wt, row, argmap, scenes, config, agent):
    import abm.loop as loop
    import selectn3
    import v39
    import v310be
    import verbworld
    from abm.domains import EdgePrediction
    st, bad = sr.restore_state(pre, argmap, scenes)
    if bad:
        raise RuntimeError("候補の引数の順序を戻せない")
    if sr._strip(json.loads(loop._json_bytes(loop._canonical(st)))) != sr._strip(pre):
        raise RuntimeError("読み直しの状態が台帳と違う")
    t = row["prediction_order"]
    ai = loop._agent_input(wt, st)
    rng_seed = loop._rng_seed(agent, t)
    actual, _ = loop.predict(ai, st, config, Random(rng_seed))
    real = row.get("predicted_edge") or {}
    e = actual.prediction.edge if isinstance(actual.prediction, EdgePrediction) else None
    if (actual.trace.get("R_used") != row.get("R_used") or
            (e.predicate if e else None) != real.get("predicate") or
            (list(e.arguments) if e else []) != list(real.get("arguments") or [])):
        raise RuntimeError("読み直しの予測が台帳と違う")
    info = verbworld.INFO[wt.G_star.graph_id]
    cands = []
    shared = sys.modules.get("smeshared")
    sme_backend = bool(shared and getattr(v39.select_definition, "__module__", "") == "smeshared")
    xx = shared.self_score(shared.typed_graph(ai.target_graph_partial)) if sme_backend else None
    for d in st.definitions.values():
        n = v39.n_FH(d, st.slot_history)
        if n == 0:
            continue
        graph, al = v39.map_v39(d, st.slot_history, ai.target_graph_partial)
        if al is None:
            continue
        support = sum(v39.seat_state(d, r, st.slot_history) != "U" and r.relation.relation_id in al.relation_mapping
                      for r in d.constituents)
        if sme_backend:
            from fractions import Fraction
            dd = shared.self_score(shared.GRAPHS[al.sme_audit["left"]])
            q = 2 * Fraction(al.total_score) / (Fraction(dd) + Fraction(xx)) if dd + xx else None
        else:
            q = selectn3.n3_value(selectn3.n3_terms(d, st.slot_history, al, ai.target_graph_partial))
        if q is None:
            v39.unregister(graph)
            continue
        pred, gate = answer_with(d, graph, al, support, n, st, ai, config, rng_seed)
        e = pred.edge if isinstance(pred, EdgePrediction) else None
        name_seats = []
        for r in d.constituents:
            # 名前の席の同定は誕生時の関係IDの役割。Uで失われた名前も追える。
            if verbworld.IDS.get(r.relation.relation_id) == "name":
                cid, _ = v310be.role_target(d, r, al, ai.target_graph_partial)
                h = v39.hist_counts(st.slot_history.get((d.name, r.slot_index)))
                name_seats.append({"slot": r.slot_index, "state": v39.seat_state(d, r, st.slot_history),
                                   "predicate": r.relation.predicate if r.alive else None,
                                   "history": dict(h), "maps_to_this_verb": al.relation_mapping.get(r.relation.relation_id) == info["name_id"] or cid == info["name_id"]})
        cands.append({"R": d.name, "born": d.registered_at, "n": n, "support": support,
                      "N3": float(q), "_q": q, "gate": gate,
                      "answer": e.predicate if e else None,
                      "arguments": list(e.arguments) if e else None,
                      "correct": bool(e) and e.predicate == wt.held_out_edge.predicate and tuple(e.arguments) == tuple(wt.held_out_edge.arguments),
                      "name_seats": name_seats})
        v39.unregister(graph)
    cands.sort(key=lambda c: (-c["_q"], -c["n"], -c["born"], c["R"]))
    if sme_backend and cands:
        # 再現したSME予測のR_usedが、N3・席数・新しさの同点集合に入ることを検査する。
        first = (cands[0]["_q"], cands[0]["n"], cands[0]["born"])
        picked = next((c for c in cands if c["R"] == row.get("R_used")), None)
        if picked is None or (picked["_q"], picked["n"], picked["born"]) != first:
            raise RuntimeError("SMEの選ばれた定義が最多の同点集合に無い")
        cands.remove(picked)
        cands.insert(0, picked)
    good = [c for c in cands if c["correct"] and c["gate"]]
    selected = next((c for c in cands if c["R"] == row.get("R_used")), None)
    if selected is None or not cands or cands[0] is not selected or selected["answer"] != real.get("predicate") or selected["arguments"] != list(real.get("arguments") or []):
        raise RuntimeError("候補の一位・答え直しが台帳と違う")
    selected_states = [s["state"] for s in selected["name_seats"] if s["maps_to_this_verb"]]
    # 選ばれた定義だけでなく、当該語をF/Hで持つ定義と、名前の席の全候補も残す。
    lexical = [{"R": c["R"], "slot": s["slot"], "state": s["state"]} for c in cands for s in c["name_seats"]
               if s["predicate"] == row["verb_name"] or s["history"].get(row["verb_name"], 0) > 0]
    for c in cands:
        c.pop("_q")
    return {"trial": t, "verb": row["verb_name"], "classification": "selection_error" if good else "distinction_loss",
            "selected_name_states": selected_states or ["no_definition"], "lexical_definitions": lexical,
            "correct_candidates": [c["R"] for c in good], "candidates": cands}


def analyze_installed(task, cfg, root, cell, seed, output):
    import abm.loop as loop
    import abm.world as w
    import sweep
    import strictpc
    import verbworld
    cfgs = sr.configs_of(cfg, task)
    agent = cfg["agent_ids"][0]
    config = cfgs[agent]
    counts = defaultdict(Counter)
    exposure = defaultdict(Counter)
    all_counts = defaultdict(Counter)
    recovery = defaultdict(dict)
    events, memory = [], []
    classes, states = Counter(), Counter()
    checks = {"ledger_rows": 0, "state_hashes": 0, "world_rows": 0, "candidate_replays": 0}
    argmap, scenes = {}, {}
    output.mkdir(parents=True, exist_ok=True)
    ledger = root / "ledgers" / "cells" / cell / f"seed{seed:03d}.jsonl.gz"
    with gzip.open(ledger, "rt") as stream, gzip.open(output / "cases.jsonl.gz", "wt") as cases:
        header = json.loads(next(stream))
        world = w.generate_world(header["run_seed"], header["trial_count"], [agent], seed=sweep.load_seed(cfg["seed_file"]),
                                 holdout_include_second_order=bool(header.get("arm_holdout_second_order")))
        if world.world_hash != header["world_hash"]:
            raise RuntimeError("世界の指紋が台帳と違う")
        state = None
        for t, line in enumerate(stream):
            row = json.loads(line)
            if row["prediction_order"] != t or t >= header["trial_count"]:
                raise RuntimeError("試行の順序か本数が違う")
            wt = world.trials[t]
            if wt.held_out_edge.to_dict() != row["held_out_content"] or [r.relation_id for r in wt.target_graph_partial.relations] != row["observable_mask_edges"]:
                raise RuntimeError("世界の試行が台帳と違う")
            info = verbworld.INFO[wt.G_star.graph_id]
            if any(row[k] != info[k] for k in verbworld.EXTRA_KEYS):
                raise RuntimeError("研究者の四欄が再抽選と違う")
            pre = state
            ss = row["state_snapshot"]
            state = ss["value"] if ss["kind"] == "full" else loop._apply(state, ss["changes"])
            if hashlib.sha256(loop._json_bytes(state)).hexdigest() != row["agent_state_snapshot_hash"]:
                raise RuntimeError("台帳の状態の指紋が違う")
            checks["ledger_rows"] += 1
            checks["state_hashes"] += 1
            checks["world_rows"] += 1
            for r in wt.G_star.relations:
                argmap[r.relation_id] = tuple(r.arguments)
            scenes[wt.target_graph_partial.graph_id] = wt.target_graph_partial
            b = t // BIN
            exposure[b][row["verb_name"]] += 1
            pe = row.get("predicted_edge") or {}
            answer = pe.get("predicate")
            all_counts[b]["trials"] += 1
            all_counts[b]["answered" if answer else "abstain"] += 1
            if row["held_out_is_past"]:
                all_counts[b]["past_queries"] += 1
                all_counts[b]["past_answered" if answer else "past_abstain"] += 1
                if row["verb_class"] == "irregular":
                    key = (b, row["verb_name"])
                    count_answer(counts[key], "other_IRR" if answer == row["correct_past"] and tuple(pe.get("arguments") or ()) != tuple(wt.held_out_edge.arguments) else answer, row["correct_past"])
                    if answer == row["correct_past"] and tuple(pe.get("arguments") or ()) == tuple(wt.held_out_edge.arguments):
                        label = "correct"
                    elif answer == "REG":
                        label = "REG"
                    else:
                        label = "other"
                    evt = recovery_step(recovery[row["verb_name"]], t, label)
                    if evt:
                        events.append({"verb": row["verb_name"], "correct_before": evt[0], "REG_start": evt[1], "correct_after": evt[2]})
                    if label == "REG":
                        if pre is None:
                            raise RuntimeError("REG回答に予測前状態が無い")
                        case = candidate_case(pre, wt, row, argmap, scenes, config, agent)
                        cases.write(json.dumps(case, ensure_ascii=False) + "\n")
                        classes[case["classification"]] += 1
                        states["+".join(case["selected_name_states"])] += 1
                        checks["candidate_replays"] += 1
            if (t + 1) % 100 == 0 or t == header["trial_count"] - 1:
                seat_counts = Counter()
                hist = state["slot_history"]
                for d in state["definitions"].values():
                    for r in d["constituents"]:
                        seat_counts["F" if r["alive"] else "H" if str((d["name"], r["slot_index"])) in hist else "U"] += 1
                memory.append({"t": t + 1, "definitions": len(state["definitions"]), "F": seat_counts["F"], "H": seat_counts["H"], "U": seat_counts["U"]})
            strictpc.record_kinds(wt.target_graph_partial, (wt.held_out_edge,) if row.get("f_fired") else ())
            sr._clear_caches(loop)
        if checks["ledger_rows"] != header["trial_count"]:
            raise RuntimeError("台帳が完走していない")
    novel = defaultdict(Counter)
    memory_bits = {}
    probes = root / "side" / cell / f"seed{seed:03d}.probe.jsonl"
    with probes.open() as stream:
        for line in stream:
            rec = json.loads(line)
            memory_bits[rec["t"]] = rec["C"]
            if rec.get("verb_class") != "novel":
                continue
            if rec.get("truth") is not None or rec.get("exp_path_n") or rec.get("verbatim_n"):
                raise RuntimeError("新語の試験に学習か採点の値がある")
            a = rec.get("answer")
            k = "abstain" if a is None else "REG" if a == "REG" else "IRR" if a.startswith("IRR_") else "other"
            novel[(rec["t"], rec["verb_name"])][k] += 1
            if a and a.startswith("IRR_"):
                novel[(rec["t"], rec["verb_name"])][a] += 1
    for m in memory:
        m["bits"] = memory_bits.get(m["t"])
    rows = []
    for b in range((header["trial_count"] + BIN - 1) // BIN):
        for k in range(33, 41):
            name = f"V{k:02d}"
            rows.append({"bin": b, "start": b * BIN, "end": min((b + 1) * BIN, header["trial_count"]),
                         "verb": name, "exposure": exposure[b][name], **rates(counts[(b, name)])})
    result = {"seed": seed, "cell": cell, "world_hash": header["world_hash"], "checks": checks,
              "overregularization": rows, "recovery": events, "classification": dict(classes), "selected_name_states": dict(states),
              "answering": [{"bin": b, **dict(c)} for b, c in sorted(all_counts.items())], "memory": memory,
              "novel": [{"t": t, "verb": v, **dict(c)} for (t, v), c in sorted(novel.items())]}
    (output / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {"cell": cell, "seed": seed, "analysis_checks": checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("seed", type=int, choices=range(1, 21))
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    ledgers = list((args.root / "ledgers" / "cells").glob(f"*/seed{args.seed:03d}.jsonl.gz"))
    if len(ledgers) != 1:
        raise SystemExit("一本の台帳を明示すること")
    cell = ledgers[0].parent.name
    import sweep
    import v3_run
    with tempfile.TemporaryDirectory(prefix="verb_replay_", dir=args.output.parent) as tmp:
        task, cfg = make_task(args.root, cell, args.seed, Path(tmp))
        sweep.run_one = lambda tk: analyze_installed(tk, cfg, args.root, cell, args.seed, args.output)
        rec = v3_run.worker(task)
        print(json.dumps(rec["analysis_checks"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
