"""段2：実際の予測を通し、対応・順つきの答え・結果の共有を検査する。"""
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from random import Random
import json
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import pytest
import answergap
import probeworld
import shopscatter
import shopworld
import smeshared
import smereplay
import ustruct
import useforget
import v39
from abm.definition import Constituent, FrozenPrice, FrequencyTable, NamedDefinition
from abm.domains import AgentConfig, AgentInput, CorrectionMode, EdgePrediction, Entity, Prototype, Relation, RelationGraph, VerbatimTrace
import abm.sme as sme
from abm.seed import load_seed
from abm.world import generate_trial, opaque_id


@pytest.fixture(autouse=True)
def separate(monkeypatch):
    # 包みの入口と控えを各小例で戻す。元の記憶や公式配布は変更しない。
    for module in tuple(sys.modules.values()):
        if module is not None and hasattr(module, "map_graphs"):
            monkeypatch.setattr(module, "map_graphs", module.map_graphs)
    for module in (v39, ustruct, answergap, shopworld, smeshared, useforget):
        for key in ("ST", "STATS", "CFG", "CTX", "REG", "UREG", "RESULTS", "GRAPHS", "CHOICES", "LOG", "ENGINE", "OLD_MAP"):
            if hasattr(module, key):
                current = getattr(module, key)
                monkeypatch.setattr(module, key, {} if isinstance(current, dict) else current)
    for key in ("select_definition", "fill_v39", "fill_decision"):
        monkeypatch.setattr(v39, key, getattr(v39, key))
    monkeypatch.setattr(probeworld, "_snapshot_modules", probeworld._snapshot_modules)
    monkeypatch.setattr(probeworld, "_restore_modules", probeworld._restore_modules)
    v39.CFG.update(amb_local=True, u_abstain=False, D=100, dict_index={}, T=1740, decay=(0.5,) * 16)
    v39.CTX.update(answers=None, output=None)
    smeshared.install(None, tie_seed=1)
    answergap.install()


def partial(g, hid):
    visible = tuple(r for r in g.relations if r.relation_id != hid)
    ents = {e.entity_id for e in g.entities}
    seen = {a for r in visible for a in r.arguments if a in ents}
    return RelationGraph(g.graph_id + ":partial", tuple(e for e in g.entities if e.entity_id in seen), visible)


def memory(g, name="R"):
    d = NamedDefinition(name, tuple(Constituent(i, 0, r, FrozenPrice(3, 0, 0, len(g.relations)))
                                   for i, r in enumerate(g.relations)), len(g.relations), 0)
    counts = Counter(r.predicate for r in g.relations)
    p = FrequencyTable(dict(counts), sum(counts.values()), 0.1, frozenset(counts))
    return v39._state_class()(prototype=Prototype((VerbatimTrace(0, g),)), definitions={name: d}, p_hat=p,
                             slot_history={(name, i): {r.predicate: 1} for i, r in enumerate(g.relations)})


def predict(g, scene):
    config = AgentConfig(0, CorrectionMode.NONE, tau_acc=0.67, nsim_threshold=0.7,
                         local_lambda=1, higher_order_predicates=frozenset({"cause", "attach", "govern", "and", "link"}))
    state = memory(g)
    before = repr(state)
    output, _ = v39.predict(AgentInput(g, scene), state, config, Random(1))
    assert repr(state) == before
    return output


@pytest.mark.parametrize("world", [1, 2])
@pytest.mark.parametrize("typ", ["甲", "乙"])
@pytest.mark.parametrize("cue", ["n", "e"])
def test_shop_correct_definition_door_and_order(world, typ, cue):
    sd = load_seed(Path(__file__).parent / "shop/U-011_seed_shop.json")
    found = {}
    for t in range(20):
        tr = generate_trial(1, t, ("agent",), seed=sd)
        if shopworld.TYPE[tr.motif] == typ:
            found[typ] = tr
            break
    tr = found[typ]
    built, info = shopworld.build(tr, 1, tr.trial, cue=cue, world=world)
    scattered = shopscatter.scatter(built, 1, tr.trial)
    scene = partial(scattered.G_star, info["door_id"])
    output = predict(scattered.G_star, scene)
    expected = next(r for r in scattered.G_star.relations if r.relation_id == info["door_id"])
    assert isinstance(output.prediction, EdgePrediction)
    assert output.prediction.edge.predicate == expected.predicate
    assert output.prediction.edge.arguments == expected.arguments
    assert output.trace["definition_alignment"].sme_audit["version"] == smeshared.VERSION
    assert output.trace["R_used"] == "R"


