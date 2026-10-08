"""動詞の世界の構造の検査。模型の誤答方向は合格条件にしない。"""
import json
import sys
from dataclasses import replace
from math import isclose
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verbworld as vw  # noqa: E402
import probeworld as pw  # noqa: E402
from abm.seed import load_seed  # noqa: E402
import abm.world as world  # noqa: E402


def base(t=0):
    return world.generate_trial(1, t, ("agent",), seed=load_seed(ROOT / "tools/verb/U-011_seed_verb.json"))


def test_distribution_and_novel_exclusion():
    items = vw.training_items()
    assert len(items) == 40
    assert [v.name for v in items] == list(vw.NAMES[:40])
    assert isclose(sum(v.probability for v in items if v.verb_class == "irregular"), .70)
    assert isclose(sum(v.probability for v in items if v.verb_class == "regular"), .30)
    for t in range(300):
        assert vw.draw_verb(1, t, items).name not in vw.NOVEL_NAMES
        assert vw.draw_verb(1, t, items) == vw.draw_verb(1, t, items)


@pytest.mark.parametrize("verb", [vw.training_items()[0], vw.training_items()[32], vw.Verb("V41", "novel", "REG", 0)])
def test_name_link_past_and_other_relations(verb):
    tr = base()
    out, info = vw.build(tr, 1, 0, verb=verb)
    old = {r.relation_id: r for r in tr.G_star.relations}
    new = {r.relation_id: r for r in out.G_star.relations}
    assert len(new) == len(old) + 2
    assert new[info["past_id"]].predicate == verb.past
    assert new[info["past_id"]].arguments == old[info["past_id"]].arguments
    assert new[info["name_id"]].predicate == verb.name
    assert new[info["name_id"]].arguments == (world.opaque_id(1, 0, "entity:a"),)
    assert new[info["link_id"]].predicate == "attach"
    assert new[info["link_id"]].arguments == (info["name_id"], info["root_id"])
    assert out.G_star.relations[-2:] == (new[info["name_id"]], new[info["link_id"]])
    assert not {"sig_n", "sig_e"} & {r.predicate for r in out.G_star.relations}
    assert all(new[rid] == row for rid, row in old.items() if rid != info["past_id"])
    assert out.held_out_edge.relation_id == tr.held_out_edge.relation_id
    assert out.u_coins == tr.u_coins
    assert info["name_id"] in {r.relation_id for r in out.target_graph_partial.relations}
    assert info["link_id"] in {r.relation_id for r in out.target_graph_partial.relations}
    assert out.held_out_edge.relation_id not in (info["name_id"], info["link_id"])


def test_past_holdout_changes_truth_only():
    tr = base()
    rid = world.opaque_id(1, 0, "relation:tree:0.0.0")
    held = next(r for r in tr.G_star.relations if r.relation_id == rid)
    tr = replace(tr, held_out_edge=held, target_graph_partial=pw._partial(tr.G_star, rid))
    out, info = vw.build(tr, 1, 0, verb=vw.training_items()[39])
    assert out.held_out_edge.predicate == "IRR_8"
    assert info["held_out_is_past"] is True
    assert rid not in {r.relation_id for r in out.target_graph_partial.relations}


@pytest.mark.parametrize("p", [None, 0.0, 0.25, 0.5, 1.0])
def test_past_probability_reuses_shop_choice_before_name(monkeypatch, p):
    import shopworld
    monkeypatch.setattr(vw, "CFG", {"items": vw.training_items(), "door_p": p})
    monkeypatch.setattr(vw, "INFO", {})
    monkeypatch.setattr(vw, "IDS", {})
    monkeypatch.setattr(vw, "STATS", {})
    monkeypatch.setattr(shopworld, "STATS", {})
    sd = load_seed(ROOT / "tools/verb/U-011_seed_verb.json")
    for t in range(40):
        tr = base(t)
        expected = tr if p is None else shopworld.rehide(tr, 1, t, p)
        expected, info = vw.build(expected, 1, t, verb=vw.draw_verb(1, t))
        actual = vw.verb_trial(world.generate_trial, 1, t, ("agent",), seed=sd)
        assert actual == expected
        assert actual.u_coins == tr.u_coins
        assert info["name_id"] in {r.relation_id for r in actual.target_graph_partial.relations}
        assert info["link_id"] in {r.relation_id for r in actual.target_graph_partial.relations}
        if p in (0.0, 1.0):
            assert info["held_out_is_past"] == bool(p)


def test_dictionary_keeps_existing_indices(monkeypatch):
    import v39
    monkeypatch.setattr(v39, "CFG", {"dict_index": {"hold": 0, "push": 1, "attach": 2}, "D": 3})
    vw.extend_dictionary()
    assert {p: v39.CFG["dict_index"][p] for p in ("hold", "push", "attach")} == {"hold": 0, "push": 1, "attach": 2}
    assert set(vw.NEW_PREDICATES) <= set(v39.CFG["dict_index"])
    assert v39.CFG["D"] == len(v39.CFG["dict_index"])


