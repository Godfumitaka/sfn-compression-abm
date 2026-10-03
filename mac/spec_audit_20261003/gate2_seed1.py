"""関門 2：小さな世界の検査（ChatGPT の五点、2026-10-01 未明の予約の委任書「手がかりの世界」の 4）。★ 模型は変えない。記録と検査だけ。
土台：~/sw_audit/swcommon.py（本番の tools/v3_run.py と同じ順で、照合・三答え・採点・U の照合・覚え直し・同点の並べ方・候補ごとの棄権を入れる）を、
  作業場所 sfn-compression-abm-shop のコードで読む（SW_TREE）。そのうえで --answer-gap（tools/answergap.py）を入れる（本番の腕と同じ）。
場面：お店の世界の生成器（abm.world.generate_trial を tools/shopworld.py build で包んだもの。種 tools/shop/U-011_seed_shop.json、世界 2、
  流れ "gate2"）で作る。甲（M1）・乙（M2）それぞれ、定義を作る場面（型ごとに 1 本目）と、答えさせる場面（2 本目）。シールは通常／例外を当てる。
定義：その状況の定義を作る場面の、構造の関係（abm.abstraction._structural_relation_ids：骨組み 15 本・シール・link）を全部 F の行にしたもの。
  履歴は F の名に 2 回（~/sw_audit の make_state と同じ）。p̂ はお店の辞書の全語に 16 回。
  1〜3 は通らなければ関門で止まる。4・5 は記録だけ。出力：<出力の .json>
使い方  SW_TREE=<作業場所> SW_FLAGS=u_struct,relearn_init,tie_struct,amb_local [SW_STRICT=1] python3.12 tools/shop/gate2.py <出力の .json>"""
import json
import os
import sys
from dataclasses import replace
from random import Random
from types import SimpleNamespace

sys.path.insert(0, os.path.expanduser("~/sw_audit"))
import swcommon as sw  # noqa: E402  （作業場所のコードを import し、差し替えを入れる）
W = sw.W
import abm.abstraction as ab  # noqa: E402
import abm.sme as sme  # noqa: E402
import abm.world as w  # noqa: E402
from abm.definition import Constituent, FrequencyTable, NamedDefinition  # noqa: E402
from abm.domains import Relation, RelationGraph, VerbatimTrace  # noqa: E402
from abm.seed import higher_order_predicates, load_seed  # noqa: E402
import answergap  # noqa: E402
import probeworld as pw  # noqa: E402
import shopworld as sh  # noqa: E402
import v39  # noqa: E402

B = sw.B
SEED = load_seed(os.path.join(W, "tools/shop/U-011_seed_shop.json"))
DICT = list(SEED.data["marginal"].keys()) + [p for p in sh.NEW_PREDICATES if p not in SEED.data["marginal"]]
HOP = frozenset(higher_order_predicates(SEED)) | {sh.ATTACH}
CONFIG = SimpleNamespace(threshold=0.0, tau_acc=0.67, local_lambda=1.0, higher_order_predicates=HOP, fill_selection="most_frequent",
                         verbatim_threshold=0.3842)
KW = dict(base_written_at=0, horizon=1740, pricing_rule="spec", refill_rule="one_per_slot", local_lambda=1.0)
WORLD = 2
RS = 1
answergap.install()
if os.environ.get("SW_STRICT"):
    # ★ --strict-pc（親子の並行連結、段 1 の (c) つき）を、ほかの候補の差し替えのあとに入れる（tools/v3_run.py と同じ順）
    import strictpc  # noqa: E402
    strictpc.install()


def setup(lam=0.3):
    sw.setup(T=1740, lam=lam)
    v39.CFG.update(D=len(DICT), dict_index={p: i for i, p in enumerate(DICT)})
    v39.CTX["config"] = CONFIG


def ptable():
    c = {p: 16 for p in DICT}
    return FrequencyTable(c, sum(c.values()), 0.1, frozenset(c))


# ---------------------------------------------------------------- 場面と定義
def base_trials():
    motifs = tuple(SEED.data["motif_structure"])
    got = {m: [] for m in motifs}
    i = 0
    while any(len(v) < 2 for v in got.values()):
        m = w._motif_for_trial(RS, i, motifs)
        if len(got[m]) < 2:
            got[m].append(w.generate_trial(RS, i, ("agent",), seed=SEED, holdout_include_second_order=True))
        i += 1
    return got


BASE = base_trials()
TYPES = {"甲": "M1", "乙": "M2"}
SITS = [(t, c) for t in ("甲", "乙") for c in ("n", "e")]


