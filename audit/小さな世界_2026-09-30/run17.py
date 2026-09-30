"""小さな世界の追加 17 件（C21〜C37、control/v310hs_small_world_supplement_2026-09-30.zip の cases.json）を走らせる。
★ コードは読むだけ（SW_TREE の作業場所を import）。直さない。期待値を書き換えない。件ごと・λ ごとに初期状態から作り直す。
版の区別：SW_VERSION＝hs（今の版）・u（U の照合だけ直した版）・ur（照合＋覚え直しの初期の評価）。
  今の版では、U の照合の直しが前提の件（C23・C25）と提案 (a) の件（C26〜C28）は NOT_APPLICABLE（観察した値は残す）。
出力：SW_OUT（既定 ~/sw_audit/results17_<版>.json）。"""
import json
import math
import os
import random
import sys
from dataclasses import replace
from random import Random
from types import SimpleNamespace

sys.path.insert(0, "/Users/tatsu-admin/sw_audit")
from swcommon import *  # noqa
from swcommon import RES, case, _need, LAYOUT, reconcile_with_scene, SW_FLAGS  # noqa

VER = os.environ.get("SW_VERSION", "hs")
C = json.load(open("/Users/tatsu-admin/sw_audit2/v310hs_small_world_supplement/cases.json", encoding="utf-8"))
NE = {}
for line in open("/Users/tatsu-admin/sw_audit2/v310hs_small_world_supplement/numeric_expectations.tsv", encoding="utf-8").read().splitlines()[1:]:
    cid, q, v = line.split("\t")
    NE.setdefault(cid, {})[q] = v
TPL = {s["id"]: s for s in C["definition_templates"]["D_A"]["slots"]}
SLOT = {"s1": 0, "s2": 1, "s3": 2, "s4": 3, "s5": 4, "s6": 5}
t = 5


def num(cid, q):
    v = NE[cid][q]
    try:
        return int(v)
    except ValueError:
        return float(v)


def scene(name):
    s = C["scenes"][name]
    rels = tuple(Relation(r["id"], r["predicate"], tuple(r["arguments"])) for r in s["visible_relations"])
    h = s.get("researcher_only_hidden_relation")
    hid = Relation(h["id"], h["predicate"], tuple(h["arguments"])) if h else None
    return RelationGraph(name, tuple(Entity(o) for o in s["objects"]), rels), hid


def defn(name, slots, states, reg_count=1):
    """slots：使う席（s1〜s6）。states：{席: "F"|"H"|"U"}（無ければ F）。関係 ID は資料の s1〜s6、引数は d_a・d_b。"""
    rows = []
    for sid in slots:
        tp = TPL[sid]
        rows.append(Constituent(SLOT[sid], 0, Relation(sid, tp["predicate"], tuple(tp["arguments"])), PRICE,
                                states.get(sid, "F") == "F"))
    return NamedDefinition(name, tuple(rows), len(rows), 0, reg_count)


def hist_for(name, slots, states, over=None):
    h = {}
    for sid in slots:
        st = states.get(sid, "F")
        if st in ("F", "H"):
            h[(name, SLOT[sid])] = {TPL[sid]["predicate"]: 2}
    for sid, v in (over or {}).items():
        h[(name, SLOT[sid])] = v
    return h


def seats_for(name, slots, states, losses=None):
    out = {}
    for sid in slots:
        st = states.get(sid, "F")
        r = zero_rec(st, t)
        if losses and sid in losses:
            F, H, U = losses[sid]
            col = lambda v: (float(v),) * 16  # noqa: E731
            r = v39.SeatRec(0, st, t, t, v39.ZERO4, (col(F), col(H), col(U), col(1.0)))
        out[(name, SLOT[sid])] = r
    return out


def breakdown(d, st, sc):
    """名前の支持の内訳：可視の対応／未観測の位置への対応／対応なし（F・H の席）。U の席は別に数える。"""
    g, al = v39.map_v39(d, st.slot_history, sc)
    ids = {r.relation_id for r in sc.relations}
    vis = hidn = none = 0
    u_mapped = []
    for row in d.constituents:
        s = v39.seat_state(d, row, st.slot_history)
        m = al.relation_mapping.get(row.relation.relation_id)
        if s == "U":
            if m is not None:
                u_mapped.append(f"s{row.slot_index + 1}→{m}")
            continue
        if m is None:
            none += 1
        elif m in ids:
            vis += 1
        else:
            hidn += 1
    return {"visible": vis, "hidden_position": hidn, "unmatched": none, "support": vis + hidn,
            "denominator": v39.n_FH(d, st.slot_history), "required": _need(0.67, v39.n_FH(d, st.slot_history)),
            "mapping": dict(al.relation_mapping), "U_mapped": u_mapped}