def competition(prefix, variant, complete=True):
    u, a, b, v, o = [prefix + k for k in ("u", "a", "b", "v", "o")]
    rows = [("p", "fold", (u, a)), ("r", "fold", (u, b)),
            ("cueA", "break", (a if variant == "A" else b, v)),
            ("cueB", "break_b", (b if variant == "A" else a, v)),
            ("anchor", "carry", (o, a)), ("other1", "lift", (v, o)), ("other2", "press", (o, u)),
            ("parent", "cause", (prefix + "hole", prefix + "anchor"))]
    if complete:
        rows.append(("hole", "hold" if variant == "A" else "hold_b", (a, v)))
    return RelationGraph(prefix, tuple(Entity(k) for k in (u, a, b, v, o)),
                         tuple(Relation(prefix + k, name, args) for k, name, args in rows))


@pytest.mark.parametrize("variant", ["A", "B"])
def test_competitive_name_fixture_through_prediction(variant):
    d, s = competition("d", variant), competition("s", variant, False)
    other = competition("s", "B" if variant == "A" else "A", False)
    assert Counter(r.predicate for r in s.relations) == Counter(r.predicate for r in other.relations)
    # 二例とも伏せ位置は同じ親の同じ引数。名前の集合と高階の位置は区別しない。
    assert s.relations[-1] == other.relations[-1]
    output = predict(d, s)
    assert isinstance(output.prediction, EdgePrediction)
    assert output.prediction.edge.predicate == ("hold" if variant == "A" else "hold_b")
    assert output.prediction.edge.arguments == ("sa", "sv")
    assert output.trace["definition_alignment"].entity_mapping == {"d" + k: "s" + k for k in ("u", "a", "b", "v", "o")}


def test_same_result_immutable_and_snapshot_restore():
    left, right = competition("d", "A"), competition("s", "A", False)
    snapshot = probeworld._snapshot_modules()
    first = sme.map_graphs(left, right)
    assert sme.map_graphs(left, right) is first
    assert smeshared.STATS["computed"] == 1 and smeshared.STATS["reused"] == 1
    with pytest.raises(TypeError):
        first.alignment.relation_mapping["dhole"] = "wrong"
    json.dumps(asdict(first.alignment))
    probeworld._restore_modules(snapshot)
    assert smeshared.STATS == {}
    again = sme.map_graphs(left, right)
    assert first == again
    assert smeshared.ENGINE.rng.getstate() == smeshared.snapshot()[0][0]


def test_unknown_h_and_u_adapter_has_no_unobserved_names(monkeypatch):
    g = RelationGraph("d", (Entity("a"),), (Relation("h", "fake", ("a",)), Relation("parent", "cause", ("u", "hole"))))
    v39.REG[id(g)] = (g, {"h": frozenset({"p", "q"})}, frozenset({"u"}))
    ustruct.UREG[id(g)] = {"u": Relation("u", "名前を消した記憶", ("a",))}
    typed = smeshared.typed_graph(g).by_id
    assert typed["h"].state == "H" and typed["h"].names == frozenset({"p", "q"})
    assert typed["u"].state == "U" and not typed["u"].names and typed["u"].args == ("a",)
    assert typed["hole"].kind == "unknown" and typed["hole"].args is None and not typed["hole"].names


def test_researcher_truth_cannot_change_prediction():
    d, scene = competition("d", "A"), competition("s", "A", False)
    truths = [Relation("shole", name, args) for name, args in (("hold", ("sa", "sv")), ("other", ("sb", "su")))]
    before = smeshared.snapshot()
    outputs = []
    for truth in truths:
        # 正解は研究者の変数だけ。AgentInputへ渡さず、同じ記憶と提示を評価する。
        smeshared.restore(before)
        outputs.append(predict(d, scene))
    assert truths[0] != truths[1]
    assert outputs[0] == outputs[1]


def test_scatter_preserves_tree_cue_coins_and_answer_rule():
    sd = load_seed(Path(__file__).parent / "shop/U-011_seed_shop.json")
    for t in range(6):
        for world in (1, 2):
            for cue in ("n", "e"):
                original = generate_trial(1, t, ("agent",), seed=sd)
                built, info = shopworld.build(original, 1, t, cue=cue, world=world)
                out = shopscatter.scatter(built, 1, t)
                assert out.u_coins == built.u_coins and out.held_out_edge.relation_id == built.held_out_edge.relation_id
                assert len(out.G_star.entities) == len(built.G_star.entities) + 6
                assert [r.predicate for r in out.G_star.relations] == [r.predicate for r in built.G_star.relations]
                old, new = {r.relation_id: r for r in built.G_star.relations}, {r.relation_id: r for r in out.G_star.relations}
                changed = [rid for rid in old if old[rid] != new[rid]]
                assert len(changed) == 8
                assert new[info["sig_id"]].arguments == (opaque_id(1, t, "entity:a"),)
                assert new[info["door_id"]].predicate == shopworld.door_pred(world, shopworld.TYPE[original.motif], cue)