def test_probe_inputs_are_past_blind_and_novel(monkeypatch):
    sd = load_seed(ROOT / "tools/verb/U-011_seed_verb.json")
    monkeypatch.setattr(vw, "CFG", {"items": vw.training_items()})
    monkeypatch.setattr(vw, "CTX", {"orig_gen": world.generate_trial})
    monkeypatch.setattr(pw, "SNAP_MODULES", pw.SNAP_MODULES)
    monkeypatch.setattr(pw, "SNAP_ATTRS", pw.SNAP_ATTRS)
    st = {"sd": sd, "probes": []}
    vw.add_probes(st, run_seed=1, agent_ids=("agent",), holdout_second=False)
    assert len(st["probes"]) == 48
    novel = [q for q in st["probes"] if q["extra"]["verb_class"] == "novel"]
    assert tuple(q["verb_name"] for q in novel) == vw.NOVEL_NAMES
    assert all(q["truth"] is None and not q["score_truth"] for q in novel)
    for q in st["probes"]:
        assert q["hid"] not in {r.relation_id for r in q["partial"].relations}
        assert q["verb_name"] in {r.predicate for r in q["partial"].relations}
        assert not ({"REG", *(f"IRR_{k}" for k in range(1, 9))} & {r.predicate for r in q["partial"].relations})


def test_schuler_does_not_guess_counts(tmp_path):
    with pytest.raises(ValueError, match="未確定"):
        vw.training_items("schuler54")
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"source": "49回の不一致の表", "schuler54": [16, 8, 5, 4, 4, 3, 3, 3, 3]}))
    with pytest.raises(ValueError, match="REG 比"):
        vw.training_items("schuler54", p)


def test_seen_is_verb_specific_and_requires_disclosure(monkeypatch):
    tr = base()
    out, info = vw.build(tr, 1, 0, verb=vw.training_items()[32])
    monkeypatch.setattr(vw, "INFO", {out.G_star.graph_id: {**info, "held_out_is_past": True}})
    st = {"trials": {0: out}, "disclosed": {}}
    assert vw.seen(st, 1, "V33")[0] == {}
    st["disclosed"][0] = True
    assert vw.seen(st, 1, "V33")[0] == {"IRR_1": 1}
    assert vw.seen(st, 1, "V41")[0] == {}
    assert vw.seen(st, 1, None)[0] == {"IRR_1": 1}


def test_probe_setup_restores_researcher_world_registry(monkeypatch, tmp_path):
    import abm.loop as loop
    import abm.ledger as ledger
    import abm.seed as seedmod
    import sweep
    for module, name in ((world, "generate_trial"), (loop, "_ledger_record"), (loop, "_update_accounting"),
                         (loop, "apply_theta"), (ledger.Ledger, "append"), (seedmod, "higher_order_predicates"),
                         (sweep, "higher_order_predicates")):
        monkeypatch.setattr(module, name, getattr(module, name))
    for name in ("INFO", "IDS", "CTX", "CFG", "STATS"):
        monkeypatch.setattr(vw, name, {})
    monkeypatch.setattr(pw, "ST", {})
    monkeypatch.setattr(pw, "SNAP_MODULES", pw.SNAP_MODULES)
    monkeypatch.setattr(pw, "SNAP_ATTRS", pw.SNAP_ATTRS)
    vw.install()
    vw.prepare_probe_snapshot(pw)
    pw.install(tmp_path / "probe.jsonl", run_seed=1, agent_ids=("agent",),
               seed_file=ROOT / "tools/verb/U-011_seed_verb.json", horizon=5000, holdout_second=False)
    assert vw.STATS == {} and vw.INFO == {} and vw.IDS == {}
    tr = world.generate_trial(1, 0, ("agent",), seed=load_seed(ROOT / "tools/verb/U-011_seed_verb.json"))
    assert vw.STATS["trials"] == 1
    assert vw.INFO[tr.G_star.graph_id]["verb_name"] in vw.NAMES[:40]
    pw.close()


def test_native_probe_keeps_state_and_global_statistics(monkeypatch):
    """学習なしの既存予測器を呼び、問い48個の前後で状態と部品の控えを比べる。"""
    import io
    import abm.agent_runtime as ar
    import v39
    from abm.domains import AgentConfig, AgentState, CorrectionMode, Prototype, VerbatimTrace
    sd = load_seed(ROOT / "tools/verb/U-011_seed_verb.json")
    tr, info = vw.build(base(), 1, 0, verb=vw.training_items()[0])
    monkeypatch.setattr(vw, "INFO", {tr.G_star.graph_id: info})
    monkeypatch.setattr(vw, "CFG", {"items": vw.training_items()})
    monkeypatch.setattr(vw, "CTX", {"orig_gen": world.generate_trial})
    monkeypatch.setattr(pw, "SNAP_MODULES", pw.SNAP_MODULES)
    monkeypatch.setattr(pw, "SNAP_ATTRS", pw.SNAP_ATTRS)
    monkeypatch.setattr(v39, "CFG", {"D": len(vw.NEW_PREDICATES)})
    st = dict(sd=sd, probes=[], f=io.StringIO(), run_seed=1, trials={0: tr}, disclosed={0: True},
              predict=ar.predict, checks=0, rows=0)
    monkeypatch.setattr(pw, "ST", st)
    vw.add_probes(st, run_seed=1, agent_ids=("agent",), holdout_second=False)
    state = AgentState(prototype=Prototype((VerbatimTrace(0, tr.target_graph_partial),)))
    config = AgentConfig(0.0, CorrectionMode.NONE, higher_order_predicates=frozenset())
    before = pw._fingerprint(state)
    saved = dict(v39.STATS)
    pw._probe(state, config, 100)
    assert pw._fingerprint(state) == before
    assert dict(v39.STATS) == saved
    assert st["checks"] == 1 and st["rows"] == 48
    records = [json.loads(line) for line in st["f"].getvalue().splitlines()]
    assert len(records) == 48
    assert all(r["exp_path_n"] == 0 for r in records if r["verb_class"] == "novel")