def trace_of(sc):
    return [VerbatimTrace(0, sc)]


NA = "NOT_APPLICABLE"
setup()
# ---------------- C21
setup()
st_ = {"s1": "U"}
D = defn("D_S", ["s1", "s2", "s3"], st_)
st = make_state([D], hist=hist_for("D_S", ["s1", "s2", "s3"], st_), seats=seats_for("D_S", ["s1", "s2", "s3"], st_))
A_full, _ = scene("A_full")
bd = breakdown(D, st, A_full)
gate = bd["support"] >= bd["required"]
chk = [("今の版：支持 1", bd["support"] == num("C21", "current_support")), ("分母 2", bd["denominator"] == num("C21", "current_denominator")),
       ("必要 2", bd["required"] == num("C21", "required")), ("門を通らない", not gate)] if "u_struct" not in SW_FLAGS else \
      [("直した版：支持 2", bd["support"] == num("C21", "fixed_support")), ("分母 2", bd["denominator"] == num("C21", "fixed_denominator")),
       ("必要 2", bd["required"] == 2), ("門を通る", gate)]
case("C21", {"今の版": "支持 1/2・必要 2・通らない", "直した版": "支持 2/2・通る（U の s1 は構造の対応に入るが支持に入らない）"},
     {**bd, "gate": gate}, chk)

# ---------------- C22
setup()
A_hp, hidp = scene("A_hide_push")
st = make_state([D], hist=hist_for("D_S", ["s1", "s2", "s3"], st_), seats=seats_for("D_S", ["s1", "s2", "s3"], st_))
bd = breakdown(D, st, A_hp)
res = B.hypo_m1(st, A_full, A_hp, sme.map_graphs(A_full, A_hp).alignment, t, "D_S", KW)
sa = reconcile_with_scene(res[0], t, "m1", A_hp) if res else None
s1_state = v39.seat_state(sa.definitions["D_S"], sa.definitions["D_S"].constituents[0], sa.slot_history) if sa else None
s1_hist = dict(v39.hist_counts(sa.slot_history.get(("D_S", 0)))) if sa else None
case("C22", {"支持": "2/2・必要 2", "s1 の観察": 0, "s1": "U のまま・履歴なし"},
     {**bd, "s1_state_after_m1": s1_state, "s1_history_after_m1": s1_hist, "s1_rec_gen": sa.v39_seats[("D_S", 0)].gen if sa else None},
     [("支持 2", bd["support"] == 2), ("分母 2", bd["denominator"] == 2), ("必要 2", bd["required"] == 2),
      ("s1 観察 0", s1_hist == {}), ("s1 は U", s1_state == "U")])

# ---------------- C23（U の照合の直しが前提）
setup()
A_rw, _ = scene("A_replace_push_wrap")
st = make_state([D], hist=hist_for("D_S", ["s1", "s2", "s3"], st_), seats=seats_for("D_S", ["s1", "s2", "s3"], st_))
res = B.hypo_m1(st, A_rw, A_rw, sme.map_graphs(A_rw, A_rw).alignment, t, "D_S", KW)
sa = reconcile_with_scene(res[0], t, "m1", A_rw) if res else None
h1 = dict(v39.hist_counts(sa.slot_history.get(("D_S", 0)))) if sa else None
L = v39.code_lengths(st.p_hat)
act = {"s1_history_after": h1, "s1_state_after": v39.seat_state(sa.definitions["D_S"], sa.definitions["D_S"].constituents[0], sa.slot_history) if sa else None}
chk = [("新しい履歴 {wrap:1}", h1 == {"wrap": 1}), ("種類 1・合計 1", bool(h1) and len(h1) == 1 and sum(h1.values()) == 1),
       ("内容 10", bool(h1) and v39.hcost(h1, L) == 10)]
case("C23", {"直した版": "s1 に {wrap:1} だけ、内容 10"}, act, chk, "今の版では照合の直しが無いので NOT_APPLICABLE（観察した値だけ残す）。",
     status=NA if VER == "hs" else None)

