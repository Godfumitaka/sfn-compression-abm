"""v3.11c（集団化・事例伝達、tools/v311c.py）の受入検査の小例（仕様 control/sfn_collective_spec_2026-09-29_v2.md の 8 節 ③〜⑧）。
走行で確かめる ①・②・⑨・⑩・⑪・⑫ は tools/v311c_checks/ の台本で別に確かめる。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from random import Random
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import v39  # noqa: E402
import v311c  # noqa: E402
from abm.accounting import decay_ladder  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Abstain, EdgePrediction, Entity, Prototype, Relation, RelationGraph, VerbatimTrace  # noqa: E402

PRICE = FrozenPrice(1.0, 0, 0.0, 3)
DICT = ["fold", "wrap", "lock", "push", "pull", "allow", "cause"]
v39._install_candidates()


def setup():
    for d in (v39.STATS, v39.CFG, v39.CTX, v39.REG, v39._POW, v311c.STATS, v311c.CFG, v311c.CTX):
        d.clear()
    v39.CFG.update(seed=1, T=100, budget=None, init="two", a=0.5, u_abstain=False, decay=decay_ladder(100), D=len(DICT),
                   dict_index={p: i for i, p in enumerate(DICT)}, rho=None, argmax=False, commons=False)
    v39.CTX.update(struct_cache={}, births_rec=[], relearn=[], drift=[], cost_mismatch=[])
    v311c.CFG.update(run=1, agent=0, wseed=1, n=2, T=100, q=1.0, m=0.0, recv="B", groups=[0, 0], tags=True, b=8, tag_limit=100)
    v311c.STATS.update(new_tags=0)
    v311c.CTX.update(t=0, tag_counter=0)


def row(slot, pred, args, alive=True, rid=None):
    return Constituent(slot, 3, Relation(rid or f"d{slot}", pred, args), PRICE, alive)


def definition(*rows, name="R_x"):
    return NamedDefinition(name, tuple(rows), len(rows), 3)


def state(defs=(), hist=None, tags=None, traces=(), trace_tags=None):
    S = v311c._state_class()
    counts = {"fold": 5, "wrap": 3, "lock": 2, "push": 1, "cause": 2, "allow": 1}
    return S(definitions={d.name: d for d in defs}, slot_history=hist or {}, p_hat=FrequencyTable(counts, 14, 0.1, frozenset(counts)),
             v39_seats={}, c_tags=tags or {}, prototype=Prototype(tuple(traces)), c_trace_tags=trace_tags or {})


# 場面：物 a・b・c。一階 s1 fold(a,b)・s2 lock(b,c)。高階 s3 allow(s1, s2)・s4 cause(s3, s1)（見えている）。
# s5 cause(h, s2)：h は見えていない関係（伏せられた）を参照する。
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")), (
    Relation("s1", "fold", ("a", "b")), Relation("s2", "lock", ("b", "c")), Relation("s3", "allow", ("s1", "s2")),
    Relation("s4", "cause", ("s3", "s1")), Relation("s5", "cause", ("h", "s2"))))


def output_for(d, mapping, pred):
    al = SimpleNamespace(relation_mapping=mapping, entity_mapping={})
    return SimpleNamespace(prediction=pred, trace={"R_used": d.name, "definition_alignment": al})


# ③ 沈黙では束を作らない。発話の束に予測は一件だけ（新しい予測を作らない）
def test_03_silent_no_bundle_and_single_prediction():
    setup()
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z")))
    st = state([d])
    silent = output_for(d, {"d0": "s1"}, Abstain("no_projectable_relation"))
    assert v311c.build_bundle(st, silent, SCENE, 5) is None
    pred = EdgePrediction(Relation("sme_projection__d1", "wrap", ("b", "c")))
    b = v311c.build_bundle(st, output_for(d, {"d0": "s1"}, pred), SCENE, 5)
    assert list(b["origin"].values()).count("予測") == 1 and b["final"] == 2


# ④ 束は開示の前の情報（使った定義・見えている場面・実際の予測）だけで決まる。受け手へは束・名札・送り手・宛先だけ
def test_04_bundle_fixed_and_no_truth_to_receiver():
    setup()
    d = definition(row(0, "fold", ("x", "y")))
    pred = EdgePrediction(Relation("sme_projection__d9", "wrap", ("b", "c")))
    out = output_for(d, {"d0": "s1"}, pred)
    b1 = v311c.build_bundle(state([d]), out, SCENE, 5)
    b2 = v311c.build_bundle(state([d]), out, SCENE, 5)
    assert v311c.graph_to_plain(b1["graph"]) == v311c.graph_to_plain(b2["graph"])     # 同じ入力なら同じ束（開示の情報は入力に無い）
    b1.update(tag="n1", send=True, to=1, sender=0)
    pub = v311c._pub(b1)
    assert set(pub) == {"graph", "tag", "sender", "to"}                                 # 見た／予測／補った・正誤・型は渡さない
    assert "origin" not in pub and "pred" not in pub


# ⑤ 参照先：見える参照先の多段の追加、予測を参照先に、欠落による連鎖の除外、共有する参照の重複なし、本数、付け直し
def test_05_reference_resolution():
    setup()
    d = definition(row(0, "cause", ("q", "p"), rid="d0"), row(1, "fold", ("x", "y")), row(2, "cause", ("h2", "d1"), rid="d2"))
    st = state([d])
    pred = EdgePrediction(Relation("sme_projection__d1", "wrap", ("a", "c")))
    # 定義が写したのは s4（cause(s3, s1)）と s5（cause(h, s2)）
    b = v311c.build_bundle(st, output_for(d, {"d0": "s4", "d2": "s5"}, pred), SCENE, 5)
    assert b["initial"] == 3                               # s4・s5・予測
    assert b["excluded"] == 1 and list(b["excluded_ids"]) == ["s5"]   # s5 は見えていない h を要る → 外す
    assert set(b["added_ids"]) == {"s3", "s1", "s2"}       # s4 → s3（→ s1・s2）・s1：多段の追加、s1 は一度だけ（共有する参照）
    assert b["final"] == b["initial"] - b["excluded"] + b["added"] == 5
    g = b["graph"]
    ids = {r.relation_id for r in g.relations}
    assert all(not x.startswith("s") for x in ids)          # 付け直し
    by = {r.predicate: r for r in g.relations}
    assert by["allow"].arguments[0] in ids and by["allow"].arguments[1] in ids   # 束の中の対応は保つ
    # 予測を参照先に：束の関係が予測を引数に持つとき（予測は見えていなくても認める）
    sc2 = RelationGraph("sc2", SCENE.entities, SCENE.relations + (Relation("s6", "allow", ("sme_projection__d1", "s1")),))
    b2 = v311c.build_bundle(st, output_for(d, {"d0": "s6"}, pred), sc2, 6)
    assert b2["excluded"] == 0 and b2["final"] == 3 and not b2["pred_excluded"]
    # 欠落の連鎖：予測そのものが見えていない関係を要ると、予測も、それを参照する関係も外れる
    pred2 = EdgePrediction(Relation("filling__R_x__0__3", "cause", ("filling__R_x__1__3", "s1")))
    sc3 = RelationGraph("sc3", SCENE.entities, SCENE.relations + (Relation("s7", "allow", ("filling__R_x__0__3", "s2")),))
    b3 = v311c.build_bundle(st, output_for(d, {"d0": "s7"}, pred2), sc3, 7)
    assert b3.get("empty") or (b3["pred_excluded"] and "s7" in b3["excluded_ids"])


# ⑥ 受信 B：同じ名札の過去の束があればそれに絞る。無ければ A。記憶が空なら土台なし
def test_06_receive_B_candidates():
    setup()
    G = RelationGraph("bnew", (Entity("u"), Entity("v")), (Relation("q1", "fold", ("u", "v")), Relation("q2", "wrap", ("u", "v"))))
    world = VerbatimTrace(3, RelationGraph("w", (Entity("a"), Entity("b")), (Relation("w1", "fold", ("a", "b")), Relation("w2", "wrap", ("a", "b")))))
    rep = VerbatimTrace(2, RelationGraph("bold", (Entity("x"), Entity("y")), (Relation("o1", "fold", ("x", "y")),)))
    st = state(traces=[world, rep], trace_tags={"bold": "nT"})
    base, _, n_same, used_B = v311c.choose_partner(st, G, "nT", "B")
    assert used_B and n_same == 1 and base.scene.graph_id == "bold"          # 同じ名札の候補がある：その中で選ぶ
    base, _, n_same, used_B = v311c.choose_partner(st, G, "nOther", "B")
    assert not used_B and n_same == 0 and base.scene.graph_id == "w"         # 同じ名札が無い：A に戻る（一番似ている世界の場面）
    base, _, _, used_B = v311c.choose_partner(st, G, "nT", "A")
    assert not used_B and base.scene.graph_id == "w"                          # 受信 A は名札を使わない
    base, mapping, _, _ = v311c.choose_partner(state(), G, "nT", "B")
    assert base is None and mapping is None                                    # 記憶が空


# ⑦ 名札：回数の割合で引く、初期値 1、自分の発話では足さない、報告からの誕生は受けた名札、同化で 1 足す
def test_07_tags_counts_sampling_init():
    setup()
    tags = {"n1": 3, "n2": 1}
    rng = Random(7)
    c = Counter(v311c.sample_tag(tags, rng) for _ in range(20000))
    assert abs(c["n1"] / 20000 - 0.75) < 0.02
    t = v311c.tag_update({}, "R1", False, None, lambda: "nNEW")
    assert t == {"R1": {"nNEW": 1}}                                         # 世界からの誕生：新しい名札 1
    t = v311c.tag_update(t, "R2", False, "nRECV", lambda: "x")
    assert t["R2"] == {"nRECV": 1}                                          # 報告からの誕生：受けた名札 1
    t = v311c.tag_update(t, "R1", True, "nRECV", lambda: "x")
    assert t["R1"] == {"nNEW": 1, "nRECV": 1}                               # 名札付きの束の同化：その名札に 1
    t2 = v311c.tag_update(t, "R1", True, None, lambda: "x")
    assert t2 == t                                                          # 世界の場面への同化：変えない
    d = definition(row(0, "fold", ("x", "y")))
    st = state([d], tags={"R_x": {"n1": 2}})
    pred = EdgePrediction(Relation("sme_projection__d9", "wrap", ("b", "c")))
    v311c.build_bundle(st, output_for(d, {"d0": "s1"}, pred), SCENE, 5)
    assert st.c_tags == {"R_x": {"n1": 2}}                                   # 自分の発話では足さない（状態は変わらない）


# ⑧ 名札表の費用：新しい定義・同化・定義を手放すときの増減
def test_08_tag_cost_changes():
    setup()
    b = v311c.CFG["b"]
    assert v311c.tag_cost({"n1": 1}) == v39.I(1) + b + v39.I(1)
    assert v311c.tag_cost({"n1": 1, "n2": 1}) - v311c.tag_cost({"n1": 1}) == v39.I(2) - v39.I(1) + b + v39.I(1)
    assert v311c.tag_cost({"n1": 2}) - v311c.tag_cost({"n1": 1}) == v39.I(2) - v39.I(1)
    d = definition(row(0, "fold", ("x", "y")), row(1, "lock", ("y", "z"), alive=False))
    hist = {("R_x", 0): {"fold": 1}}
    st = state([d], hist=hist, tags={"R_x": {"n1": 1}})
    L = v39.code_lengths(st.p_hat)
    assert v311c.tagged_total_bits(v39.total_bits, st, L) == v39.total_bits(st, L) + v311c.tag_cost({"n1": 1})
    # 最後の非 U の席（席 0 は F→H を経て H）を手放すと、定義ごと消える：解放量に名札表を足す
    st2, _ = v39._convert(st, "FH", "R_x", 0, 10) if False else (st, None)
    fake = [(0.5, "HU", "R_x", 0, 40, (0, 0, 0, 1)), (0.2, "FH", "R_x", 0, 5, (0, 0, 0, 1))]
    out = v311c.tagged_candidates(lambda *a: fake, st2, d, 10, L, 1)
    assert out[0][4] == 40 + v311c.tag_cost({"n1": 1}) and abs(out[0][0] - 0.5 * 40 / out[0][4]) < 1e-12
    assert out[1] == fake[1]                                               # F→H は定義を消さない：名札表は空かない


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
