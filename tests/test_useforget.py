"""使用で強める腕 D（--use-forget、tools/useforget.py）の関門 1 の小例。2026-10-01 昼の予約の委任書（改訂 2：D-最小）の 2 節。
例の場面：物 a・b・c。見えている関係 fold(a,b)、lock(b,c)、高階 cause(s_fold, s_lock)。伏せた関係 s_hid。写し x→a・y→b・z→c。
古さの重みは --v39-decay actr（tools/v39.py mean16）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import useforget as U  # noqa: E402
import v39  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402

SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")),
                      (Relation("s_fold", "fold", ("a", "b")), Relation("s_lock", "lock", ("b", "c")),
                       Relation("s_cause", "cause", ("s_fold", "s_lock"))))
LAM = 0.0187371
OUT = Path("/tmp/claude-1000/-home-tatsu-sfn/46945c76-63c2-47d5-81fa-9b12440cb938/scratchpad/uf_test.jsonl")


def setup(tau):
    T.MODE["decay"] = "actr"
    T.setup(price=LAM)
    if not U.ST:                                                 # 包みは一度だけ入れる（入れ直すと包みが重なる）
        U.install(str(OUT), tau=tau)
    U.ST.update(tau=float(tau), S={}, born={}, used_t=set(), t=None)
    U.ST["rec"] = {"uses": [], "struct": [], "other": 0, "answer": None}


def the_state():
    # r0 fold（F）・r1 lock（F）・r2 H（履歴 push）・c3 cause(r0, r1)（高階の F）・r4 wrap（F、伏せた位置に写る）
    d = T.definition(T.row(0, "fold", ("x", "y"), rid="r0"), T.row(1, "lock", ("y", "z"), rid="r1"),
                     T.row(2, v39.ERASED, ("x", "z"), alive=False, rid="r2"), T.row(3, "cause", ("r0", "r1"), rid="c3"),
                     T.row(4, "wrap", ("x", "y"), rid="r4"))
    hist = {("R_x", 0): {"fold": 1}, ("R_x", 1): {"lock": 1}, ("R_x", 2): {"push": 1}, ("R_x", 3): {"cause": 1}, ("R_x", 4): {"wrap": 1}}
    seats = {("R_x", s): T.rec("H" if s == 2 else "F", sf=1.0, sh=1.0, su=1.0, e=1.0) for s in range(5)}
    return d, T.state([d], hist, seats, ph=T.p_hat(fold=5, wrap=3, lock=2, push=1, cause=1))


def key(d, s):
    return (d.name, s, d.registered_at)


def match(st, d, rm, passed=True):
    U.ST["rec"] = {"uses": [], "struct": [], "other": 0, "answer": None}
    U._record_matching(st, SCENE, (None, None, d, None, SimpleNamespace(relation_mapping=rm), None, None, passed))
    return U.ST["rec"]


def states(st):
    d = st.definitions.get("R_x")
    return {r.slot_index: v39.seat_state(d, r, st.slot_history) for r in d.constituents} if d else None


def births(d, t):
    for r in d.constituents:
        U._birth(key(d, r.slot_index), t)
    U.ST["used_t"] = set()


def test_1_used_every_trial_is_not_thinned():
    setup(tau=0.5)
    d, st = the_state()
    births(d, 10)
    for t in range(11, 40):
        U.ST["t"] = t
        for s in (0, 1):
            U._use(key(d, s), t)
        st, *_ = v39.run_conversions(st, t)
    sts = states(st)
    assert sts[0] == "F" and sts[1] == "F"                       # 毎試行使われる席は薄くならない
    assert U.strength(U.ST["S"][key(d, 0)], 39) >= 1.0


def test_2_unused_F_and_H_go_to_U_when_S_below_tau():
    setup(tau=0.5)
    d, st = the_state()
    births(d, 10)
    U.ST["t"] = 11
    U._use(key(d, 0), 11)
    U._use(key(d, 1), 11)
    s11 = U.strength(U.ST["S"][key(d, 4)], 11)
    assert s11 < 0.5                                             # 誕生の一回の使用は次の試行で 0.4168（actr）
    out, ev, *_ = v39.run_conversions(st, 11)
    sts = states(out)
    assert sts[0] == "F" and sts[1] == "F"
    assert sts[2] == "U" and sts[4] == "U" and sts[3] == "U"     # H は U、F は H を経て U まで（同じ判断の中）
    conv = [(e["v39"], e["slot_index"]) for e in ev if e.get("v39") in ("FH", "HU")]
    assert ("FH", 4) in conv and ("HU", 4) in conv and ("HU", 2) in conv and ("FH", 2) not in conv


def test_2b_S_at_or_above_tau_is_kept():
    setup(tau=0.4)                                               # 0.4168 ≥ 0.4 なら残す
    d, st = the_state()
    births(d, 10)
    out, *_ = v39.run_conversions(st, 11)
    assert set(states(out).values()) == {"F", "H"}


def test_3_higher_order_seat_in_selected_matching_is_counted():
    setup(tau=0.5)
    d, st = the_state()
    U.ST["t"] = 11
    rec = match(st, d, {"r0": "s_fold", "r1": "s_lock", "c3": "s_cause"})
    assert [u[1] for u in rec["uses"]] == [0, 1, 3]              # 高階の席 c3（cause の名が場面の cause と一致）も数える


def test_4_mapped_only_to_hidden_position_is_not_counted():
    setup(tau=0.5)
    d, st = the_state()
    U.ST["t"] = 11
    rec = match(st, d, {"r0": "s_fold", "r4": "s_hid"})
    assert [u[1] for u in rec["uses"]] == [0]
    assert rec["struct"] == [[4, "F"]]                           # 伏せた位置に写っただけ：構造だけ（数えない）
    assert key(d, 4) not in U.ST["S"]


def test_4b_name_mismatch_and_H_history():
    setup(tau=0.5)
    d, st = the_state()
    U.ST["t"] = 11
    rec = match(st, d, {"r4": "s_fold", "r2": "s_lock"})         # F の wrap が fold に写る（名が違う）・H の履歴 push に lock
    assert rec["uses"] == []
    st2 = replace(st, slot_history={**st.slot_history, ("R_x", 2): {"push": 1, "lock": 1}})
    rec = match(st2, d, {"r2": "s_lock"})
    assert [u[1:] for u in rec["uses"]] == [[2, "照合", "H"]]        # H：場面の名が履歴にあれば数える


def test_5_silent_trial_still_counts_matching():
    setup(tau=0.5)
    d, st = the_state()
    U.ST["t"] = 11
    rec = match(st, d, {"r0": "s_fold", "r1": "s_lock"}, passed=False)   # 発話の門を通らない
    assert [u[1] for u in rec["uses"]] == [0, 1]


def test_6_not_thinned_on_birth_trial():
    setup(tau=1e9)                                               # どの席も S＜τ
    d, st = the_state()
    births(d, 10)
    out, *_ = v39.run_conversions(st, 10)                        # 誕生の試行
    assert set(states(out).values()) == {"F", "H"}
    out, *_ = v39.run_conversions(out, 11)                       # 次の試行から
    assert states(out) is None or set(states(out).values()) == {"U"}


def test_7_once_per_trial():
    setup(tau=0.5)
    d, st = the_state()
    U.ST["t"] = 11
    match(st, d, {"r0": "s_fold"})
    assert not U._use(key(d, 0), 11)                             # 照合と答えが重なっても一回
    assert U.ST["S"][key(d, 0)] == (11, [1.0] * 16)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