# ---------------- C24
setup()
A_sp, _ = scene("A_replace_shared_parent")
st = make_state([D], hist=hist_for("D_S", ["s1", "s2", "s3"], st_), seats=seats_for("D_S", ["s1", "s2", "s3"], st_))
bd = breakdown(D, st, A_sp)
res = B.hypo_m1(st, A_sp, A_sp, sme.map_graphs(A_sp, A_sp).alignment, t, "D_S", KW)
sa = reconcile_with_scene(res[0], t, "m1", A_sp) if res else None
h1 = dict(v39.hist_counts(sa.slot_history.get(("D_S", 0)))) if sa else {}
case("C24", {"支持": "1/2・通らない", "s1 の観察": 0}, {**bd, "s1_history_after_m1": h1, "m1_registered": res is not None},
     [("支持 1", bd["support"] == num("C24", "support")), ("分母 2", bd["denominator"] == num("C24", "denominator")),
      ("通らない", bd["support"] < bd["required"]), ("s1 観察 0", h1 == {})])


# ---------------- C25〜C28（照合の直し・提案 (a) が前提）
def c25(lam, ph=None, tick=0):
    setup(lam=lam)
    st_ = {"s1": "U"}
    D = defn("D_S", ["s1", "s2", "s3"], st_, reg_count=2)
    st = make_state([D], hist=hist_for("D_S", ["s1", "s2", "s3"], st_),
                    seats=seats_for("D_S", ["s1", "s2", "s3"], st_, {"s2": (0, 100, 200), "s3": (0, 100, 200)}), ph=ph)
    L = v39.code_lengths(st.p_hat)
    b0 = v39.total_bits(st, L)
    res = B.hypo_m1(st, A_full, A_full, sme.map_graphs(A_full, A_full).alignment, t, "D_S", KW)
    sa = reconcile_with_scene(res[0], t, "m1", A_full)
    b1 = v39.total_bits(sa, L)
    r0 = sa.v39_seats.get(("D_S", 0))
    RF, RH, RU, _n = v39.rec_means(r0, t + tick) if r0 else (None,) * 4
    cs1 = [c for c in B.candidates(sa, sa.definitions["D_S"], t + tick, L, 1) if c[3] == 0]
    out, ev, *_ = v39.run_conversions(sa, t + tick)
    b2 = v39.total_bits(out, L)
    return {"bits_before": b0, "bits_after_m1": b1, "s1_history": dict(v39.hist_counts(sa.slot_history.get(("D_S", 0)))),
            "s1_gen": r0.gen if r0 else None, "s1_R_H": RH, "s1_R_U": RU,
            "s1_candidate": [[c[1], c[0], c[4]] for c in cs1], "content_bits": v39.hcost(sa.slot_history.get(("D_S", 0)), L) if ("D_S", 0) in sa.slot_history else None,
            "s1_state": v39.seat_state(sa.definitions["D_S"], sa.definitions["D_S"].constituents[0], sa.slot_history),
            "registration": sa.definitions["D_S"].assimilation_count, "bits_after_B": b2,
            "conversions": [[e.get("v39"), e.get("slot_index"), e.get("V")] for e in ev if e.get("v39")]}


a0 = c25(0.0)
a1 = c25(LAM)
case("C25", {"直した版": "194→208、H{push:1}、λ＝1/16 で 198・λ＝0 で 208"}, {"λ=0": a0, "λ=1/16": a1},
     [("before 194", a1["bits_before"] == 194), ("after m1 208", a1["bits_after_m1"] == 208), ("s1 H{push:1}", a1["s1_history"] == {"push": 1}),
      ("λ=1/16 → 198", a1["bits_after_B"] == 198), ("λ=0 → 208", a0["bits_after_B"] == 208)],
     "照合の直しとゼロの初期値が前提（v3.10u だけ）。今の版と、初期の評価を入れた版（v3.10ur）では NOT_APPLICABLE（観察した値だけ残す）。",
     status=NA if ("u_struct" not in SW_FLAGS or "relearn_init" in SW_FLAGS) else None)