def scene(typ, cue, k):
    """k＝0：定義を作る場面、1：答えさせる場面。返り値：(完全な場面, 研究者の側の記録)"""
    tr = BASE[TYPES[typ]][k]
    out, info = sh.build(tr, RS, tr.trial, cue=cue, world=WORLD)
    return out.G_star, info


def door_hidden(typ, cue):
    G, info = scene(typ, cue, 1)
    return pw._partial(G, info["door_id"]), G, info


def make_def(name, typ, cue, alive=None):
    G, info = scene(typ, cue, 0)
    sids = ab._structural_relation_ids(G)
    rows = []
    for r in G.relations:
        if r.relation_id in sids:
            s = len(rows)
            rows.append(Constituent(s, 0, r, sw.PRICE, True if alive is None else alive(r, info)))
    return NamedDefinition(name, tuple(rows), len(rows), 0, 1), info


def slot_of(d, rid):
    return next(row.slot_index for row in d.constituents if row.relation.relation_id == rid)


def state_of(defs, hist=None):
    trace_scene = scene("甲", "n", 0)[0]
    return sw.make_state(defs, hist=hist, ph=ptable(), traces=[VerbatimTrace(0, trace_scene)])


def predict(state, sc):
    out, pend = v39.predict(SimpleNamespace(target_graph_partial=sc), state, CONFIG, Random(0))
    p = out.prediction
    return {"answer": getattr(getattr(p, "edge", None), "predicate", None),
            "args": list(p.edge.arguments) if hasattr(p, "edge") else None,
            "abstain": getattr(p, "reason", None), "R_used": out.trace.get("R_used"), "path": pend.prediction_path,
            "support": out.trace.get("support_at_adoption"), "m_live": out.trace.get("m_live")}


def supports(state, sc):
    """定義ごとの支持（写った F・H の席の数）と F＋H の席の数。tools/v39.py select_definition と同じ数え方。"""
    out = {}
    for d in state.definitions.values():
        n = v39.n_FH(d, state.slot_history)
        if n == 0:
            out[d.name] = [0, 0]
            continue
        _g, al = v39.map_v39(d, state.slot_history, sc)
        s = sum(1 for row in d.constituents if v39.seat_state(d, row, state.slot_history) != "U"
                and row.relation.relation_id in al.relation_mapping)
        out[d.name] = [s, n]
    return out


RES = {}


def check(cid, ok, detail, must):
    RES[cid] = {"must": must, "pass": bool(ok), "detail": detail}


# ---------------------------------------------------------------- 1：四状況それぞれ専用の定義で、世界 2 のドアに正しく答えるか
setup()
defs = {}
for t, c in SITS:
    d, info = make_def(f"D_{t}{c}", t, c)
    defs[(t, c)] = (d, info)
st = state_of([d for d, _ in defs.values()])
det = {}
ok1 = True
for t, c in SITS:
    part, G, info = door_hidden(t, c)
    want = sh.door_pred(WORLD, t, c)
    door = next(r for r in G.relations if r.relation_id == info["door_id"])
    got = predict(st, part)
    good = got["answer"] == want and got["args"] == list(door.arguments)
    ok1 &= good
    det[f"{t}・{c}"] = {"期待": want, **got, "正しい": good, "支持": supports(st, part)}
check("1 四状況の専用の定義で正しく答える", ok1, det, True)

# ---------------------------------------------------------------- 2：F の席の履歴に別の名が混ざっても、照合は固定の名だけを許す
setup()
d, info = defs[("甲", "n")]
ds = slot_of(d, info["door_id"])
hist = {(d.name, row.slot_index): {row.relation.predicate: 2} for row in d.constituents}
hist[(d.name, ds)] = {sh.X: 2, sh.Y: 3}
G1, i1 = scene("甲", "n", 1)
GX = G1
GY = RelationGraph(G1.graph_id, G1.entities, tuple(Relation(r.relation_id, sh.Y, r.arguments) if r.relation_id == i1["door_id"] else r
                                                   for r in G1.relations))
_g, alX = v39.map_v39(d, hist, GX)
_g, alY = v39.map_v39(d, hist, GY)
door_row = d.constituents[ds].relation.relation_id
mX, mY = alX.relation_mapping.get(door_row), alY.relation_mapping.get(door_row)
check("2 F の席は固定の名だけに合う", mX == i1["door_id"] and mY != i1["door_id"],
      {"ドアの席の状態": "F", "履歴": {sh.X: 2, sh.Y: 3}, "場面のドアが hold のときの写し先": mX, "場面のドアが hold_b のときの写し先": mY,
       "場面のドアの ID": i1["door_id"]}, True)

