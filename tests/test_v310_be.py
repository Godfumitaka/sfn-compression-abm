"""v3.10 B＋E（旗 --v310-be、tools/v310be.py）の受入検査の小例（仕様 control/sfn_v310_be_spec_2026-09-29_v2.md の 10 節 ①〜⑫）。
走行を使う検査（⑫ 旗なしで v3.10 と同じ・T02・λ＝0 の 1,740 試行）は tools/v310_checks/be_checks.sh で別に確かめる。
すべて --v39-decay actr（仕様 6 節の w）で回す。
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import v39  # noqa: E402
import v310be as B  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

T.MODE["decay"] = "actr"
PH = dict(fold=5, wrap=3, lock=2, push=1, pull=1, cause=2)
CONFIG = SimpleNamespace(local_lambda=1.0, higher_order_predicates=frozenset({"cause"}))
KW = dict(base_written_at=0, horizon=100, pricing_rule="legacy", refill_rule="legacy", local_lambda=1.0)


def setup(lam=0.0):
    T.setup(price=lam)
    v39.CFG["dict_index"] = {p: i for i, p in enumerate(list(PH) + ["never_seen"])}
    v39.CFG["D"] = len(v39.CFG["dict_index"])
    for d in (B.STATS, B.CFG, B.CTX):
        d.clear()
    B.CFG.update(seed=1, alpha=1.0, lam=lam, nohash=True)
    B.STATS.update(commons_lt2=0, chose_new=0, chose_existing=0, ties=0, new_excluded_structure=0, assim_impossible=0,
                   no_candidate=0, dC_mismatch=0, assim_match0=0, assim_hist0=0, zero_release=0, retire_candidate_evals=0,
                   score_other_position=0)
    B.CTX.update(R_B_trial=0.0, R_E_trial=0.0, L_score=v39.code_lengths(T.p_hat(**PH)))
    v39.CTX["config"] = CONFIG


def st(defs, hist, seats=None):
    return T.S39(definitions={d.name: d for d in defs}, slot_history=hist, p_hat=T.p_hat(**PH), v39_seats=seats or {})


def seat(st_="F", t0=10, gen=0):
    return v39.SeatRec(gen, st_, 3, t0, v39.ZERO4, v39.ZERO4)


def the_def(name="R_x"):
    return T.definition(T.row(0, "fold", ("x", "y")), T.row(1, "lock", ("y", "z")), T.row(2, "push", ("x", "z"), alive=False),
                        name=name)


HIST = {("R_x", 0): {"fold": 2, "wrap": 1}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 1}}
X = RelationGraph("x", (Entity("a"), Entity("b"), Entity("c")),
                  (Relation("s_fold", "fold", ("a", "b")), Relation("s_lock", "wrap", ("b", "c")),
                   Relation("s_pull", "pull", ("a", "c"))))


# ① 同じ答えは差 0、写しの決まらない席・位置の違う席は全列を更新しない
def test_01_same_answer_zero_and_unknown_not_updated():
    setup()
    seats = {("R_x", 0): seat("F"), ("R_x", 1): seat("F"), ("R_x", 2): seat("H")}
    ans = {"R": "R_x", "items": [
        {"slot": 0, "st": "F", "pos": ["a", "b"], "gen": 0, "ans": {"F": "fold", "H": "fold", "U": "wrap"}},
        {"slot": 1, "st": "F", "pos": ["b", "c"], "gen": 0, "ans": {"F": "lock", "H": "lock", "U": "lock"}},
        {"slot": 2, "st": "H", "pos": None, "gen": 0}]}
    out, scored = B.score_answers(seats, ans, Relation("e", "wrap", ("a", "b")), 11)
    RF, RH, RU, n = v39.rec_means(out[("R_x", 0)], 11)
    lw = v39.code_lengths(T.p_hat(**PH))["wrap"]
    assert abs(RF - lw) < 1e-12 and abs(RH - lw) < 1e-12 and RU == 0.0     # F と H は同じ答え：差 0。U だけ当たり
    assert out[("R_x", 1)] is seats[("R_x", 1)] and out[("R_x", 2)] is seats[("R_x", 2)]   # 位置が違う・写しが無い：不更新
    assert B.STATS["score_other_position"] == 1 and len(scored) == 1


# ② 名前・引数・取消／追加を二重に数えない
def test_02_no_double_counting():
    setup()
    s = st([the_def()], HIST)
    L = v39.code_lengths(s.p_hat)
    bits, parts = B.rewrite(s, "R_x", X, L, CONFIG, {r.relation_id for r in X.relations})
    # fold→s_fold は一致、lock の席は H でないので名前が違う wrap には当てはまらない → 写らない。push（H）は pull に写らない
    assert parts["写った席"] + parts["追加数"] == len(X.relations)          # x の各関係は「写った」か「追加」のどちらか一回だけ
    assert parts["一致"] + parts["書換数"] == parts["写った席"]              # 写った関係は「一致」か「書換」のどちらか一回だけ
    assert abs(bits - (parts["書換"] + parts["追加"] + parts["取消"])) < 1e-12


# ③ 伏せ・抽出落ち・複数の真を否定しない。一関係の開示や二度の未観測で不在にしない（取消は払わない）
def test_03_absence_never_assumed():
    setup()
    s = st([the_def()], HIST)
    L = v39.code_lengths(s.p_hat)
    _, parts = B.rewrite(s, "R_x", X, L, CONFIG, {r.relation_id for r in X.relations})
    assert parts["取消"] == v39.I(0) and parts["取消の未確認"] >= 1          # 写らなかった席は数えるだけ（m＝0）
    # 同じ引数に別名の真の関係があっても、答えた名が開示と違うだけで、ほかの席を外れにしない（位置が違えば不更新）
    seats = {("R_x", 0): seat("F")}
    ans = {"R": "R_x", "items": [{"slot": 0, "st": "F", "pos": ["a", "c"], "gen": 0, "ans": {"F": "fold", "H": None, "U": None}}]}
    out, _ = B.score_answers(seats, ans, Relation("e", "wrap", ("a", "b")), 11)
    assert out[("R_x", 0)] is seats[("R_x", 0)]


# ④ 取消リストの復元、k＝0、m＝0／m＝k、仕様 8 節の小例
def test_04_cancel_code():
    for k, sl in ((15, [3, 0, 14]), (15, []), (15, list(range(15))), (1, [0]), (0, [])):
        e = B.d1_encode(k, sl)
        assert len(e) == B.d1_bits(k, len(sl)) and B.d1_decode(k, e) == sorted(sl)
    try:
        B.d1_bits(0, 1)
        raise AssertionError("k＝0 で m＞0 を許した")
    except ValueError:
        pass
    I0 = v39.I(0)
    M3 = 8 * 5 + (B.d1_bits(15, 8) - I0)                  # 7 一致・8 取消・8 追加（追加 1 本 5 ビットの仮定）
    M4 = 15 * 5 + (B.d1_bits(15, 15) - I0)
    assert (M3, M4) == (78, 143) and (B.d1_bits(15, 8) - I0, B.d1_bits(15, 15) - I0) == (38, 68)
    assert M3 < 100 < M4                                  # 不在を全部確かめた場合：M3 は同化、M4 は新規
    assert 8 * 5 < 100 and 15 * 5 < 100                   # 不在が確かめられない場合（取消の増分 0）：どちらも同化


def _graphs():
    import abm.sme as sme
    base = RelationGraph("base", (Entity("p"), Entity("q"), Entity("r")),
                         (Relation("b_fold", "fold", ("p", "q")), Relation("b_lock", "lock", ("q", "r")),
                          Relation("b_cause", "cause", ("b_fold", "b_lock"))))
    target = RelationGraph("scene", X.entities, (Relation("s_fold", "fold", ("a", "b")), Relation("s_lock", "lock", ("b", "c")),
                                                 Relation("s_cause", "cause", ("s_fold", "s_lock")),
                                                 Relation("s_pull", "pull", ("a", "c"))))
    return base, target, sme.map_graphs(base, target).alignment


# ⑤ 新規／同化の増分が実測の C の差と一致。保存料を r に二重に入れない
def test_05_increment_matches_and_no_double_storage():
    setup()
    base, target, al = _graphs()
    s = st([the_def()], HIST)
    L = v39.code_lengths(s.p_hat)
    C0 = v39.total_bits(s, L)
    for name in (None, "R_x"):
        sa, R = B.hypo_m1(s, base, target, al, 5, name, KW)
        C1 = v39.total_bits(sa, L)
        if name is None:
            fast = v39.definition_bits(sa.definitions[R], sa.slot_history, L) + v39.I(2) - v39.I(1)
            _, parts = B.rewrite(sa, R, target, L, CONFIG, {r.relation_id for r in target.relations})
            assert parts["書換数"] == 0                     # 新しい定義は自分の行を書き換えない（保存料は λΔC だけ）
        else:
            fast = v39.definition_bits(sa.definitions[R], sa.slot_history, L) - v39.definition_bits(s.definitions[R], s.slot_history, L)
        assert C1 - C0 == fast


# ⑥ 重みの和・時間の経過・平均の除算の撤去
def test_06_weights_decay_no_division():
    setup()
    wt = v39.CFG["mean_weights"]
    assert abs(sum(wt) - 1.0) < 1e-12
    taus = [0.3 * (5220 / 0.3) ** ((i - 1) / 15) for i in range(1, 17)]
    a = [t ** -0.5 / sum(x ** -0.5 for x in taus) for t in taus]
    v39.CFG["T"] = 1740
    v39.CFG["decay"] = __import__("abm.accounting", fromlist=["decay_ladder"]).decay_ladder(1740)
    v39.CFG["mean_weights"] = v39.actr_weights(1740)
    v39._POW.clear()
    rec = v39.rec_add(seat("F", t0=10), 10, (0.0, 3.0, 5.0, 1.0))
    for d in (0, 1, 10, 100):
        w = sum(ai * math.exp(-d / ti) for ai, ti in zip(a, taus))
        RF, RH, RU, n = v39.rec_means(rec, 10 + d)
        assert abs(RH - 3.0 * w) < 1e-9 and abs(RU - 5.0 * w) < 1e-9
    d = T.definition(T.row(0, "fold", ("x", "y")), T.row(1, "lock", ("y", "z")))
    s = st([d], {("R_x", 0): {"fold": 2}, ("R_x", 1): {"lock": 1}}, {("R_x", 0): rec, ("R_x", 1): seat("F")})
    L = v39.code_lengths(s.p_hat)
    c = [x for x in B.candidates(s, d, 20, L, 1) if x[3] == 0][0]
    RF, RH, RU, n = v39.rec_means(rec, 20)
    assert c[0] == (RH - RF) / v39.fixed_spec_bits("fold", {"fold": 2}, L)   # E で割らない・a の補正なし


# ⑦ 負点／同点／解放量 0 と独立の乱数
def test_07_negative_ties_zero_release():
    setup(lam=0.0)
    d = T.definition(T.row(0, "fold", ("x", "y")), T.row(1, "lock", ("y", "z")), T.row(2, "push", ("x", "z")))
    neg = v39.rec_add(seat("F"), 10, (5.0, 0.0, 0.0, 1.0))           # R_F＞R_H：手放すと書換が減る → V＜0
    zero = seat("F")
    s = st([d], {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 1}},
           {("R_x", 0): neg, ("R_x", 1): zero, ("R_x", 2): zero})
    v39._candidates = B.candidates
    g0 = random.getstate()
    out, ev, *_ = v39.run_conversions(s, 10)
    conv = [(e["v39"], e["slot_index"]) for e in ev if e.get("v39") in ("FH", "HU")]
    assert conv[0] == ("FH", 0) and ("FH", 1) not in conv          # λ＝0：負は手放し、V＝0（＝λ）は残す
    assert random.getstate() == g0
    setup(lam=1e-9)
    out, ev, *_ = v39.run_conversions(s, 10)
    ties = [e["tie_n"] for e in ev if e.get("v39") == "FH" and e["slot_index"] in (1, 2)]
    assert ties and max(ties) >= 2 and random.getstate() == g0      # V＝0＜λ の同点は独立の乱数で一つずつ
    real = v39.fixed_spec_bits
    v39.fixed_spec_bits = lambda *a, **k: 0
    try:
        L = v39.code_lengths(s.p_hat)
        assert [c for c in B.candidates(s, d, 10, L, 1) if c[1] == "FH"] == [] and B.STATS["zero_release"] == 3
    finally:
        v39.fixed_spec_bits = real


# ⑧ 候補の仮評価に副作用が無い・共通の記憶価格
def test_08_hypo_no_side_effects():
    setup()
    base, target, al = _graphs()
    s = st([the_def()], HIST)
    snap = (dict(s.definitions), dict(s.slot_history), s.p_hat, dict(v39.STATS), dict(B.STATS), len(v39.REG))
    for name in (None, "R_x"):
        B.hypo_m1(s, base, target, al, 5, name, KW)
    assert (dict(s.definitions), dict(s.slot_history), s.p_hat, dict(v39.STATS), dict(B.STATS), len(v39.REG)) == snap


# ⑨ 三段階・覚え直し・全 U で退役（v3.9 の変換をそのまま使う。最後の変換は構造を含む総解放量）
def test_09_three_stages_retire():
    setup()
    d = T.definition(T.row(0, "fold", ("x", "y"), alive=False))
    s = st([d], {("R_x", 0): {"fold": 1}}, {("R_x", 0): seat("H")})
    L = v39.code_lengths(s.p_hat)
    c = B.candidates(s, d, 10, L, 1)[0]
    assert c[1] == "HU" and c[4] == v39.definition_bits(d, s.slot_history, L) + v39.I(1) - v39.I(0)
    out, ev = v39._convert(s, "HU", "R_x", 0, 10)
    assert "R_x" not in out.definitions and ev["v39"] == "retire"


# ⑩ 候補の内訳の和と採否が一致（K＝A＋r＋λΔC、r＝書換＋追加＋取消、最小を採る）
def test_10_breakdown_and_choice():
    setup(lam=0.5)
    base, target, al = _graphs()
    s = st([the_def()], HIST, {("R_x", i): seat("F" if i < 2 else "H") for i in range(3)})
    v39.CTX["output"] = SimpleNamespace(trace={"selected_scene": base, "alignment": al})
    calls = []

    def inner(state, b, t, a, trial, **kw):
        calls.append(kw.get("name"))
        h = B.hypo_m1(state, b, t, a, trial, kw.get("name"), {k: v for k, v in kw.items() if k != "name"})
        return (h[0], {"R": h[1], "was_extension": kw.get("name") is not None}) if h else (state, None)

    out, reg = B.choose_and_register(s, base, target, al, 5, KW, inner)
    rec = B.CTX["side"]
    for R, A, r, dC, K, parts in rec["cands"]:
        assert abs(K - (A + r + 0.5 * dC)) < 1e-6 and abs(r - (parts["書換"] + parts["追加"] + parts["取消"])) < 1e-6
    assert rec["chosen"] == min(rec["cands"], key=lambda c: c[4])[0] and calls == [rec["chosen"]]
    assert rec["dC_pred"] == rec["dC_real"]


# ⑪ 答えは正解を見る前に控えたもの。誕生の初期値は観察を二重に足さない
def test_11_answers_before_truth_and_no_double_birth_observation():
    setup()
    d = the_def()
    s = st([d], HIST)
    base, target, _ = _graphs()
    hist0 = dict(s.slot_history)
    v39.CTX["births_rec"] = []
    rec = B.init_rec(d, d.constituents[0], s, base, target, 5, 2, CONFIG)
    assert dict(s.slot_history) == hist0 and rec.post == v39.ZERO4          # 初期値は別に持ち、履歴は触らない
    # 採点は控えた答え（ans）だけを読む。開示の後で答えを作り直さない
    seats = {("R_x", 0): seat("F")}
    ans = {"R": "R_x", "items": [{"slot": 0, "st": "F", "pos": ["a", "b"], "gen": 0, "ans": {"F": "fold", "H": "wrap", "U": None}}]}
    out, sc = B.score_answers(seats, ans, Relation("e", "wrap", ("a", "b")), 11)
    assert sc[0][2] > 0 and sc[0][3] == 0.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