if "relearn_init" in SW_FLAGS:
    a2 = c25(0.2)
    a5 = c25(0.5)
    case("C26", {q: NE["C26"][q] for q in NE["C26"]}, {"λ=0.2": a2, "λ=0.5": a5},
         [("損失 H0", abs(a2["s1_R_H"] - 0) < 1e-9), ("損失 U4", abs(a2["s1_R_U"] - 4) < 1e-9),
          ("空く量 10", bool(a2["s1_candidate"]) and a2["s1_candidate"][0][2] == 10),
          ("V 0.4", bool(a2["s1_candidate"]) and abs(a2["s1_candidate"][0][1] - 0.4) < 1e-9),
          ("λ.2 で H を残す 208", a2["bits_after_B"] == 208), ("λ.5 で H→U 198", a5["bits_after_B"] == 198)])
    a27 = c25(LAM, ph=ptable(push=32))
    case("C27", {q: NE["C27"][q] for q in NE["C27"]}, a27,
         [("内容 9", a27["content_bits"] == 9), ("損失 H0・U0", abs(a27["s1_R_H"]) < 1e-9 and abs(a27["s1_R_U"]) < 1e-9),
          ("V 0", bool(a27["s1_candidate"]) and a27["s1_candidate"][0][1] == 0.0),
          ("λ＝1/16 で同じ試行に U へ戻る", ["HU", 0] in [c[:2] for c in a27["conversions"]])])
    a28 = c25(0.2, tick=1)
    case("C28", {q: NE["C28"][q] for q in NE["C28"]}, a28,
         [("損失差 4w(1)", abs((a28["s1_R_U"] - a28["s1_R_H"]) - num("C28", "loss_difference_next")) < 1e-9),
          ("V 0.16208", bool(a28["s1_candidate"]) and abs(a28["s1_candidate"][0][1] - num("C28", "V_next")) < 1e-9),
          ("H→U で 198", a28["bits_after_B"] == 198)],
         "c25 と同じ初期状態から m1 を行い、B を内部の時計を 1 進めた時点（t＋1）で行った。新しい観察・開示・登録は足していない。")
else:
    for cid in ("C26", "C27", "C28"):
        case(cid, {"提案 (a)": "承認・実装されたときだけ"}, {"note": "提案 (a)（覚え直しの一観察で初期の評価をする）は、この版に無い"}, [],
             "提案 (a) は、この版に無い。", status=NA)


# ---------------- C29・C30（E の比べ）
def run_E2(defs, hist, base, target, lam):
    setup(lam=lam)
    st = make_state(defs, hist=hist)
    al = sme.map_graphs(base, target).alignment
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base, "alignment": al})
    snap = (dict(st.definitions), dict(st.slot_history), st.p_hat, dict(st.v39_seats))
    calls = []

    def inner(state, b, t_, a_, tr, **kw):
        calls.append(kw.get("name"))
        h = B.hypo_m1(state, b, t_, a_, tr, kw.get("name"), {k: v for k, v in kw.items() if k != "name"})
        return (reconcile_with_scene(h[0], tr, "m1", t_), {"R": h[1], "was_extension": kw.get("name") is not None}) if h else (state, None)

    out, reg = B.choose_and_register(st, base, target, al, t, KW, inner)
    rec = B.CTX.get("side")
    unchanged = snap == (dict(st.definitions), dict(st.slot_history), st.p_hat, dict(st.v39_seats))
    L = v39.code_lengths(st.p_hat)
    cm = {c[0]: c for c in rec["cands"]}
    ex_, nw = cm.get("D_A"), cm.get(None)
    N = 2
    K = lambda c, A: A + c[2] + lam * c[3]  # noqa: E731
    return {"x_rows": rec.get("x_rows"), "existing": {"r": ex_[2], "dC": ex_[3], "parts": ex_[5], "K": K(ex_, -math.log2(2 / 3))},
            "new": {"r": nw[2], "dC": nw[3], "parts": nw[5], "K": K(nw, -math.log2(1 / 3))}, "chosen": rec["chosen"], "calls": calls,
            "state_unchanged_by_E": unchanged, "bits_before": v39.total_bits(st, L), "bits_after": v39.total_bits(v39.ensure(out), L),
            "registration_after": (v39.ensure(out).definitions.get("D_A").assimilation_count if "D_A" in v39.ensure(out).definitions else None),
            "definitions_after": len(v39.ensure(out).definitions),
            "hist_after": {f"s{s + 1}": dict(v39.hist_counts(v39.ensure(out).slot_history.get(("D_A", s)))) for s in range(6)}}, out