# ---------------------------------------------------------------- 3：H の席になった後、履歴にある名なら照合が許すか・話す答えはどう選ばれるか
setup()
dH = replace(d, constituents=tuple(replace(row, alive=False) if row.slot_index == ds else row for row in d.constituents))
histH = dict(hist)
histH[(d.name, ds)] = {sh.X: 2, sh.Y: 1}
_g, alX = v39.map_v39(dH, histH, GX)
_g, alY = v39.map_v39(dH, histH, GY)
mX, mY = alX.relation_mapping.get(door_row), alY.relation_mapping.get(door_row)
stH = state_of([dH], hist=histH)
ans = {}
for c in ("n", "e"):
    part, G, inf = door_hidden("甲", c)
    ans[f"甲・{c}（ドアを伏せた）"] = {**predict(stH, part), "表の答え": sh.door_pred(WORLD, "甲", c)}
check("3 H の席は履歴にある名に合う", mX == i1["door_id"] and mY == i1["door_id"],
      {"ドアの席の状態": "H", "履歴": {sh.X: 2, sh.Y: 1}, "場面のドアが hold のときの写し先": mX, "場面のドアが hold_b のときの写し先": mY,
       "場面のドアの ID": i1["door_id"], "話す答え（記録だけ）": ans}, True)

# ---------------------------------------------------------------- 4：通常と例外を混ぜた材料から定義が生まれるとき（記録だけ）
rec4 = {}
for t, (cb, ct) in (("甲", ("n", "e")), ("甲", ("e", "n")), ("乙", ("n", "e"))):
    setup()
    base, ib = scene(t, cb, 0)
    tgt_full, it = scene(t, ct, 1)
    tgt = pw._partial(tgt_full, BASE[TYPES[t]][1].held_out_edge.relation_id)
    st0 = state_of([])
    al = sme.map_graphs(base, tgt).alignment
    res = B.hypo_m1(st0, base, tgt, al, 5, None, KW)
    key = f"{t}：材料 {cb} → 場面 {ct}"
    if res is None:
        rec4[key] = {"生まれた": False}
        continue
    sa, R = res
    dd = sa.definitions[R]
    by = {r.relation_id: r for r in base.relations}
    sids = ab._structural_relation_ids(base)
    rows = {row.relation.relation_id: row for row in dd.constituents}
    rec4[key] = {"生まれた": True, "定義": R, "席の数": len(dd.constituents),
                 "構造の関係のうち落ちたもの": sorted(by[x].predicate for x in sids if x not in rows),
                 "ドアの席": ({"ある": True, "状態": v39.seat_state(dd, rows[ib["door_id"]], sa.slot_history),
                             "履歴": dict(v39.hist_counts(sa.slot_history.get((R, rows[ib["door_id"]].slot_index))))}
                            if ib["door_id"] in rows else {"ある": False}),
                 "シールの席": ({"ある": True, "状態": v39.seat_state(dd, rows[ib["sig_id"]], sa.slot_history)} if ib["sig_id"] in rows else {"ある": False}),
                 "link の席": ({"ある": True} if ib["link_id"] in rows else {"ある": False}),
                 "伏せた関係（場面）": BASE[TYPES[t]][1].held_out_edge.predicate}
RES["4 通常と例外を混ぜた材料からの誕生（記録だけ）"] = {"must": False, "detail": rec4}

# ---------------------------------------------------------------- 5：シールの席を手放した前後の、四状況の答えと点数（記録だけ）
rec5 = {}
for label in ("F（そのまま）", "H（シールの席を手放した：墓石・履歴あり）", "U（中身も忘れた：墓石・履歴なし）"):
    setup()
    ds_ = []
    hist5 = {}
    for (t, c), (d0, inf) in defs.items():
        s = slot_of(d0, inf["sig_id"])
        if label.startswith("F"):
            d1 = d0
        else:
            d1 = replace(d0, constituents=tuple(replace(row, alive=False) if row.slot_index == s else row for row in d0.constituents))
        for row in d0.constituents:
            if label.startswith("U") and row.slot_index == s:
                continue
            hist5[(d0.name, row.slot_index)] = {row.relation.predicate: 2}
        ds_.append(d1)
    st5 = state_of(ds_, hist=hist5)
    rec5[label] = {}
    for t, c in SITS:
        part, G, inf = door_hidden(t, c)
        rec5[label][f"{t}・{c}"] = {**predict(st5, part), "表の答え": sh.door_pred(WORLD, t, c), "支持": supports(st5, part)}
RES["5 シールの席を手放した前後（記録だけ）"] = {"must": False, "detail": rec5}

out = sys.argv[1]
json.dump(RES, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, v in RES.items():
    print(k, "必須" if v["must"] else "記録", "通った" if v.get("pass") else ("—" if not v["must"] else "通らない"))