def test_d_name_use_once_and_unknown_not_used():
    g, scene = competition("d", "A"), competition("s", "A", False)
    state = memory(g)
    config = AgentConfig(0, CorrectionMode.NONE, tau_acc=0.67, local_lambda=1, higher_order_predicates=frozenset({"cause"}))
    useforget.ST.update(t=1, rec={"uses": [], "struct": [], "answer": None}, S={}, used_t=set(), n_use={}, stats={"uses": 0})
    selected = v39.select_definition(state, scene, config)
    useforget._record_matching(state, scene, selected)
    assert useforget.ST["stats"]["uses"] == 8
    assert useforget.ST["rec"]["struct"] == [[8, "F"]]
    output, _ = v39.predict(AgentInput(g, scene), state, config, Random(1))
    useforget._record_answer(state, output)
    assert useforget.ST["stats"]["uses"] == 9
    # 候補の再検査を増やしても、同じ試行の名前の使用は増えない。
    for _ in range(3):
        useforget._record_matching(state, scene, v39.select_definition(state, scene, config))
        useforget._record_answer(state, output)
    assert useforget.ST["stats"]["uses"] == 9
    assert all(n == 1 for n in useforget.ST["n_use"].values())


def test_candidate_order_same_choice_and_delivered_alignment():
    good = competition("d", "A")
    other = competition("o", "B")
    target = competition("s", "A", False)
    state = memory(good)
    second = memory(other, "Other")
    state = replace(state, definitions={**state.definitions, **second.definitions}, slot_history={**state.slot_history, **second.slot_history})
    config = AgentConfig(0, CorrectionMode.NONE)
    initial = smeshared.snapshot()
    result = v39.select_definition(state, target, config)
    smeshared.restore(initial)
    reverse = replace(state, definitions=dict(reversed(list(state.definitions.items()))))
    result2 = v39.select_definition(reverse, target, config)
    assert result[2].name == result2[2].name == "R"
    assert result[4] == result2[4]


def test_diagnosis_twice_restores_broker_frequency_memory_and_world_rng():
    g, scene = competition("d", "A"), competition("s", "A", False)
    state = memory(g)
    rng = Random(1)
    before = repr(state), rng.getstate(), smeshared.snapshot()
    for _ in range(2):
        snap = probeworld._snapshot_modules()
        predict(g, scene)
        probeworld._restore_modules(snap)
    assert repr(state) == before[0] and rng.getstate() == before[1]
    assert smeshared.snapshot() == before[2]


def test_saved_state_retains_argument_order_and_four_score_columns():
    g = competition("d", "A")
    state = memory(g)
    rec = v39.SeatRec(0, "F", 1, 2, tuple((float(i),) * 16 for i in (7, 3, 9, 1)), v39.ZERO4)
    state = replace(state, v39_seats={("R", 0): rec})
    saved = json.loads(json.dumps(smereplay.encode(state)))
    restored = smereplay.decode(saved)
    assert smereplay.encode(restored) == saved
    assert restored.definitions["R"].constituents[0].relation.arguments == ("du", "da")
    assert tuple(x[0] for x in restored.v39_seats["R", 0].init) == (7, 3, 9, 1)


def test_saved_state_with_existing_v38_merit_and_closed_type_list(monkeypatch):
    import inspect
    import io
    import abm.accounting as accounting
    import abm.loop as loop
    import v38
    for mod, names in ((loop, ("classify_row", "update_merit", "_update_accounting")),
                       (accounting, ("participation",))):
        for name in names:
            monkeypatch.setattr(mod, name, getattr(mod, name))
    for name in ("STATS", "CTX", "_REAL"):
        monkeypatch.setattr(v38, name, {})
    v38.install(io.StringIO())
    cls = inspect.getclosurevars(loop.update_merit).nonlocals["MeritAccumulatorV38"]
    acc = cls(2, 3, (1.0,) * 16, (2.0,) * 16, 4.0, 0, (), (3.0,) * 16)
    state = replace(memory(competition("d", "A")), merit={("R", 2, 3): acc})
    saved = json.loads(json.dumps(smereplay.encode(state)))
    restored = smereplay.decode(saved)
    assert type(restored.merit["R", 2, 3]) is cls
    assert smereplay.encode(restored) == saved
    # abmの接頭辞だけでも許可せず、読込前に拒否する。
    with pytest.raises(ValueError, match="認めていない型"):
        smereplay.decode({"tag": "dataclass", "module": "abm.unlisted", "name": "Other", "fields": {}})