B_full, _ = scene("B_full")
B_hp, hidb = scene("B_hide_push")
DA = defn("D_A", list(TPL), {}, reg_count=2)
HA = hist_for("D_A", list(TPL), {})
r29 = {lam: run_E2([DA], HA, B_full, B_full, lam)[0] for lam in (0.25, 0.5)}
case("C29", {q: NE["C29"][q] for q in NE["C29"]},
     {f"λ={k}": v for k, v in r29.items()},
     [("既存 r 44", r29[0.25]["existing"]["r"] == 44), ("新規 r 3", r29[0.25]["new"]["r"] == 3),
      ("既存 ΔC 6", r29[0.25]["existing"]["dC"] == 6), ("新規 ΔC 152", r29[0.25]["new"]["dC"] == 152),
      ("λ.25 既存 K", abs(r29[0.25]["existing"]["K"] - num("C29", "existing_lambda_025")) < 1e-9),
      ("λ.25 新規 K", abs(r29[0.25]["new"]["K"] - num("C29", "new_lambda_025")) < 1e-9), ("λ.25 新規を選ぶ", r29[0.25]["chosen"] is None),
      ("λ.5 既存 K", abs(r29[0.5]["existing"]["K"] - num("C29", "existing_lambda_050")) < 1e-9),
      ("λ.5 新規 K", abs(r29[0.5]["new"]["K"] - num("C29", "new_lambda_050")) < 1e-9), ("λ.5 既存を選ぶ", r29[0.5]["chosen"] == "D_A"),
      ("取消の未確認 3", r29[0.25]["existing"]["parts"]["取消の未確認"] == 3)],
     "K は side の丸め（6 桁）を使わず、A を式から、r と ΔC を整数のまま足した。")
r30 = {lam: run_E2([DA], HA, B_full, B_hp, lam)[0] for lam in (0.25, 0.5)}
# 新規の中身（構造・状態・親の無い fold の内容）を、仮の誕生から数える
setup()
st = make_state([DA], hist=HA)
h = B.hypo_m1(st, B_full, B_hp, sme.map_graphs(B_full, B_hp).alignment, t, None, KW)
L = v39.code_lengths(st.p_hat)
nd = h[0].definitions[h[1]]
new_struct = v39.structure_bits(nd)
fold_row = [r for r in nd.constituents if r.relation.predicate == "fold"]
fold_content = v39.seat_content_bits(nd, fold_row[0], "F", h[0].slot_history, L) if fold_row else None
C30X = {"existing_rewrite": 48, "existing_lambda_025": math.log2(3 / 2) + 48 + 0.25 * 4, "new_lambda_025": math.log2(3) + 19 + 0.25 * 95,
        "existing_lambda_050": math.log2(3 / 2) + 48 + 0.5 * 4, "new_lambda_050": math.log2(3) + 19 + 0.5 * 95}
# ★ ChatGPT の訂正（2026-09-30 夕方、アストラさん経由）：既存の書き直し 48 ビット。λ＝0.25 で既存 49.58・新規 44.33 → 新規、0.5 で既存 50.58・新規 68.08 → 既存
case("C30", {**{q: NE["C30"][q] for q in NE["C30"]}, "訂正": {k: round(v, 12) if isinstance(v, float) else v for k, v in C30X.items()}},
     {**{f"λ={k}": v for k, v in r30.items()}, "new_rows": [r.relation.predicate for r in nd.constituents], "new_structure": new_struct,
      "new_states": 2 * len(nd.constituents), "orphan_fold_content": fold_content,
      "new_histories": {r.relation.predicate: dict(v39.hist_counts(h[0].slot_history.get((h[1], r.slot_index)))) for r in nd.constituents}},
     [("x 5 本", r30[0.25]["x_rows"] == 5), ("新規 4 席", len(nd.constituents) == 4), ("既存 r 48（訂正）", r30[0.25]["existing"]["r"] == 48),
      ("新規 r 19", r30[0.25]["new"]["r"] == 19), ("既存 ΔC 4", r30[0.25]["existing"]["dC"] == 4), ("構造 42", new_struct == 42),
      ("状態 8", 2 * len(nd.constituents) == 8), ("親なし fold 内容 6", fold_content == 6), ("新規 ΔC 95", r30[0.25]["new"]["dC"] == 95),
      ("λ.25 既存 K 49.58（訂正）", abs(r30[0.25]["existing"]["K"] - C30X["existing_lambda_025"]) < 1e-9),
      ("λ.25 新規 K 44.33", abs(r30[0.25]["new"]["K"] - C30X["new_lambda_025"]) < 1e-9), ("λ.25 新規", r30[0.25]["chosen"] is None),
      ("λ.5 既存 K 50.58（訂正）", abs(r30[0.5]["existing"]["K"] - C30X["existing_lambda_050"]) < 1e-9),
      ("λ.5 新規 K 68.08", abs(r30[0.5]["new"]["K"] - C30X["new_lambda_050"]) < 1e-9), ("λ.5 既存", r30[0.5]["chosen"] == "D_A")])

