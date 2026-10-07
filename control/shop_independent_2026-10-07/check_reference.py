"""Independent small-graph checks. No new production code is imported/read."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import resource
import time

from reference import (Candidate, Definition, FrozenState, Seat, attention_gradient,
                       average_distributions, birth_values, distribution, fixed_mapping_score,
                       fresh_candidate, load_ordinary, loss, marginal_values, mismatch,
                       provisional_definition, select, self_structure_score, update_attention,
                       expected_match)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ordinary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    started = time.monotonic()
    sme = load_ordinary(args.ordinary)
    checks, data = [], {}

    def check(label, condition, details=None):
        checks.append({"check": label, "passed": bool(condition), "details": details})
        if not condition:
            raise AssertionError(label)

    def close(a, b):
        return math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)

    def graph():
        return sme.Graph((sme.Node("d", "entity"), sme.Node("s", "entity"),
            sme.Node("seal", "relation", frozenset({"sig_e"}), ("d",)),
            sme.Node("at", "relation", frozenset({"at"}), ("d", "s")),
            sme.Node("open", "relation", frozenset({"open"}), ("d",)),
            sme.Node("top", "relation", frozenset({"implies"}), ("at", "open")),
            sme.Node("link", "relation", frozenset({"attach"}), ("seal", "top"))))

    toy = graph()
    mapping = {n.key: n.key for n in toy.nodes}
    q = {n.key: 1.0 for n in toy.nodes if n.kind != "entity"}
    toy_rows = []
    for p, expected in zip((0., .1, .5, .9, 1.), (.1175, .2052, .5560, .9068, .9945)):
        value, cases = fixed_mapping_score(sme, toy, toy, mapping, {**q, "seal": p}, details=True)
        check(f"commission41_toy_p{p}", close(value, expected) and close(sum(c["weight"] for c in cases), 1))
        toy_rows.append({"p": p, "reference": value, "hand": expected, "cases": cases})
    data["commission41_toy"] = toy_rows
    for state, names in (("F", frozenset({"sig_e"})), ("H", frozenset({"other"})), ("U", frozenset())):
        other = sme.Graph(tuple(replace(n, state=state, names=names) if n.key == "seal" else n for n in toy.nodes))
        check(f"fixed_self_T_{state}", close(self_structure_score(sme, other), .9945))

    hidden = sme.Graph(tuple(sme.Node(n.key, "unknown", args=None) if n.key == "seal" else n for n in toy.nodes))
    hidden_q = {key: p for key, p in q.items() if key != "seal"}
    hidden_score = fixed_mapping_score(sme, toy, hidden, mapping, hidden_q)
    check("hidden_local_zero", close(hidden_score, self_structure_score(sme, hidden)))
    check("hidden_is_marginalized_not_guessed", hidden_score > .1175 and hidden_score < .9945)

    shared = sme.Graph((sme.Node("e", "entity"),
        sme.Node("child", "relation", frozenset({"child"}), ("e",)),
        sme.Node("parent1", "relation", frozenset({"p1"}), ("child",)),
        sme.Node("parent2", "relation", frozenset({"p2"}), ("child",))))
    shared_value = fixed_mapping_score(sme, shared, shared, {n.key: n.key for n in shared.nodes},
                                      {"child": .3, "parent1": 1, "parent2": 1})
    check("shared_child_drawn_once", close(shared_value, .3*.0775))
    data["shared_child"] = {"score": shared_value, "hand": .3*.0775, "incorrect_squared_probability": .3*.3*.0775}

    competing = Definition("competing", (Seat("e", "entity", ()),
        Seat("r", "relation", ("e",), "U", background=distribution({"a": .5, "b": .5}))), frozenset())
    competing_scene = sme.Graph((sme.Node("e", "entity"),
                                 sme.Node("ra", "relation", frozenset({"a"}), ("e",)),
                                 sme.Node("rb", "relation", frozenset({"b"}), ("e",))))
    competing_result, competing_engine = expected_match(sme, competing, competing_scene)
    check("competing_MHs_share_one_categorical_seat_draw", close(math.fsum(competing_engine.initial.values()), .0045))
    check("U_match_gets_normal_name_local", close(competing_result.best.score, .00225))
    data["competing_MHs"] = {"correct_initial_sum": math.fsum(competing_engine.initial.values()),
                              "wrong_independent_MH_Bernoulli_sum": .0035}

    # Different integration route: literal F name assignments are sent through
    # ordinary _grow and ordinary _scores. No reference pruning routine is used.
    rng = random.Random(20261007)
    random_rows = []
    for trial in range(220):
        nodes = [sme.Node("e0", "entity"), sme.Node("e1", "entity")]
        for i in range(rng.randrange(1, 6)):
            prior = [n.key for n in nodes]
            arity = rng.randrange(1, 3)
            argkeys = tuple(rng.choice(prior) for _ in range(arity))
            nodes.append(sme.Node(f"r{i}", "relation", frozenset({f"name{i}"}), argkeys))
        g = sme.Graph(tuple(nodes))
        rels = [n for n in nodes if n.kind != "entity"]
        probabilities = {n.key: rng.choice((0., .1, .5, .9, 1.)) for n in rels}
        ref = fixed_mapping_score(sme, g, g, {n.key: n.key for n in nodes}, probabilities)
        pieces = []
        for bits in itertools.product((False, True), repeat=len(rels)):
            weight = math.prod(probabilities[n.key] if bit else 1-probabilities[n.key] for n, bit in zip(rels, bits))
            if not weight:
                continue
            bit_by_key = {n.key: bit for n, bit in zip(rels, bits)}
            literal = sme.Graph(tuple(replace(n, names=frozenset({"UNMATCHED"}))
                                     if n.kind != "entity" and not bit_by_key[n.key] else n for n in nodes))
            engine = sme._Engine(literal, g, sme.Settings(), random.Random(0))
            members = set()
            for n in nodes:
                for index in engine._grow(n.key, n.key, True):
                    members.update(engine.closures[index])
            ordinary = math.fsum(engine._scores(frozenset(members), True).values())
            pieces.append(weight*ordinary)
        literal_mean = math.fsum(pieces)
        check(f"literal_names_random_{trial}", close(ref, literal_mean))
        random_rows.append({"example": trial, "seats": len(rels), "enumeration": ref,
                            "literal_name_mean": literal_mean, "absolute_difference": abs(ref-literal_mean)})
    data["random_fixed_mappings"] = random_rows

    cap = sme.Settings(max_local_score=.001)
    cap_ref = fixed_mapping_score(sme, shared, shared, {n.key: n.key for n in shared.nodes},
                                 {"child": .3, "parent1": 1, "parent2": 1}, settings=cap)
    cap_full = self_structure_score(sme, shared, settings=cap)
    check("cap_applied_inside_each_case", close(cap_ref, .3*cap_full))
    check("U_m_zero", close(mismatch("n", {"n": .1, "e": .9}, {"n": .1, "e": .9}), 0))
    check("F_mismatch_m_one", close(mismatch("n", {"n": .001, "e": .999}, {"n": .1, "e": .9}), 1))
    check("F_fit_negative_m_kept", mismatch("n", {"n": .991, "e": .009}, {"n": .1, "e": .9}) < 0)
    try:
        mismatch("n", {"n": 0., "e": 1.}, {"n": .1, "e": .9})
    except ValueError:
        zero_rejected = True
    else:
        zero_rejected = False
    check("undefined_m_zero_probability_not_silently_patched", zero_rejected)

    p1, p2 = distribution({"y": .9, "n": .1}), distribution({"y": .1, "n": .9})
    candidates = (Candidate("A", .8, True, p1, (("j1", "shared", .3), ("j2", "shared", .4)), "y", "one_seat"),
                  Candidate("B", .6, True, p2, (("j1", "shared", 1.), ("j2", "shared", 0.)), "n", "one_seat"))
    prediction = select(candidates, {"shared": .5}, {"y": .5, "n": .5})
    check("duplicate_position_keys_add", close(dict(prediction.logits)["A"], math.log(.8)-.5*(.3+.4)))
    check("a_zero_argmax_Q", select(candidates, {}, {"y": .5, "n": .5}).selected == "A")
    shifted = tuple(replace(c, positions=tuple((rid, key, m+.2) for rid, key, m in c.positions)) for c in candidates)
    shifted_pred = select(shifted, {"shared": .5}, {"y": .5, "n": .5})
    check("common_baseline_term_cancels", close(dict(prediction.logits)["A"]-dict(prediction.logits)["B"],
                                               dict(shifted_pred.logits)["A"]-dict(shifted_pred.logits)["B"]))
    gradient = attention_gradient(prediction, "y")["shared"]
    h = 1e-6
    lp = -math.log(dict(select(candidates, {"shared": .5+h}, {"y": .5, "n": .5}).mixture)["y"])
    lm = -math.log(dict(select(candidates, {"shared": .5-h}, {"y": .5, "n": .5}).mixture)["y"])
    finite = (lp-lm)/(2*h)
    check("natural_log_attention_gradient", math.isclose(gradient, finite, abs_tol=1e-9))
    check("undisclosed_attention_unchanged", update_attention({"shared": .5}, {"shared": 1}, disclosed=False) == {"shared": .5})
    check("attention_projected_0_10", update_attention({"x": 0, "y": 10}, {"x": 1, "y": -1}, disclosed=True) == {"x": 0., "y": 10.})
    no_q = select(tuple(replace(c, q=0) for c in candidates), {}, {"y": .5, "n": .5})
    check("all_Q_zero_background_no_softmax", no_q.selected is None and dict(no_q.distribution)["y"] == .5)
    ell = lambda name: 9.0
    check("zero_P_existing_escape_code", loss(replace(prediction, distribution=(("y", 0.), ("n", 1.))), "y", ell) == 9.)
    check("alpha_abstention_cost", loss(replace(prediction, utterance=None), "y", ell, arm="alpha") == 9.)
    mixed = average_distributions([{"y": .9, "n": .1}, {"y": .3, "n": .7}])
    check("multiple_target_seats_equal_distribution_mix", close(mixed["y"], .6))
    top_before = select((replace(candidates[0], answer=distribution({"y": .99, "n": .01})),), {}, {"y": .5, "n": .5})
    top_after = select((replace(candidates[0], answer=distribution({"y": .51, "n": .49})),), {}, {"y": .5, "n": .5})
    check("one_candidate_log_P_changes_even_same_utterance", loss(top_after, "y", ell)-loss(top_before, "y", ell) > .9)
    data["attention"] = {"analytic_gradient": gradient, "finite_difference": finite,
                         "bits_per_nat": 1/math.log(2), "m_F_fit": mismatch("n", {"n": .991, "e": .009}, {"n": .1, "e": .9})}

    b = distribution({"normal": .25, "exception": .25, "yes": .25, "no": .25})
    bjoin = distribution({"join": 1.})
    def make_definition(key, cue_state, history, answer):
        return Definition(key, (Seat("e", "entity", ()),
            Seat("cue", "relation", ("e",), cue_state, "normal" if cue_state == "F" else None, history, b),
            Seat("answer", "relation", ("e",), "F", answer, ((answer, 1.),), b),
            Seat("parent", "relation", ("cue", "answer"), "F", "join", (("join", 1.),), bjoin)),
            frozenset({"cue", "answer", "parent"}))
    A = make_definition("A", "F", (("normal", 1.),), "no")
    B = make_definition("B", "H", (("normal", 9.),), "yes")
    complete = sme.Graph((sme.Node("e", "entity"),
                         sme.Node("cue", "relation", frozenset({"exception"}), ("e",)),
                         sme.Node("answer", "relation", frozenset({"yes"}), ("e",)),
                         sme.Node("parent", "relation", frozenset({"join"}), ("cue", "answer"))))
    def question(rid):
        # All entities here remain reachable from other visible relations.
        public = sme.Graph(tuple(sme.Node(n.key, "unknown", args=None) if n.key == rid else n for n in complete.nodes))
        positions = {n.key: ("shared_cue" if n.key != "parent" else "shared_parent", bjoin if n.key == "parent" else b)
                     for n in public.nodes if n.kind not in {"entity", "unknown"}}
        return public, rid, positions
    state = FrozenState((A, B), (("shared_cue", .0), ("shared_parent", .0)), b, 100, (("A", 2), ("B", 3)), 7)
    calls = []
    def predictor(snapshot, public_question):
        scene, target, positions = public_question
        cs = []
        for definition in snapshot.memory:
            candidate, result = fresh_candidate(sme, definition, scene, target, positions, dict(snapshot.global_background),
                                                tie_seed=snapshot.tie_seed, threshold=0., empty_gate_ratio=1.)
            calls.append((definition.key, tuple(s.state for s in definition.seats), target))
            cs.append(candidate)
        return select(cs, dict(snapshot.attention), dict(snapshot.global_background))
    state_before = repr(state)
    rows = marginal_values(state, question("answer"), "yes", predictor, ell)
    by_seat = {(r["definition"], r["seat"]): r for r in rows}
    check("full_rerun_all_candidates_each_intervention", len(calls) == (1+len(rows))*len(state.memory))
    signal = by_seat["A", "cue"]
    check("unselected_seat_can_change_final_choice", signal["before_selected"] == "B" and signal["after_selected"] == "A")
    check("unselected_seat_has_positive_delta", signal["delta"] > 1)
    check("counterfactual_snapshot_unchanged", repr(state) == state_before)
    chosen_rows = marginal_values(state, question("answer"), "yes", predictor, ell, scope="chosen")
    check("chosen_restricts_seats_not_reranking", all(r["definition"] == "B" for r in chosen_rows)
          and all(close(r["delta"], by_seat[r["definition"], r["seat"]]["delta"]) for r in chosen_rows))
    alpha_rows = marginal_values(state, question("answer"), "yes", predictor, ell, arm="alpha")
    check("alpha_final_answer_loss", next(r for r in alpha_rows if r["definition"] == "A" and r["seat"] == "cue")["delta"] == 9)
    reverse_rows = marginal_values(state, question("answer"), "no", predictor, ell)
    check("negative_delta_not_clipped_even_lambda_zero", next(r for r in reverse_rows if r["definition"] == "A" and r["seat"] == "cue")["delta"] < 0)
    # q>0 is not exact-name support. A has no support at the visible cue.
    outside = replace(A, gate_eligible=frozenset({"cue"}))
    cand, _ = fresh_candidate(sme, outside, *question("answer")[:2], question("answer")[2], dict(b), threshold=.4, empty_gate_ratio=1.)
    opened, _ = fresh_candidate(sme, replace(outside, seats=tuple(replace(s, state="U") if s.key == "cue" else s for s in outside.seats)),
                                *question("answer")[:2], question("answer")[2], dict(b), threshold=.4, empty_gate_ratio=1.)
    check("positive_Cstar_q_not_gate_support", cand.q > 0 and not cand.gate)
    check("gate_recomputed_when_U_leaves_denominator", opened.gate)
    original_cue_m = dict((rid, m) for rid, _, m in cand.positions)["cue"]
    thinned_cand, _ = fresh_candidate(sme, outside.thin("cue"), *question("answer")[:2],
                                      question("answer")[2], dict(b), threshold=.4, empty_gate_ratio=1.)
    thinned_cue_m = dict((rid, m) for rid, _, m in thinned_cand.positions)["cue"]
    check("counterfactual_recomputes_attention_m", close(original_cue_m, 1.) and thinned_cue_m < original_cue_m)
    data["full_stage2"] = {"top1_rows": rows, "alpha_rows": alpha_rows,
                           "negative_example": next(r for r in reverse_rows if r["definition"] == "A" and r["seat"] == "cue"),
                           "gate_fixture_empty_ratio": 1., "warning": "fixture gate/tie/target adapter; actual learner policies still require record audit"}

    template = replace(A, key="new")
    first = {"cue": "normal", "answer": "no", "parent": "join"}
    provisional = provisional_definition(template, first)
    check("birth_names_from_first_only", provisional.seats[1].fixed == "normal" and provisional.seats[2].fixed == "no")
    unknown_first = provisional_definition(template, {"parent": "join"})
    check("unrevealed_first_F_returns_background", unknown_first.seats[1].probabilities() == dict(b))
    second = (("cue", "exception"), ("answer", "yes"), ("parent", "join"))
    birth = birth_values(replace(state, memory=(B,)), template, first, second, question, predictor, ell,
                         {"door": 3, "non_door": 1}, {"yes"}, decay_weight=.5)
    weights = {r["visible_relation"]: r["weight"] for r in birth["questions"]}
    check("birth_learner_type_frequency_split", weights == {"cue": .125, "answer": .75, "parent": .125})
    check("birth_hides_only_visible_relations", {r["visible_relation"] for r in birth["questions"]} == {rid for rid, _ in second})
    uniform = birth_values(replace(state, memory=(B,)), template, first, second, question, predictor, ell, {}, set())
    check("birth_no_question_history_uniform", all(close(r["weight"], 1/3) for r in uniform["questions"]))
    check("birth_reference_values_not_A_initial_copy", set(birth["values"]) == {"cue", "answer", "parent"})
    data["birth"] = birth

    # Exact name/ID equivariance in a case with a unique definition selection.
    renames = {"normal": "v4", "exception": "v1", "yes": "v9", "no": "v0", "join": "v7"}
    idnames = {"e": "o9", "cue": "o2", "answer": "o1", "parent": "o8", "A": "d9", "B": "d1"}
    def renamed_distribution(p):
        return tuple((renames[n], v) for n, v in p)
    def renamed_definition(d):
        return replace(d, key=idnames[d.key], gate_eligible=frozenset(idnames[k] for k in d.gate_eligible),
                       seats=tuple(replace(s, key=idnames[s.key], args=None if s.args is None else tuple(idnames[a] for a in s.args),
                                           fixed=renames.get(s.fixed), counts=renamed_distribution(s.counts),
                                           background=renamed_distribution(s.background)) for s in d.seats))
    qscene, qtarget, qpositions = question("answer")
    rscene = sme.Graph(tuple(replace(n, key=idnames[n.key], names=frozenset(renames[nm] for nm in n.names),
                                    args=None if n.args is None else tuple(idnames[a] for a in n.args)) for n in qscene.nodes))
    rpositions = {idnames[k]: (key, renamed_distribution(base)) for k, (key, base) in qpositions.items()}
    original = predictor(state, question("answer"))
    transformed = predictor(replace(state, memory=tuple(renamed_definition(d) for d in state.memory),
                                    global_background=renamed_distribution(state.global_background)),
                            (rscene, idnames[qtarget], rpositions))
    check("reference_name_ID_equivariance_unique_choice", transformed.selected == idnames[original.selected]
          and transformed.utterance == renames[original.utterance]
          and all(close(dict(transformed.distribution)[renames[n]], p) for n, p in original.distribution))

    # Exercise the eventual sampling/difference-table wrapper with explicitly
    # synthetic rows. This is not a real-run comparison or a model gate.
    from compare_records import compare
    synth = Path(args.output).parent/"synthetic_comparison"
    synth.mkdir(parents=True, exist_ok=True)
    actual_path, replay_path = synth/"actual.jsonl", synth/"reference.jsonl"
    with open(actual_path, "w") as actual_handle, open(replay_path, "w") as replay_handle:
        for config in range(9):
            for trial in range(55):
                row = {"configuration": f"synthetic_{config}", "trial_key": f"1:{trial}", "world_seed": 1,
                       "values": {"delta": .75 if config == 0 else .5, "selected": "A"}}
                actual_handle.write(json.dumps(row)+"\n")
                replay_handle.write(json.dumps({**row, "values": {"delta": .5, "selected": "A"}})+"\n")
    compared = compare(actual_path, replay_path, synth/"tables")
    check("comparison_50_random_trials_each_9_configs", compared["different_values"] == 50
          and all(len(values) == 50 for values in compared["selected_trials"].values()))
    try:
        compare(actual_path, replay_path, synth/"too_small", sample_size=49)
    except ValueError:
        insufficient_rejected = True
    else:
        insufficient_rejected = False
    check("comparison_rejects_less_than_50", insufficient_rejected)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {"scope": "reference self-checks; not production gate or real-run comparison", "checks": checks,
              "passed": len(checks), "failed": sum(not c["passed"] for c in checks), "data": data,
              "ordinary_path": str(Path(args.ordinary).resolve()),
              "ordinary_sha256": hashlib.sha256(Path(args.ordinary).read_bytes()).hexdigest(),
              "elapsed_seconds": time.monotonic()-started, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("passed", "failed", "elapsed_seconds", "peak_rss_bytes")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
