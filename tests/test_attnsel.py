"""注意の選択・段①。手例と旧 N3 の小例だけ。元の走行は読まない。"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from random import Random
import sys
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests"), str(ROOT)]
import attnsel as A
import attnsel_checks as C
import selectn3 as N
import test_selectn3 as OLD
import test_v39_budget as T
import v39
from abm.domains import Abstain, AgentOutput, EdgePrediction, Relation, RelationGraph, Prototype, VerbatimTrace


@pytest.fixture(autouse=True)
def setup():
    T.setup()
    with C.matching():
        yield


def prepared(learner=None, *, trial=1, extra_unknown=True, config=None, state=None, rng=None):
    st, ai, cfg, truth = C.example(extra_unknown=extra_unknown)
    learner = learner or A.Attention(enabled=True, seen=C.SEEN)
    pre = learner.prepare("agent", trial, ai, state or st, config or cfg, rng or Random(1))
    return learner, pre, st, ai, cfg, truth


def test_01_unit_weights_match_N3_selection_and_answer():
    for extra in (False, True):
        st, ai, cfg, truth = C.example(extra_unknown=extra)
        for c in A.candidates(st, ai.target_graph_partial):
            old = N.n3_value(N.n3_terms(c.definition, st.slot_history, c.alignment, ai.target_graph_partial))
            assert c.terms.value({p: 1.0 for p in C.SEEN}) == old
        before_rng, attn_rng = Random(1), Random(1)
        old, _old_pending = v39.predict(ai, st, cfg, before_rng)
        learner = A.Attention(enabled=True, eta=0, seen=C.SEEN)
        pre = learner.prepare("agent", 1, ai, st, cfg, attn_rng)
        assert pre.output == old
        assert attn_rng.getstate() == before_rng.getstate()
        learner.finish(pre, C.feedback(1, truth))
        assert set(learner.weights.values()) == {1.0}


def fixture_files(root, *, attention=None, record_only=False):
    """既存の台帳の行の生成器と選択 side の記録器を使う。記憶の学習なし。"""
    import abm.loop as loop
    root.mkdir()
    st, ai, cfg, truth = C.example(extra_unknown=True)
    before = loop._json_bytes(loop._canonical(st))
    old_select, old_predict, old_ai = v39.select_definition, loop.predict, loop._agent_input
    old_log = dict(N.LOG)
    rng = Random(1)
    loop.predict = v39.predict
    N.install_log(root / "seed001.select.jsonl.gz")
    states = []
    try:
        with (root / "seed001.jsonl").open("w", encoding="utf-8") as ledger, (root / "seed001.side.jsonl").open("w", encoding="utf-8") as side:
            for t in (1, 2):
                N.LOG["t"] = t
                if attention is None:
                    output, pending = loop.predict(ai, st, cfg, rng)
                else:
                    pre = attention.prepare("agent", t, ai, st, cfg, rng, record_only=record_only, predictor=loop.predict)
                    output, pending = pre.output, pre.pending
                    # 非開示なので、この控えから正解の値は使わない。
                    attention.finish(pre, C.feedback(t, truth, disclosed=False))
                coin = NS(coin_t=0.75, f_realized=0.5, f_fired=False)
                score = NS(hit=int(A.answer_key(output.prediction) == (truth.predicate, truth.arguments)),
                           outcome_category="correct" if A.answer_key(output.prediction) == (truth.predicate, truth.arguments) else "incorrect")
                trial = NS(trial=t, G_star=ai.base_graph, target_graph_partial=ai.target_graph_partial, held_out_edge=truth)
                accounting = dict(pending_claims_open=0, pending_claims_new=0, pending_claims_confirmed=0,
                                  pending_merit_awarded=0, exception_bits_charged=0, constituent_reason_123=[], charge_source=None, type2_fired=False)
                rec, _snapshot, _hash = loop._ledger_record("agent", trial, cfg, output, score, coin, st, None, (),
                                                         "hand_example", None, accounting, "full", None, None, True, [])
                ledger.write(json.dumps({"record_type": "trial", **rec}, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
                side.write(json.dumps({"trial": t, "output": loop._canonical(output), "state": loop._canonical(st)}, sort_keys=True) + "\n")
                states.append(rng.getstate())
    finally:
        N.close()
        N.LOG.clear(); N.LOG.update(old_log)
        v39.select_definition, loop.predict, loop._agent_input = old_select, old_predict, old_ai
    assert loop._json_bytes(loop._canonical(st)) == before
    return {p.name: p.read_bytes() for p in root.iterdir()}, states


def test_02_flag_off_ledger_and_all_generated_side_bytes_identical(tmp_path, monkeypatch):
    # gzip の時刻を同じにし、内容だけでなく圧縮ファイル本体も比較する。
    monkeypatch.setattr(gzip.time, "time", lambda: 1791000000)
    baseline, rng1 = fixture_files(tmp_path / "baseline")
    disabled = A.Attention(enabled=False, seen=C.SEEN)
    before = dict(disabled.weights)
    off, rng2 = fixture_files(tmp_path / "off", attention=disabled)
    assert baseline == off and rng1 == rng2
    assert disabled.weights == before and disabled.version == 0
    assert set(off) == {"seed001.jsonl", "seed001.side.jsonl", "seed001.select.jsonl.gz"}
    assert len(gzip.decompress(off["seed001.select.jsonl.gz"]).splitlines()) == 2


def test_03_same_weights_in_three_scores_and_recomputed_self_scores():
    st, ai, cfg, y = C.example()
    cs = {c.definition.name: c for c in A.candidates(st, ai.target_graph_partial)}
    weights = {p: 1.0 for p in C.SEEN}
    normal, exception = cs["R_normal"].terms, cs["R_exception"].terms
    assert normal.scores(weights) == (12, 17, 14)
    assert exception.scores(weights) == (13, 18, 14)
    weights["sig_e"] = 2.0
    assert normal.scores(weights) == (12, 17, 15)
    assert exception.scores(weights) == (14, 19, 15)
    assert exception.value(weights) == Fraction(14, 17)
    assert normal.value(weights) == Fraction(3, 4)
    weights["sig_e"] = 1.0
    assert exception.scores(weights) == (13, 18, 14)


def test_04_H_once_max_self_and_U_never_reads_erased_name():
    st, ai, cfg, y = C.example()
    d = st.definitions["R_exception"]
    c = next(c for c in A.candidates(st, ai.target_graph_partial) if c.definition.name == d.name)
    row = d.constituents[3]
    h_d = replace(d, constituents=tuple(replace(r, alive=False) if r.slot_index == 3 else r for r in d.constituents))
    hist = dict(st.slot_history); hist[(d.name, 3)] = {"sig_e": 700, "sig_n": 30}
    t = A.terms(h_d, hist, c.alignment, ai.target_graph_partial)
    w = {p: 1.0 for p in C.SEEN}; w.update(sig_e=2, sig_n=4)
    assert dict(t.cross)["sig_e"] == 1
    assert t.scores(w) == (14, 21, 15)
    hist[(d.name, 3)] = {"sig_e": 1, "sig_n": 1}
    assert A.terms(h_d, hist, c.alignment, ai.target_graph_partial) == t
    hist.pop((d.name, 3))
    # U の行で predicate を読めば例外になる材料を渡す。
    class Erased:
        relation_id, arguments = row.relation.relation_id, row.relation.arguments
        @property
        def predicate(self):
            raise AssertionError("U の忘れた名前を読んだ")
    u_d = replace(h_d, constituents=tuple(replace(r, relation=Erased()) if r.slot_index == 3 else r for r in h_d.constituents))
    u = A.terms(u_d, hist, c.alignment, ai.target_graph_partial)
    assert "sig_e" not in dict(u.cross)
    assert u.scores(w) == (12, 17, 15)


def test_04b_empty_H_preserves_unit_N3_and_max_tie_subgradient_is_symmetric():
    d = OLD.same_def(); al = OLD.al(OLD.ID)
    d = replace(d, constituents=tuple(replace(r, alive=False) if r.slot_index == 0 else r for r in d.constituents))
    hist = dict(OLD.HIST); hist[(d.name, 0)] = {}
    tt = A.terms(d, hist, al, OLD.SCENE)
    assert tt.empty_histories == 1
    assert tt.value({}) == N.n3_value(N.n3_terms(d, hist, al, OLD.SCENE))
    hist[(d.name, 0)] = {"fold": 1, "wrap": 1}
    tt = A.terms(d, hist, al, OLD.SCENE)
    w = {"fold": 1., "wrap": 1., "lock": 1., "cause": 1.}
    g = tt.gradient(w)
    # cross の fold による差を除いた自己の微分は両名に等分。
    s, dd, xx = tt.scores(w)
    assert g["fold"] - g["wrap"] == pytest.approx(float(2 / (dd + xx)))


def test_05_analytic_gradient_matches_measured_loss_and_projected_step():
    learner, pre, st, ai, cfg, y = prepared()
    cs = pre.candidates
    w = dict(learner.weights); w.update(sig_e=1.3, hold=0.9)
    mask = tuple(c.answer == (y.predicate, y.arguments) for c in cs)
    loss, grad, pi = A.loss_gradient(cs, w, mask, 5.)
    for p in w:
        left, right = dict(w), dict(w)
        left[p] -= 1e-6; right[p] += 1e-6
        measured = (A.loss_gradient(cs, right, mask, 5.)[0] - A.loss_gradient(cs, left, mask, 5.)[0]) / 2e-6
        assert measured == pytest.approx(grad[p], abs=2e-9)
    # 平均 1 の射影まで含め、実際の小さな一歩の L と勾配による予測を照合。
    w = {p: 1. for p in w}
    loss, grad, _pi = A.loss_gradient(cs, w, mask, 5.)
    after = A.normalized_step(w, grad, 1e-6)
    delta = A.loss_gradient(cs, after, mask, 5.)[0] - loss
    predicted = math.fsum(grad[p] * (after[p] - w[p]) for p in w)
    assert delta < 0 and delta == pytest.approx(predicted, abs=2e-12)
    assert sum(pi) == pytest.approx(1.)


def test_05b_H_smooth_gradient_and_multiple_correct_candidates():
    tt = A.Terms((("a", 1),), (), (("a", "b"),), 2, 2, (("a", 1),), 2)
    cs = (A.Candidate(None, None, None, 1, 1, tt, ("answer", ())),
          A.Candidate(None, None, None, 1, 1, replace(tt, cross_structure=1), ("other", ())),
          A.Candidate(None, None, None, 1, 1, replace(tt, cross_structure=3), ("answer", ())))
    w = {"a": 1., "b": 2.}; mask = (True, False, True)
    loss, g, pi = A.loss_gradient(cs, w, mask, 10.)
    assert loss == pytest.approx(-math.log(pi[0] + pi[2]))
    for p in w:
        lo, hi = dict(w), dict(w); lo[p] -= 1e-6; hi[p] += 1e-6
        assert g[p] == pytest.approx((A.loss_gradient(cs, hi, mask, 10.)[0] - A.loss_gradient(cs, lo, mask, 10.)[0]) / 2e-6, abs=2e-9)


def test_06_two_candidate_hand_values():
    rows = C.hand_values()
    assert [r["exception_minus_normal"] for r in rows] == ["19/496", "5/68"]
    assert Fraction(rows[1]["exception_minus_normal"]) > Fraction(rows[0]["exception_minus_normal"])


def test_07_no_correct_candidate_all_same_and_no_candidates_skip():
    learner, pre, st, ai, cfg, truth = prepared()
    before = dict(learner.weights)
    wrong = replace(truth, predicate="sig_n")  # 名前自体は既に見た名前。
    rec = learner.finish(pre, C.feedback(1, wrong))
    assert rec["reason"] == "no_correct_candidate" and not rec["updated"]
    assert learner.weights == before and rec["L"] is None
    st = replace(st, definitions={"R_exception": st.definitions["R_exception"]})
    learner, pre, *_ = prepared(state=st)
    rec = learner.finish(pre, C.feedback(1, truth))
    assert rec["reason"] == "all_same_answer" and rec["L"] == pytest.approx(0)
    assert not rec["updated"]
    learner, pre, *_ = prepared(state=replace(st, definitions={}))
    rec = learner.finish(pre, C.feedback(1, truth))
    assert rec["reason"] == "no_candidates" and not rec["updated"]


def test_08_no_disclosure_never_reads_truth_and_dynamic_f_is_exact():
    class NoTruth(dict):
        def __getitem__(self, key):
            if key in ("feedback_content", "held_out_content"):
                raise AssertionError("非開示で正解を読んだ")
            return super().__getitem__(key)
    learner, pre, st, ai, cfg, truth = prepared()
    before = dict(learner.weights)
    rec = learner.finish(pre, NoTruth(C.feedback(1, truth, disclosed=False, f=.125)))
    assert rec["reason"] == "no_disclosure" and rec["f_realized"] == .125 and not rec["f_fired"]
    assert learner.weights == before
    for t, f, fired in ((2, 0., False), (3, .75, True), (4, 1., True)):
        pre = learner.prepare("agent", t, ai, st, cfg, Random(1))
        rec = learner.finish(pre, C.feedback(t, truth, f=f, disclosed=fired))
        assert rec["f_realized"] == f and rec["f_fired"] is fired
        assert rec["updated"] is fired


def test_09_current_answer_precedes_update_next_scores_follow_update():
    learner, pre, st, ai, cfg, truth = prepared()
    first = pre.output
    before_q = {c.definition.name: c.terms.value(learner.weights) for c in pre.candidates}
    rec = learner.finish(pre, C.feedback(1, truth))
    assert rec["selected_before_update"] == "R_normal" and A.answer_key(first.prediction)[0] == "hold"
    assert pre.output is first  # 採点後に今の答えを差し替えない。
    nxt = learner.prepare("agent", 2, ai, st, cfg, Random(1))
    assert dict(nxt.before) == rec["weights_after"]
    assert any(c.terms.value(dict(nxt.before)) != before_q[c.definition.name] for c in nxt.candidates)
    chosen = A.rank(nxt.candidates, learner.weights)[0]
    assert A.answer_key(nxt.output.prediction) == chosen.answer
    assert sum(learner.weights.values()) / len(learner.weights) == pytest.approx(1.)
    with pytest.raises(ValueError, match="二重"):
        learner.finish(pre, C.feedback(1, truth))


def renamed(st, ai, cfg, truth):
    names = {p: f"name_{i}" for i, p in enumerate(reversed(C.SEEN))}
    ids = {x: f"id_{i}" for i, x in enumerate(("x", "y", "a", "b", "door", "fold", "root", "sig", "attach", "extra",
                                               "s_door", "s_fold", "s_root", "s_sig", "s_attach"))}
    dn = {"R_normal": "def_B", "R_exception": "def_A"}
    def rel(r):
        return replace(r, relation_id=ids[r.relation_id], predicate=names.get(r.predicate, r.predicate),
                       arguments=tuple(ids[a] for a in r.arguments))
    def graph(g):
        return replace(g, entities=tuple(replace(e, entity_id=ids[e.entity_id]) for e in reversed(g.entities)),
                       relations=tuple(rel(r) for r in reversed(g.relations)))
    defs = {dn[d.name]: replace(d, name=dn[d.name], constituents=tuple(replace(r, slot_index=100-r.slot_index, relation=rel(r.relation))
                                                                            for r in reversed(d.constituents))) for d in st.definitions.values()}
    hist = {(dn[n], 100-s): {names[p]: k for p, k in v.items()} for (n, s), v in st.slot_history.items()}
    ph = replace(st.p_hat, counts={names[p]: k for p, k in st.p_hat.counts.items()}, alive_vocab=frozenset(names.values()))
    st2 = replace(st, definitions=defs, slot_history=hist, p_hat=ph,
                  prototype=Prototype(tuple(replace(t, scene=graph(t.scene)) for t in st.prototype.traces)))
    ai2 = replace(ai, base_graph=graph(ai.base_graph), target_graph_partial=graph(ai.target_graph_partial),
                  observable_mask=tuple(ids[x] for x in ai.observable_mask))
    return st2, ai2, replace(cfg, higher_order_predicates=frozenset(names[p] for p in cfg.higher_order_predicates)), rel(truth), names, ids


def test_10_name_id_seat_number_relabeling_preserves_answer_and_update():
    st, ai, cfg, truth = C.example(extra_unknown=True)
    st2, ai2, cfg2, truth2, names, ids = renamed(st, ai, cfg, truth)
    a, b = A.Attention(enabled=True, seen=C.SEEN), A.Attention(enabled=True, seen=names.values())
    x, y = a.prepare("agent", 1, ai, st, cfg, Random(1)), b.prepare("agent", 1, ai2, st2, cfg2, Random(1))
    pred, args = A.answer_key(x.output.prediction)
    assert A.answer_key(y.output.prediction) == (names[pred], tuple(ids[z] for z in args))
    ra, rb = a.finish(x, C.feedback(1, truth)), b.finish(y, C.feedback(1, truth2))
    assert ra["L"] == pytest.approx(rb["L"], abs=1e-14)
    assert {names[p]: w for p, w in a.weights.items()} == pytest.approx(b.weights, abs=1e-14)


def test_11_record_only_memory_attention_and_rng_match_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(gzip.time, "time", lambda: 1791000000)
    baseline, rng1 = fixture_files(tmp_path / "baseline")
    learner = A.Attention(enabled=False, seen=C.SEEN)
    before = (dict(learner.weights), learner.version, set(learner._finished))
    log, rng2 = fixture_files(tmp_path / "log", attention=learner, record_only=True)
    assert baseline == log and rng1 == rng2
    assert before == (learner.weights, learner.version, learner._finished)
    learner, pre, *_ = prepared()
    rec = learner.finish(pre, C.feedback(1, C.example()[3]))
    before = (dict(learner.weights), learner.version, set(learner._finished))
    stream = io.StringIO(); A.write_record(stream, rec)
    assert json.loads(stream.getvalue()) == json.loads(json.dumps(rec))
    assert before == (learner.weights, learner.version, learner._finished)


def test_12_gate_and_silence_are_precomputed_without_fallback():
    learner, pre, st, ai, cfg, truth = prepared(config=replace(C.example()[2], tau_acc=1.))
    assert isinstance(pre.output.prediction, Abstain)
    assert all(c.answer is None for c in pre.candidates)
    rec = learner.finish(pre, C.feedback(1, truth))
    assert not rec["updated"] and rec["reason"] == "no_correct_candidate"


def test_13_mean_scope_includes_only_seen_and_feedback_after_disclosure():
    learner = A.Attention(enabled=True, seen=C.SEEN)
    learner, pre, st, ai, cfg, truth = prepared(learner)
    unseen = replace(truth, predicate="new_name")
    learner.finish(pre, C.feedback(1, unseen, disclosed=False))
    assert "new_name" not in learner.weights
    pre = learner.prepare("agent", 2, ai, st, cfg, Random(1))
    rec = learner.finish(pre, C.feedback(2, unseen))
    assert "new_name" not in rec["weights_before"] and rec["weights_after"]["new_name"] == 1.
    assert not rec["updated"] and sum(learner.weights.values()) == len(learner.weights)


def test_14_nonnegative_projection_ties_and_agent_isolation():
    assert A.normalized_step({"a": 1., "b": 1.}, {"a": 10., "b": -1.}, 1.) == {"a": 0., "b": 2.}
    assert A.normalized_step({"a": 1., "b": 1.}, {"a": 10., "b": 10.}, 1.) == {"a": 1., "b": 1.}
    learner, pre, st, ai, cfg, truth = prepared()
    other = A.Attention(enabled=True, seen=C.SEEN)
    with pytest.raises(ValueError, match="他個体"):
        other.finish(pre, C.feedback(1, truth))
    assert set(other.weights.values()) == {1.}
    cs = A.candidates(st, ai.target_graph_partial)
    c = cs[0]
    tied = (replace(c, definition=replace(c.definition, name="B")), replace(c, definition=replace(c.definition, name="A")))
    assert A.rank(tied, learner.weights)[0].definition.name == "A"
    newer = replace(tied[0], definition=replace(tied[0].definition, registered_at=4))
    assert A.rank((newer, tied[1]), learner.weights)[0].definition.name == "B"
    bigger = replace(tied[0], n=tied[0].n + 1)
    assert A.rank((bigger, newer), learner.weights)[0].n == bigger.n