# ---------------- C31（仮の適用に副作用が無い・実際の登録は一回）
a29 = r29[0.5]
a30 = r30[0.5]
case("C31", {q: NE["C31"][q] for q in NE["C31"]},
     {"C29_λ.5": {k: a29[k] for k in ("state_unchanged_by_E", "calls", "bits_before", "bits_after", "registration_after", "definitions_after", "hist_after")},
      "C30_λ.5": {k: a30[k] for k in ("state_unchanged_by_E", "calls", "bits_before", "bits_after", "registration_after", "definitions_after", "hist_after")}},
     [("仮の適用で実記憶は変わらない", a29["state_unchanged_by_E"] and a30["state_unchanged_by_E"]),
      ("実登録は一回", a29["calls"] == ["D_A"] and a30["calls"] == ["D_A"]),
      ("C29 279→285", a29["bits_before"] == 279 and a29["bits_after"] == 285), ("C30 279→283", a30["bits_after"] == 283),
      ("登録 2→3", a29["registration_after"] == 3 and a30["registration_after"] == 3), ("定義数 1", a29["definitions_after"] == 1 and a30["definitions_after"] == 1),
      ("C29 共有 3 履歴だけ 3", [a29["hist_after"][f"s{i}"] for i in range(1, 7)] == [{"push": 3}, {"fold": 3}, {"bind_s": 3}, {"cut": 2}, {"turn": 2}, {"bind_a": 2}]),
      ("C30 fold・bind_s だけ 3", [a30["hist_after"][f"s{i}"] for i in range(1, 7)] == [{"push": 2}, {"fold": 3}, {"bind_s": 3}, {"cut": 2}, {"turn": 2}, {"bind_a": 2}])],
     "実登録は、E が採った候補を hypo_m1 と同じ経路（abm.abstraction.m1＋--hist-role の包み）で一回呼び、v39.reconcile を通した。")


# ---------------- C32・C33・C34（B）
def c32_state():
    setup(lam=LAM)
    D = defn("D_A", list(TPL), {})
    return make_state([D], hist=hist_for("D_A", list(TPL), {}),
                      seats=seats_for("D_A", list(TPL), {}, {"s1": (0, 0, 100), "s2": (0, 0, 100), "s3": (0, 100, 200),
                                                             "s4": (0, 100, 200), "s5": (0, 100, 200), "s6": (0, 100, 200)}))


def c33_state():
    setup(lam=LAM)
    sts = {"s2": "H"}
    D = defn("D_A", list(TPL), sts)
    return make_state([D], hist=hist_for("D_A", list(TPL), sts),
                      seats=seats_for("D_A", list(TPL), sts, {"s1": (4, 4, 0), "s2": (0, 4, 4), "s3": (0, 100, 200),
                                                              "s4": (0, 100, 200), "s5": (0, 100, 200), "s6": (0, 100, 200)}))


def run_B(st, force_first=None):
    """変換の段を走らせ、各変換の直前の全候補と選んだものを残す（_pick を包んで記録するだけ。force_first があれば最初の同点をその候補にする）。"""
    log = []
    real = v39._pick

    def pick(cands, trial, k):
        c, nt = real(cands, trial, k)
        if force_first is not None and k == 0 and nt > 1:
            c = next(x for x in cands if (x[1], x[3]) == force_first)
        log.append({"k": k, "候補": sorted([[x[1], f"s{x[3] + 1}", round(x[0], 12), x[4]] for x in cands], key=lambda z: (z[2], z[1])),
                    "選んだ": [c[1], f"s{c[3] + 1}"], "同点": nt})
        return c, nt

    v39._pick = pick
    try:
        L = v39.code_lengths(st.p_hat)
        b0 = v39.total_bits(st, L)
        out, ev, *_ = v39.run_conversions(st, t)
        b1 = v39.total_bits(out, L)
    finally:
        v39._pick = real
    after = sorted([[c[1], f"s{c[3] + 1}", round(c[0], 12), c[4]] for d in out.definitions.values()
                    for c in B.candidates(out, d, t, L, len(out.definitions))], key=lambda z: (z[2], z[1]))
    return {"bits_before": b0, "bits_after": b1, "order": [[e["v39"], f"s{e['slot_index'] + 1}"] for e in ev if e.get("v39") in ("FH", "HU")],
            "freed": sum(e["dC"] for e in ev if e.get("v39") in ("FH", "HU")),
            "log（各変換の直前の、λ 未満の候補＝_pick に渡るもの）": log, "log": log, "段の後の全候補": after}


