"""前の 20 件を、ERRATA.txt の訂正後の期待値で走らせる（SW_TREE で版を選ぶ）。本体は run_cases.py と同じ。"""
import sys, os
sys.path.insert(0, "/Users/tatsu-admin/sw_audit")
from swcommon import *  # noqa
from swcommon import RES, case, _need, _ORIG_M1


def exp(cid):
    return next(c for c in json.load(open("/Users/tatsu-admin/sw_audit/v310hs_small_world/local_expectations.json")) if c["id"] == cid)["expected"]


t = 10
# ---------------- C01
setup()
D = make_def("D_A")
scene, hid = make_scene("A", "push")
st = make_state([D], traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
out, a, ans = predict(st, scene)
seats, inc, _ = score(st, ans, hid)
case("C01", exp("C01"), {**a, "loss_increment": inc},
     [("selected", a["R_used"] == "D_A"), ("support 6（訂正）", a["support"] == 6), ("denominator 6", a["denominator"] == 6),
      ("required 5", a["required"] == 5), ("gate", a["R_used"] is not None), ("answer push(a,b)", a["answer"] == "push(a,b)"),
      ("source F_projection", a["path"] == "projection"),
      ("role_target s1 only", [s for s, c in (a["role_targets"] or {}).items() if c == hid.relation_id] == [0]),
      ("loss s1 (0,0,4)", inc == {"s1": {"F": 0.0, "H": 0.0, "U": 4.0}})])

# ---------------- C02（開示なし：tools/v39.py:1003-1007 は開示のときだけ score_answers を呼ぶ）
setup()
st = make_state([D], traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
out, a, ans = predict(st, scene)
received = None     # coin.f_fired＝False のとき v39.update_accounting が渡すもの
inc = {}
if received is not None:
    _, inc, _ = score(st, ans, received)
case("C02", exp("C02"), {"score_called": received is not None, "loss_increment": inc},
     [("score increment all 0", inc == {})], "採点の関数は開示のときだけ呼ばれる（tools/v39.py:1003-1007 の条件をそのまま当てた）。")

# ---------------- C03
setup()
DB = make_def("D_B", "B")
sceneB, hidB = make_scene("B", "wrap")
st = make_state([DB], traces=[VerbatimTrace(0, make_scene("B", None, "full")[0])])
out, a, ans = predict(st, sceneB)
seats, inc, _ = score(st, ans, hidB)
case("C03", exp("C03"), {**a, "loss_increment": inc},
     [("selected", a["R_used"] == "D_B"), ("support 6（訂正）", a["support"] == 6), ("denominator 6", a["denominator"] == 6),
      ("required 5", a["required"] == 5), ("answer wrap(a,b)", a["answer"] == "wrap(a,b)"),
      ("loss s4 (0,0,4)", inc == {"s4": {"F": 0.0, "H": 0.0, "U": 4.0}})])

# ---------------- C04
setup()
DA = make_def("D_A")
st = make_state([DA, DB], traces=[VerbatimTrace(0, make_scene("B", None, "full")[0])])
sel = v39.select_definition(st, sceneB, CONFIG)
ratios = {}
for d in (DA, DB):
    g, al = v39.map_v39(d, st.slot_history, sceneB)
    s_ = sum(1 for row in d.constituents if row.relation.relation_id in al.relation_mapping)
    ratios[d.name] = f"{s_}/{v39.n_FH(d, st.slot_history)}"
out, a, ans = predict(st, sceneB)
seats, inc, _ = score(st, ans, hidB)
recips = sorted({k.split("|")[0] for k in []})
case("C04", exp("C04"), {"support_ratios": ratios, **a, "loss_increment": inc, "score_recipients": sorted({ans["R"]}) if ans else []},
     [("ratio D_A 3/6", ratios["D_A"] == "3/6"), ("ratio D_B 6/6（訂正）", ratios["D_B"] == "6/6"), ("selected D_B", a["R_used"] == "D_B"),
      ("answer wrap(a,b)", a["answer"] == "wrap(a,b)"), ("score only D_B", (ans or {}).get("R") == "D_B")])

# ---------------- C05
setup()
DS = make_def("D_S", "A", slots=[0, 1, 2])
sceneC, hidC = make_scene("A", "cut")
st = make_state([DS], traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
out, a, ans = predict(st, sceneC)
seats, inc, _ = score(st, ans, hidC) if ans else (None, {}, None)
case("C05", exp("C05"), {**a, "loss_increment": inc},
     [("selected D_S", a["R_used"] == "D_S"), ("support 3", a["support"] == 3), ("denominator 3", a["denominator"] == 3),
      ("required 3", a["required"] == 3), ("answer abstain", a["answer"] == "abstain"),
      ("score for cut 0", inc == {})])

# ---------------- C06
setup()
st = make_state([DS], traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
out, a, ans = predict(st, scene)
g, al = v39.map_v39(DS, st.slot_history, scene)
cand_support = sum(1 for row in DS.constituents if row.relation.relation_id in al.relation_mapping)
seats, inc, _ = score(st, ans, hid) if ans else (None, {}, None)
case("C06", exp("C06"), {**a, "candidate_support": cand_support, "loss_increment": inc},
     [("support 3（訂正）", cand_support == 3), ("required 3", _need(0.67, 3) == 3), ("gate true（訂正）", a["R_used"] == "D_S"),
      ("answer push(a,b)（訂正）", a["answer"] == "push(a,b)"), ("loss s1 (0,0,4)（訂正）", inc == {"s1": {"F": 0.0, "H": 0.0, "U": 4.0}})])

# ---------------- C07
setup()
st = make_state([DA], traces=[VerbatimTrace(0, make_scene("B", None, "full")[0])])
out, a, ans = predict(st, sceneB)
g, al = v39.map_v39(DA, st.slot_history, sceneB)
cand_support = sum(1 for row in DA.constituents if row.relation.relation_id in al.relation_mapping)
case("C07", exp("C07"), {**a, "candidate_support": cand_support},
     [("support 3", cand_support == 3), ("required 5", _need(0.67, 6) == 5), ("gate false", a["R_used"] is None),
      ("answer abstain", a["answer"] == "abstain")])

# ---------------- C08
setup()
DAu = make_def("D_A", alive={3: False, 4: False, 5: False})
histu = {("D_A", s): {LAYOUT["A"][s]: 2} for s in (0, 1, 2)}
st = make_state([DAu], hist=histu, traces=[VerbatimTrace(0, make_scene("B", None, "full")[0])])
out, a, ans = predict(st, sceneB)
case("C08", exp("C08"), a,
     [("support 3", a["support"] == 3), ("denominator 3", a["denominator"] == 3), ("required 3", a["required"] == 3),
      ("gate", a["R_used"] == "D_A"), ("answer abstain", a["answer"] == "abstain")])

# ---------------- C09（m1 の履歴だけ。場面は提示 5 本。name＝D_A の同化。価格は p_hat 固定）
setup()
fullA = make_scene("A", None, "full", tag="b")[0]
st = make_state([make_def("D_A", reg_count=1)])
L = v39.code_lengths(st.p_hat)
C0 = v39.total_bits(st, L)
al0 = sme.map_graphs(fullA, scene).alignment
res = B.hypo_m1(st, fullA, scene, al0, 5, "D_A", KW)
sa = res[0]
C1 = v39.total_bits(sa, L)
hist_after = {f"s{s + 1}": dict(v39.hist_counts(sa.slot_history.get(("D_A", s)))) for s in range(6)}
ex = exp("C09")
case("C09", ex, {"history_after": hist_after, "memory_before": C0, "memory_after": C1, "memory_delta": C1 - C0,
                 "definition_alignment_used": "m1 の中の map_graphs（abm/abstraction.py:125-129）。親の対応は外から与えられない"},
     [("history", hist_after == ex["history_after"]), ("memory_before 279", C0 == 279), ("memory_after 289", C1 == 289),
      ("delta 10", C1 - C0 == 10)])

# ---------------- C10（親の無い push の席。push は見えている）
setup()
Dor = make_def("D_O", "A", slots=[0, 3, 4, 5])      # push（親なし）・cut・turn・bind_a(cut,turn)
st = make_state([Dor])
sceneF = make_scene("A", None, "sc")[0]
res = B.hypo_m1(st, fullA, sceneF, sme.map_graphs(fullA, sceneF).alignment, 5, "D_O", KW)
h_push_before = v39.hist_counts(st.slot_history.get(("D_O", 0)))
h_push_after = v39.hist_counts(res[0].slot_history.get(("D_O", 0)))
g, alD = v39.map_v39(Dor, st.slot_history, sceneF)
cid, why = B.role_target(Dor, Dor.constituents[0], alD, sceneF)
ans_items = v39.three_answers(Dor, alD, st, CONFIG, sceneF)
ansD = {"R": "D_O", "items": ans_items}
_, inc, _ = score(st, ansD, Relation("q_push", "push", ("a", "b")))
case("C10", exp("C10"), {"history_increment_for_push": sum(h_push_after.values()) - sum(h_push_before.values()),
                         "role_target": cid, "role_why": why, "score_increment": inc},
     [("history +0", sum(h_push_after.values()) - sum(h_push_before.values()) == 0), ("role_target None", cid is None),
      ("score push 0", "s1" not in inc)])

# ---------------- C11
setup()
D11 = make_def("D_A", preds={0: "wrap"})
hist11 = {("D_A", s): {LAYOUT["A"][s]: 2} for s in range(6)}
hist11[("D_A", 0)] = {"push": 2, "wrap": 1}
st = make_state([D11], hist=hist11, traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
out, a, ans = predict(st, scene)
seats, inc, _ = score(st, ans, hid)
st2 = replace(st, v39_seats=seats)
L = v39.code_lengths(st2.p_hat)
cands = {c[1]: c for c in B.candidates(st2, D11, t, L, 1) if c[3] == 0}
hb = v39.hcost(hist11[("D_A", 0)], L)
fb = v39.fixed_spec_bits("wrap", hist11[("D_A", 0)], L)
# 変換：席 s1 だけを見る（ほかの席の B は、この件の外：local_expectations の注）。
#   F→H の点が λ 未満なら v39._convert で F→H し、その後の s1 の H→U の点を candidates で見て λ と比べる。
out_all, ev_all, *_ = v39.run_conversions(st2, t)        # 参考：定義全体の変換の段（ほかの席も動く）
conv_s1 = []
V_FH = cands["FH"][0] if "FH" in cands else None
st3 = st2
if V_FH is not None and V_FH < LAM:
    conv_s1.append("FH")
    st3, _ = v39._convert(st2, "FH", "D_A", 0, t)
c3 = [c for c in B.candidates(st3, st3.definitions["D_A"], t, L, 1) if c[3] == 0]
V_HU = c3[0][0] if c3 else None
if V_HU is not None and V_HU < LAM:
    conv_s1.append("HU")
ex = exp("C11")
case("C11", ex, {"local_answers": a["answers"].get(0) if a["answers"] else None, "loss_increment": inc.get("s1"),
                 "history_bits": hb, "fixed_pointer_bits": fb, "V_FH": V_FH, "V_HU_after_FH": V_HU, "conversions_s1": conv_s1,
                 "R_used": a["R_used"], "answer": a["answer"],
                 "参考_定義全体の変換の段": [[e.get("v39"), e.get("slot_index"), e.get("V")] for e in ev_all if e.get("v39")]},
     [("answers F wrap/H push/U None", (a["answers"] or {}).get(0) == {"F": "wrap", "H": "push", "U": None}),
      ("loss (4,0,4)", inc.get("s1") == {"F": 4.0, "H": 0.0, "U": 4.0}), ("history_bits 17", hb == 17), ("pointer 3", fb == 3),
      ("V_FH -4/3", V_FH is not None and abs(V_FH - (-4 / 3)) < 1e-9), ("V_HU 4/17", V_HU is not None and abs(V_HU - 4 / 17) < 1e-9),
      ("F->H, H remains", conv_s1 == ["FH"])])

# ---------------- C12
setup()
ph = ptable(push=32)
D12 = make_def("D_A", alive={0: False})
hist12 = {("D_A", s): {LAYOUT["A"][s]: 2} for s in range(1, 6)}
hist12[("D_A", 0)] = {"push": 1, "wrap": 3}
st = make_state([D12], hist=hist12, ph=ph, traces=[VerbatimTrace(0, make_scene("A", None, "full")[0])])
L = v39.code_lengths(ph)
g, al12 = v39.map_v39(D12, hist12, scene)
row0 = D12.constituents[0]
hA, _ = v39.h_answer(D12, row0, hist12, ph, 1.0, HOP)
uA, _ = v39.u_answer(D12, row0, scene, ph, HOP)
ans12 = {"R": "D_A", "items": v39.three_answers(D12, al12, st, CONFIG, scene)}
seats, inc, _ = score(st, ans12, hid)
st2 = replace(st, v39_seats=seats)
cands = {c[1]: c for c in B.candidates(st2, D12, t, L, 1) if c[3] == 0}
conv_s1 = [("HU", cands["HU"][4])] if "HU" in cands and cands["HU"][0] < LAM else []
ex = exp("C12")
case("C12", ex, {"L_push": L["push"], "L_wrap": L["wrap"], "local_answers": {"H": hA, "U": uA}, "loss_increment": inc.get("s1"),
                 "history_bits": v39.hcost(hist12[("D_A", 0)], L), "V_HU": cands.get("HU", [None])[0], "conversions_s1": conv_s1},
     [("L_push 3", L["push"] == 3), ("L_wrap 4", L["wrap"] == 4), ("H wrap", hA == "wrap"), ("U push", uA == "push"),
      ("loss H3 U0", inc.get("s1") == {"F": 0.0, "H": 3.0, "U": 0.0}), ("history_bits 18", v39.hcost(hist12[("D_A", 0)], L) == 18),
      ("V_HU -1/6", abs(cands["HU"][0] + 1 / 6) < 1e-9 if "HU" in cands else False), ("H->U frees 18", conv_s1 == [("HU", 18)])])

# ---------------- C13（誕生の初期成績：B.init_rec を、土台の年齢 1 で）
def c13(T):
    setup(T=T)
    D13 = make_def("D_X", "A", slots=[0, 1, 2])
    hist13 = {("D_X", 0): {"push": 2}, ("D_X", 1): {"fold": 2}, ("D_X", 2): {"bind_s": 2}}
    st = make_state([D13], hist=hist13)
    v39.CTX["births_rec"] = []
    base13 = make_scene("A", None, "base", tag="b")[0]
    rec = B.init_rec(D13, D13.constituents[0], st, base13, make_scene("A", None, "cur")[0], t, 1, CONFIG)
    st = replace(st, v39_seats={("D_X", 0): rec, ("D_X", 1): zero_rec(), ("D_X", 2): zero_rec()})
    L = v39.code_lengths(st.p_hat)
    RF, RH, RU, n = v39.rec_means(rec, t)
    cs = {c[1]: c[0] for c in B.candidates(st, D13, t, L, 1) if c[3] == 0}
    RF1, RH1, RU1, _ = v39.rec_means(rec, t + 1)
    return {"R_F": RF, "R_H": RH, "R_U": RU, "V_FH": cs.get("FH"), "fixed_pointer_bits": v39.fixed_spec_bits("push", {"push": 2}, L),
            "after_one_tick": {"R_H": RH1, "R_U": RU1}, "births_rec": v39.CTX["births_rec"][:1]}
a16 = c13(T_PLAN)
a1740 = c13(1740)
ex = exp("C13")
case("C13", ex, {f"T={T_PLAN}": a16, "T=1740": a1740},
     [("R_F 0", a16["R_F"] == 0), ("R_H 0", a16["R_H"] == 0), (f"R_U 5.620777114088078 (T={T_PLAN}、訂正)", abs(a16["R_U"] - 5.620777114088078) < 1e-9),
      ("V_FH 0", a16["V_FH"] == 0), (f"after tick R_U 2.691317711067378 (T={T_PLAN}、訂正)", abs(a16["after_one_tick"]["R_U"] - 2.691317711067378) < 1e-9)],
     "V_HU（F→H の後の H→U の点）は、同じ席を F→H したあとに candidates で見る（下の actual に足す）。")
for T_, key in ((T_PLAN, f"T={T_PLAN}"), (1740, "T=1740")):
    setup(T=T_)
    D13 = make_def("D_X", "A", slots=[0, 1, 2])
    hist13 = {("D_X", 0): {"push": 2}, ("D_X", 1): {"fold": 2}, ("D_X", 2): {"bind_s": 2}}
    st = make_state([D13], hist=hist13)
    v39.CTX["births_rec"] = []
    rec = B.init_rec(D13, D13.constituents[0], st, make_scene("A", None, "base", tag="b")[0], make_scene("A", None, "cur")[0], t, 1, CONFIG)
    st = replace(st, v39_seats={("D_X", 0): rec, ("D_X", 1): zero_rec(), ("D_X", 2): zero_rec()})
    st, _ = v39._convert(st, "FH", "D_X", 0, t)
    L = v39.code_lengths(st.p_hat)
    cs = [c[0] for c in B.candidates(st, st.definitions["D_X"], t, L, 1) if c[3] == 0]
    RES[-1]["actual"][key]["V_HU_after_FH"] = cs[0] if cs else None
RES[-1]["checks"].append([f"V_HU 0.5620777114088078 (T={T_PLAN}、訂正)", bool(abs((RES[-1]["actual"][f"T={T_PLAN}"]["V_HU_after_FH"] or 0) - 0.5620777114088078) < 1e-9)])
RES[-1]["pass"] = all(v for _, v in RES[-1]["checks"])

# ---------------- C14
setup()
st = make_state([make_def("D_A")])
L = v39.code_lengths(st.p_hat)
tot = v39.total_bits(st, L)
parts = {"global_table": v39.global_table_bits(st.p_hat), "definition_count": v39.I(1), "structure": v39.structure_bits(st.definitions["D_A"])}
s1, _ = v39._convert(st, "FH", "D_A", 0, t)
t1 = v39.total_bits(s1, L)
s2, _ = v39._convert(s1, "HU", "D_A", 0, t)
t2 = v39.total_bits(s2, L)
s6 = st
for s in range(6):
    s6, _ = v39._convert(s6, "FH", "D_A", s, t)
t6 = v39.total_bits(s6, L)
case("C14", exp("C14"), {**parts, "total": tot, "one_F_to_H_total": t1, "then_same_H_to_U_total": t2, "all_six_H_total": t6},
     [("global 124", parts["global_table"] == 124), ("count 3", parts["definition_count"] == 3), ("structure 62", parts["structure"] == 62),
      ("total 279", tot == 279), ("FH 276", t1 == 276), ("HU 266", t2 == 266), ("all H 261", t6 == 261)])

# ---------------- C15
setup()
D15 = make_def("D_A", alive={s: False for s in range(6)})
hist15 = {("D_A", 5): {"bind_a": 2}}
rec15 = v39.rec_add(zero_rec("H"), t, (0.0, 0.0, 4.0, 1.0))
seats15 = {("D_A", s): zero_rec("U") for s in range(5)}
seats15[("D_A", 5)] = rec15
st = make_state([D15], hist=hist15, seats=seats15)
L = v39.code_lengths(st.p_hat)
before = v39.total_bits(st, L)
c = B.candidates(st, D15, t, L, 1)
out_c, ev, *_ = v39.run_conversions(st, t)
after = v39.total_bits(out_c, L)
case("C15", exp("C15"), {"memory_before": before, "memory_after": after, "bits_freed": c[0][4] if c else None, "V_HU": c[0][0] if c else None,
                         "retired": "D_A" not in out_c.definitions, "events": [e.get("v39") for e in ev],
                         "global_counts_preserved": out_c.p_hat == st.p_hat},
     [("before 211", before == 211), ("after 125", after == 125), ("freed 86", bool(c) and c[0][4] == 86),
      ("V 4/86", bool(c) and abs(c[0][0] - 4 / 86) < 1e-9), ("retired", "D_A" not in out_c.definitions),
      ("global preserved", out_c.p_hat == st.p_hat)])


# ---------------- C16・C17（E の比べ）
def run_E(defs, hist, base, target, trial=5):
    st = make_state(defs, hist=hist)
    al = sme.map_graphs(base, target).alignment
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base, "alignment": al})
    calls = []

    def inner(state, b, t_, a_, tr, **kw):
        calls.append(kw.get("name"))
        h = B.hypo_m1(state, b, t_, a_, tr, kw.get("name"), {k: v for k, v in kw.items() if k != "name"})
        return (h[0], {"R": h[1], "was_extension": kw.get("name") is not None}) if h else (state, None)

    out, reg = B.choose_and_register(st, base, target, al, trial, KW, inner)
    rec = B.CTX.get("side")
    return rec, calls


setup()
D16 = make_def("D_A", reg_count=2)
fullA_b = make_scene("A", None, "base", tag="b")[0]
fullA_t = make_scene("A", None, "cur", tag="q")[0]
rec, calls = run_E([D16], None, fullA_b, fullA_t)
cm = {c[0]: c for c in rec["cands"]}
e_, n_ = cm.get("D_A"), cm.get(None)
common = v39.I(0) * 3        # 書換 I(0)・追加 I(0)・取消 I(0)：両方に同じ（無編集の頭）
ex = exp("C16")
act = {"A_existing": e_[1], "A_new": n_[1], "deltaC_existing": e_[3], "deltaC_new": n_[3], "r_existing": e_[2], "r_new": n_[2],
       "parts_existing": e_[5], "parts_new": n_[5], "K_existing": e_[4], "K_new": n_[4],
       "K_minus_common_overhead_existing": e_[4] - common, "K_minus_common_overhead_new": n_[4] - common, "choice": rec["chosen"]}
case("C16", ex, act,
     [("A_existing", abs(e_[1] - ex["A_existing"]) < 1e-6), ("A_new", abs(n_[1] - ex["A_new"]) < 1e-6),
      ("dC existing 12", e_[3] == 12), ("dC new 152", n_[3] == 152),
      ("residual body 0/0", e_[5]["書換数"] == 0 and e_[5]["追加数"] == 0 and n_[5]["書換数"] == 0 and n_[5]["追加数"] == 0),
      ("K-common existing", abs(e_[4] - common - ex["K_minus_common_overhead_existing"]) < 1e-6),
      ("K-common new", abs(n_[4] - common - ex["K_minus_common_overhead_new"]) < 1e-6),
      ("choice existing", rec["chosen"] == "D_A")],
     "side の cands の A・K は 6 桁に丸めてある（tools/v310be.py:411-412）。共通の無編集の頭は I(0)×3＝3 ビットとして引いた。")

setup()
D17 = make_def("D_S", "A", slots=[0, 1, 2], reg_count=2)
fullB_b = make_scene("B", None, "base", tag="b")[0]
fullB_t = make_scene("B", None, "cur", tag="q")[0]
rec, calls = run_E([D17], None, fullB_b, fullB_t)
cm = {c[0]: c for c in rec["cands"]}
e_, n_ = cm.get("D_S"), cm.get(None)
ex = exp("C17")
act = {"A_existing": e_[1], "A_new": n_[1], "deltaC_existing": e_[3], "deltaC_new": n_[3], "r_existing": e_[2], "r_new": n_[2],
       "parts_existing": e_[5], "parts_new": n_[5], "K_existing": e_[4], "K_new": n_[4],
       "K_existing_minus_common_overhead": e_[4] - common, "K_new_minus_common_overhead": n_[4] - common, "choice": rec["chosen"]}
case("C17", ex, act,
     [("A_existing", abs(e_[1] - ex["A_existing"]) < 1e-6), ("A_new", abs(n_[1] - ex["A_new"]) < 1e-6),
      ("dC existing 6", e_[3] == 6), ("dC new 152", n_[3] == 152), ("cancellations 0", e_[5]["取消"] == v39.I(0)),
      ("existing >= lower bound", e_[4] - common >= ex["K_existing_minus_common_overhead_lower_bound"] - 1e-6),
      ("K-common new", abs(n_[4] - common - ex["K_new_minus_common_overhead"]) < 1e-6),
      ("addition names >= 12", e_[5]["追加数"] * 4 >= 12), ("choice new D_B", rec["chosen"] is None)])

# ---------------- C18（最後でない s1 の席が U。見えた push を bind_s の写しで観察する）
setup()
D18 = make_def("D_A", alive={0: False})
hist18 = {("D_A", s): {LAYOUT["A"][s]: 2} for s in range(1, 6)}
seats18 = {("D_A", s): zero_rec("F") for s in range(1, 6)}
seats18[("D_A", 0)] = zero_rec("U")
st = make_state([D18], hist=hist18, seats=seats18)
L = v39.code_lengths(st.p_hat)
C0 = v39.total_bits(st, L)
res = B.hypo_m1(st, fullA, sceneF, sme.map_graphs(fullA, sceneF).alignment, 5, "D_A", KW)
sa = v39.reconcile(res[0], 5, "m1")
h0 = dict(v39.hist_counts(sa.slot_history.get(("D_A", 0))))
st0 = v39.seat_state(sa.definitions["D_A"], sa.definitions["D_A"].constituents[0], sa.slot_history)
rec0 = sa.v39_seats.get(("D_A", 0))
g, al18 = v39.map_v39(D18, hist18, sceneF)
# 訂正：今の版の通常の照合では U のまま。別の行：観察を直接与えた（observe_slot で push を 1 回）あとの算術
sd = replace(st, slot_history={**st.slot_history, ("D_A", 0): {"push": 1}})
sd = v39.reconcile(sd, 5, "直接")
rd = sd.v39_seats.get(("D_A", 0))
case("C18", exp("C18"), {"通常の照合_state_after": st0, "通常の照合_history_after": h0, "bind_s_mapped_in_m1_alignment": "D_A_s3" in al18.relation_mapping,
                         "直接_state": v39.seat_state(sd.definitions["D_A"], sd.definitions["D_A"].constituents[0], sd.slot_history),
                         "直接_H内容": v39.hcost(sd.slot_history[("D_A", 0)], L), "直接_世代": rd.gen if rd else None,
                         "直接_初期点": list(v39.rec_means(rd, 5)[1:3]) if rd else None},
     [("通常の照合では U のまま（訂正）", st0 == "U" and h0 == {}),
      ("直接：H", v39.seat_state(sd.definitions["D_A"], sd.definitions["D_A"].constituents[0], sd.slot_history) == "H"),
      ("直接：H 内容 10", v39.hcost(sd.slot_history[("D_A", 0)], L) == 10),
      ("直接：新しい世代・点 0", bool(rd) and rd.gen == 1 and v39.rec_means(rd, 5)[1:3] == (0.0, 0.0))],
     "訂正（ERRATA）に従い二つに分けた。直接の行は、観察を slot_history に置いてから v39.reconcile（tools/v39.py:764-790）を通した。")

# ---------------- C19（ΔR＝1・ΔC＝16：H 席の履歴 {push:15}＝I(1)＋4＋I(15)＝16）
setup()
D19 = make_def("D_A", alive={0: False})
hist19 = {("D_A", s): {LAYOUT["A"][s]: 2} for s in range(1, 6)}
hist19[("D_A", 0)] = {"push": 15}
seats19 = {("D_A", s): zero_rec("F") for s in range(1, 6)}
seats19[("D_A", 0)] = v39.rec_add(zero_rec("H"), t, (0.0, 0.0, 1.0, 1.0))
st = make_state([D19], hist=hist19, seats=seats19)
L = v39.code_lengths(st.p_hat)
c = [x for x in B.candidates(st, D19, t, L, 1) if x[3] == 0]
# 席 s1 だけ：変換の段の比べ（tools/v39.py:886-890 の c[0] < LAM）をそのまま当てる。ほかの席の変換は、この件の外
conv = ["HU"] if c[0][0] < LAM else []
out_all, ev_all, *_ = v39.run_conversions(st, t)
case("C19", exp("C19"), {"dC": c[0][4], "V": c[0][0], "converted_s1": conv,
                         "参考_定義全体の変換の段": [[e.get("v39"), e.get("slot_index"), e.get("V")] for e in ev_all if e.get("v39")]},
     [("dC 16", c[0][4] == 16), ("V 0.0625", c[0][0] == 0.0625), ("not converted", conv == [])])

# ---------------- C20（伏せた正解だけ変える・開示なし。取消は数えない）
setup()
st = make_state([make_def("D_A")], traces=[VerbatimTrace(0, make_scene("B", None, "full")[0])])
out1, a1, ans1 = predict(st, sceneB)
out2, a2, ans2 = predict(st, sceneB)       # 予測は伏せた正解を受け取らない（入力は提示の図だけ）
same_pred = a1 == a2
# 開示なし：採点は呼ばれない（tools/v39.py:1003-1007）。E の取消：写らない行のある定義で rewrite
L = v39.code_lengths(st.p_hat)
xB = make_scene("B", "wrap", "x")[0]
_, partsA = B.rewrite(st, "D_A", xB, L, CONFIG, {r.relation_id for r in xB.relations})
case("C20", exp("C20"), {"prediction_same_for_two_hidden_answers": same_pred, "rewrite_parts": partsA,
                         "new_cancellation_count": 0 if partsA["取消"] == v39.I(0) else "≠0"},
     [("cancellations 0", partsA["取消"] == v39.I(0)), ("prediction independent of hidden answer", same_pred)],
     "予測と E の入力は提示の図だけで、伏せた正解の値は関数の引数に無い。本人の状態の一致は、本番の旗で T02（tools/v38_checks/t02.py）が 839/839 一致（v3.10hs の確かめ）。ここでは同じ入力で二回予測して一致を見た。")

json.dump(RES, open(os.environ.get("SW_OUT", "/Users/tatsu-admin/sw_audit/results20e.json"), "w"), ensure_ascii=False, indent=1, default=str)
print("合", sum(r["pass"] for r in RES), "／", len(RES))
