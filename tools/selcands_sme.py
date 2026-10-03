"""保存したSME状態の再生中に、採用済みの対応で候補の答えを後づけで調べる。

使い方：python3.12 tools/selcands_sme.py <元のcommand.json> <出力先> <状態記録.gz>
旧いselcandsの恒等自己点と照合し直しを使わず、共有結果のSESと自己点を読む。
正解は予測後の記録でだけ突き合わせる。模型・経験・保存形式は変更しない。
"""
from dataclasses import replace
from pathlib import Path
from random import Random
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]
import smereplay

_REAL_INSTALL = smereplay.install


def install(path, *, replay=None):
    _REAL_INSTALL(path, replay=replay)
    if replay is None:
        raise ValueError("候補の再解析は保存状態の再生にだけ使う")
    import abm.agent_runtime as ar
    import abm.loop as loop
    import abm.sme as sme
    from abm.domains import Abstain, EdgePrediction
    import probeworld
    import smeshared
    import v39
    import v310be
    actual_select = v39.select_definition
    selection = {"last": None}
    pending_rows = {}
    stream = smeshared._text_gzip(Path(path).with_name(Path(path).name.replace(".sme.states.", ".sme.candidates.")))
    legacy_checks = {"reference_calls": 0, "main_legacy_calls": 0}
    previous_profile = sys.getprofile()
    if os.environ.get("SME_CHECK_LEGACY") == "1":
        def profile(frame, event, arg):
            if event != "call" or frame.f_code.co_name != "map_graphs" or frame.f_globals.get("__name__") == "smeshared":
                return
            filename = Path(frame.f_code.co_filename)
            if ROOT not in filename.parents:
                return
            parent = frame.f_back
            while parent is not None:
                if parent.f_globals.get("__name__") == "smeshared" and parent.f_code.co_name == "map_graphs":
                    legacy_checks["reference_calls"] += 1
                    return
                parent = parent.f_back
            legacy_checks["main_legacy_calls"] += 1
            raise RuntimeError("SME再解析：参考の採点以外で旧い照合器が呼ばれた")
        sys.setprofile(profile)

    def capture_selection(*a, **k):
        choice = actual_select(*a, **k)
        selection["last"] = choice
        return choice

    v39.select_definition = capture_selection
    real_predict = loop.predict

    def prediction_key(p):
        return p.edge.to_dict() if isinstance(p, EdgePrediction) else {"abstain_reason": p.reason}

    def predict(ai, state, config, rng):
        before_rng = rng.getstate()
        selection["last"] = None
        output, pending = real_predict(ai, state, config, rng)
        after_rng = rng.getstate()
        # Cの答え直しは本番の試行として記録しない。
        if any(f.function in ("variants_correct", "_measure", "_probe")
               and f.frame.f_globals.get("__name__") in ("cflearn", "cfvalue", "probeworld")
               for f in __import__("inspect").stack()):
            return output, pending
        actual = selection["last"]
        trial = smereplay.ST["trial"]
        scene = ai.target_graph_partial
        memory_before = smereplay.encode(state)
        snap = probeworld._snapshot_modules()
        extras = []
        for name in ("v39", "ustruct", "strictpc", "useforget"):
            mod = sys.modules.get(name)
            for attr in ("REG", "UREG", "RELPOS", "KINDS", "_POW", "STATS", "CTX"):
                val = getattr(mod, attr, None)
                if isinstance(val, dict):
                    extras.append((val, dict(val)))
        rows = []
        try:
            xx = smeshared.self_score(smeshared.typed_graph(scene))
            for d in state.definitions.values():
                n = v39.n_FH(d, state.slot_history)
                if not n:
                    continue
                graph, alignment = v39.map_v39(d, state.slot_history, scene)
                dd = smeshared.self_score(smeshared.GRAPHS[alignment.sme_audit["left"]])
                support = sum(v39.seat_state(d, row, state.slot_history) != "U"
                              and row.relation.relation_id in alignment.relation_mapping for row in d.constituents)
                fids = {r.relation.relation_id for r in d.constituents if r.alive}
                alignment = replace(alignment, candidate_projections=tuple(x for x in alignment.candidate_projections if x in fids))
                fixed = (support / n, support, d, graph, alignment, n, False, ())
                v39.select_definition = lambda *a, _fixed=fixed, **k: _fixed
                candidate_rng = Random()
                candidate_rng.setstate(before_rng)
                candidate_output, _ = v39.predict(ai, state, config, candidate_rng)
                selected = actual is not None and actual[2].name == d.name
                if selected and prediction_key(candidate_output.prediction) != prediction_key(output.prediction):
                    raise RuntimeError(f"候補の再解析：試行{trial}の選ばれた定義の答えが本物と違う")
                visible = {r.relation_id for r in scene.relations}
                fh = [r for r in d.constituents if v39.seat_state(d, r, state.slot_history) != "U"]
                e = candidate_output.prediction.edge if isinstance(candidate_output.prediction, EdgePrediction) else None
                lengths = v39.code_lengths(state.p_hat)
                rewrite_bits, rewrite_parts = v310be.rewrite(state, d.name, scene, lengths, config, visible)
                slots = []
                vis_by_id = {r.relation_id: r for r in scene.relations}
                for r in d.constituents:
                    rid = r.relation.relation_id
                    destination, reason = v310be.role_target(d, r, alignment, scene)
                    mapped = alignment.relation_mapping.get(rid)
                    slots.append({"slot": r.slot_index, "state": v39.seat_state(d, r, state.slot_history),
                                  "fixed_name": r.relation.predicate if r.alive else None,
                                  "history": v39.hist_counts(state.slot_history.get((d.name, r.slot_index))),
                                  "mapped_to": mapped, "mapped_visible": mapped in visible,
                                  "mapped_name": vis_by_id[mapped].predicate if mapped in visible else None,
                                  "role_destination": destination, "role_reason": reason})
                rows.append({"R": d.name, "born_trial": d.registered_at, "selected": selected,
                             "version": alignment.sme_audit["version"], "result_id": alignment.sme_result_id,
                             "entity_mapping": dict(alignment.entity_mapping), "relation_mapping": dict(alignment.relation_mapping),
                             "score_breakdown": dict(alignment.score_breakdown),
                             "old_score_on_new_alignment": alignment.sme_audit["old_on_new"],
                             "old_matcher_selected_score": alignment.sme_audit["old_selected_score"],
                             "S_dx": alignment.total_score, "S_dd": dd, "S_xx": xx,
                             "N3": 2 * alignment.total_score / (dd + xx) if dd + xx else None,
                             "support": support, "denominator": n, "gate_passed": support >= ar._need(config.tau_acc, n),
                             "mapped_visible_FH": sum(r.relation.relation_id in alignment.relation_mapping and alignment.relation_mapping[r.relation.relation_id] in visible for r in fh),
                             "mapped_unknown_FH": sum(r.relation.relation_id in alignment.relation_mapping and alignment.relation_mapping[r.relation.relation_id] not in visible for r in fh),
                             "F": sum(r.alive for r in d.constituents), "H": sum(v39.seat_state(d, r, state.slot_history) == "H" for r in d.constituents),
                             "U": sum(v39.seat_state(d, r, state.slot_history) == "U" for r in d.constituents),
                             "prediction": e.to_dict() if e is not None else None,
                             "abstain_reason": candidate_output.prediction.reason if e is None else None,
                             "rewrite_bits": rewrite_bits, "rewrite_parts": rewrite_parts, "slots": slots})
        finally:
            v39.select_definition = capture_selection
            probeworld._restore_modules(snap)
            for current, saved in extras:
                current.clear()
                current.update(saved)
        if smereplay.encode(state) != memory_before or rng.getstate() != after_rng:
            raise RuntimeError(f"候補の再解析：試行{trial}の記憶か乱数を変えた")
        pending_rows[trial] = {"trial": trial, "chosen_R": actual[2].name if actual is not None else None,
                               "prediction": prediction_key(output.prediction), "candidates": rows}
        return output, pending

    loop.predict = predict
    real_record = loop._ledger_record

    def record(agent_id, trial, config, output, score, coin, state, *a, **k):
        row = pending_rows.pop(trial.trial)
        # 本人への入力には使わない。予測確定後の研究者用の判定。
        held = trial.held_out_edge
        for c in row["candidates"]:
            p = c["prediction"]
            c["hit"] = p is not None and p["predicate"] == held.predicate and tuple(p["arguments"]) == tuple(held.arguments)
        row["any_correct"] = any(c["hit"] for c in row["candidates"])
        row["correct_gate_passed"] = any(c["hit"] and c["gate_passed"] for c in row["candidates"])
        row["original_hit"] = bool(score.hit)
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        result = real_record(agent_id, trial, config, output, score, coin, state, *a, **k)
        return result

    loop._ledger_record = record
    real_close = smereplay.close

    def close():
        stream.close()
        sys.setprofile(previous_profile)
        if os.environ.get("SME_CHECK_LEGACY") == "1":
            Path(path).with_name(Path(path).name.replace(".sme.states.jsonl.gz", ".sme.analysis-check.json")).write_text(
                json.dumps(legacy_checks, ensure_ascii=False, indent=2) + "\n")
        return real_close()

    smereplay.close = close


# spawnされた一台帳用の子でも、同じ再解析の入口を登録する。
smereplay.install = install


def main():
    import v3_run
    if "--check-legacy" in sys.argv:
        sys.argv.remove("--check-legacy")
        os.environ["SME_CHECK_LEGACY"] = "1"
    command_file, output, states = sys.argv[1:]
    command = json.loads(Path(command_file).read_text())
    command[3] = str(Path(output).resolve())
    if "--sme-replay" in command:
        command[command.index("--sme-replay") + 1] = str(Path(states).resolve())
    else:
        command += ["--sme-replay", str(Path(states).resolve())]
    if Path(output).exists():
        raise SystemExit("再解析の出力先は新しい場所にする")
    sys.argv = command[1:]
    v3_run.main()


if __name__ == "__main__":
    main()