g0 = random.getstate()
r32 = run_B(c32_state())
first = r32["log"][0]
case("C32", {q: NE["C32"][q] for q in NE["C32"]}, r32,
     [("最初の同点 {s1 F→H, s2 F→H} 点 0", sorted(c[1] for c in first["候補"] if c[2] == 0.0) == ["s1", "s2"] and first["同点"] == 2),
      ("空く量 3", all(c[3] == 3 for c in first["候補"] if c[2] == 0.0)),
      ("順序は二つのどちらか", r32["order"] in ([["FH", "s1"], ["FH", "s2"]], [["FH", "s2"], ["FH", "s1"]])),
      ("279→273", r32["bits_before"] == 279 and r32["bits_after"] == 273),
      ("s1・s2 を H にしたあとの H→U の点 10（変換しない）", sorted(c[1] for c in r32["段の後の全候補"] if c[0] == "HU" and abs(c[2] - 10) < 1e-9) == ["s1", "s2"] and all(o[0] == "FH" for o in r32["order"]))])
r33 = run_B(c33_state())
r33a = run_B(c33_state(), force_first=("FH", 0))
r33b = run_B(c33_state(), force_first=("HU", 1))
okset = ([["FH", "s1"], ["HU", "s1"], ["HU", "s2"]], [["HU", "s2"], ["FH", "s1"], ["HU", "s1"]])
case("C33", {q: NE["C33"][q] for q in NE["C33"]}, {"本番の選び方": r33, "最初に s1 F→H を指定": r33a, "最初に s2 H→U を指定": r33b},
     [("最初の同点 {s1 F→H, s2 H→U} 点 0", sorted([c[0], c[1]] for c in r33["log"][0]["候補"] if c[2] == 0.0) == [["FH", "s1"], ["HU", "s2"]]),
      ("順序が許される二つのどちらか", r33["order"] in okset), ("指定 (i)", r33a["order"] == okset[0]), ("指定 (ii)", r33b["order"] == okset[1]),
      ("s1 F→H の直後の s1 H→U の点 −0.4", any(c[0] == "HU" and c[1] == "s1" and abs(c[2] + 0.4) < 1e-9 for c in r33a["log"][1]["候補"])),
      ("解放 23・276→253", r33["freed"] == 23 and r33["bits_before"] == 276 and r33["bits_after"] == 253)])
same = all(run_B(c32_state())["order"] == r32["order"] for _ in range(3)) and all(run_B(c33_state())["order"] == r33["order"] for _ in range(3))
g1 = random.getstate()
# 種 101・試行 5：v39.CFG の seed を変えて同じ状態を繰り返す
def with_seed(fn):
    st = fn()
    v39.CFG["seed"] = 101
    return run_B(st)
s101 = [with_seed(c33_state)["order"] for _ in range(3)]
case("C34", {q: NE["C34"][q] for q in NE["C34"]},
     {"同じ鍵で繰り返して同じ順": same, "種 101・試行 5 の順（3 回）": s101, "random（世界の乱数と同じ Python の random）の状態が B の前後で同じ": g0 == g1},
     [("繰り返して同じ", same and len({json.dumps(x) for x in s101}) == 1), ("世界・開示の乱数の状態を変えない", g0 == g1)],
     "B の同点の乱数は tools/v39.py:859-866 _pick が sha256(種・試行・変換番号) から作る Random で、Python の random の状態も世界の乱数（abm/loop.py の Random(_rng_seed(...)) と world の u_coins）も使わない。ここでは random.getstate() の前後の一致を見た。")


# ---------------- C35〜C37（予測と役割の採点）
def c3x(D, hist, sc, hidden, extra=None):
    setup()
    st = make_state([D], hist=hist, traces=[VerbatimTrace(0, scene("A_full")[0])])
    bd = breakdown(D, st, sc)
    out, a, ans = predict(st, sc)
    inc = {}
    if ans:
        _, inc, _ = score(st, ans, hidden)
    fill_src = None
    if a["path"] in ("filling_live", "filling_tombstone"):
        fl = v39.CTX.get("fill_states") or ()
        fill_src = fl[0] if fl else None
    return st, bd, a, inc, fill_src


sts = {"s1": "H", "s4": "U", "s5": "U", "s6": "U"}
D35 = defn("D_A", list(TPL), sts)
st, bd, a, inc, src = c3x(D35, hist_for("D_A", list(TPL), sts, {"s1": {"push": 2}}), B_hp, hidb)
d10 = a["path"] in ("filling_live", "filling_tombstone") and a["answer"] == "push(ba,bb)"
case("C35", {q: NE["C35"][q] for q in NE["C35"]},
     {**bd, "R_used": a["R_used"], "answer": a["answer"], "path": a["path"], "abstain_reason": a["abstain_reason"], "fill_seat_state": src,
      "answers": a["answers"], "role_targets": a["role_targets"], "loss_increment": inc,
      "D-10 の条件（穴埋めの当たり＋開示）": d10},
     [("支持 3/3・必要 3", bd["support"] == 3 and bd["denominator"] == 3 and bd["required"] == 3),
      ("内訳 可視2・未観測1・なし0", (bd["visible"], bd["hidden_position"], bd["unmatched"]) == (2, 1, 0)),
      ("H から push(ba,bb) を答える", a["answer"] == "push(ba,bb)" and src == "H"),
      ("s1 の届け先 b1", (a["role_targets"] or {}).get(0) == "b1"),
      ("損失 H0・U4、s1 だけ", inc == {"s1": {"F": 0.0, "H": 0.0, "U": 4.0}}),
      ("当たりの穴埋めで履歴 2→3（D-10 の条件）", d10)],
     "D-10（tools/v38.py:140-160）は会計の包みの中なので、ここでは条件（穴埋めの答えが当たりで開示あり）が成り立つかだけを見た。")
B_hw, hidw = scene("B_hide_wrap")
sts = {"s4": "H", "s5": "U", "s6": "U"}
D36 = defn("D_A", list(TPL), sts)
st, bd, a, inc, src = c3x(D36, hist_for("D_A", list(TPL), sts, {"s4": {"cut": 2}}), B_hw, hidw)
case("C36", {q: NE["C36"][q] for q in NE["C36"]},
     {**bd, "R_used": a["R_used"], "answer": a["answer"], "path": a["path"], "abstain_reason": a["abstain_reason"], "fill_seat_state": src,
      "answers": a["answers"], "role_targets": a["role_targets"], "role_why": a["role_why"], "loss_increment": inc},
     [("支持 3/4・必要 3", bd["support"] == 3 and bd["denominator"] == 4 and bd["required"] == 3),
      ("内訳 可視3・未観測0・なし1", (bd["visible"], bd["hidden_position"], bd["unmatched"]) == (3, 0, 1)),
      ("H から cut(ba,bb) を答える（世界で外れ）", a["answer"] == "cut(ba,bb)" and src == "H"),
      ("s4 の届け先なし", (a["role_targets"] or {}).get(3) is None),
      ("役割採点の加算 0", inc == {})])
sts = {"s1": "H"}
D37 = defn("D_S", ["s1", "s2", "s3"], sts)
st, bd, a, inc, src = c3x(D37, hist_for("D_S", ["s1", "s2", "s3"], sts, {"s1": {"cut": 2}}), B_hp, hidb)
case("C37", {q: NE["C37"][q] for q in NE["C37"]},
     {**bd, "R_used": a["R_used"], "answer": a["answer"], "path": a["path"], "abstain_reason": a["abstain_reason"], "fill_seat_state": src,
      "answers": a["answers"], "role_targets": a["role_targets"], "loss_increment": inc},
     [("支持 3/3・必要 3", bd["support"] == 3 and bd["denominator"] == 3 and bd["required"] == 3),
      ("内訳 可視2・未観測1・なし0", (bd["visible"], bd["hidden_position"], bd["unmatched"]) == (2, 1, 0)),
      ("H から cut(ba,bb) を答える（外れ）", a["answer"] == "cut(ba,bb)" and src == "H"),
      ("損失 H4・U4、s1 だけ", inc == {"s1": {"F": 0.0, "H": 4.0, "U": 4.0}})])

json.dump(RES, open(os.environ.get("SW_OUT", f"/Users/tatsu-admin/sw_audit/results17_{VER}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print("PASS", sum(r["status"] == "PASS" for r in RES), "DIFFERENCE", sum(r["status"] == "DIFFERENCE" for r in RES),
      "NOT_APPLICABLE", sum(r["status"] == "NOT_APPLICABLE" for r in RES))
