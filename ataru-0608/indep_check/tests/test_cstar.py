"""(a) C* の参照の検査。手で確かめられる小さな図。python3.12 tests/run_all.py で走る（pytest でも可）。"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from refcommon import Definition, Scene, Seat, sme2017, sme2017_blob_sha, SME2017_BLOB  # noqa: E402
from ref_cstar import (T_def, T_scene, best_mappings, cstar_score, cstar_score_fullnames, enumerate_mappings,  # noqa: E402
                       Q_P, score_fixed)
from refcommon import def_graph, scene_graph  # noqa: E402


def toy_def(seal_state="U", fixed=None, hist=()):
    """委任書 41 ■5 のおもちゃ（control/2026-10-06_照合のおもちゃ_Claude.py の図）。"""
    return Definition("toy", 0, ("d", "s"), (
        Seat("seal", ("d",), seal_state, fixed, hist),
        Seat("at", ("d", "s"), "F", "at"), Seat("open", ("d",), "F", "open"),
        Seat("top", ("at", "open"), "F", "implies"), Seat("link", ("seal", "top"), "F", "attach")))


TOY_SCENE = Scene(("d", "s"), (("seal", "sig_e", ("d",)), ("at", "at", ("d", "s")), ("open", "open", ("d",)),
                               ("top", "implies", ("at", "open")), ("link", "attach", ("seal", "top"))))
TOY_M = {k: k for k in ("seal", "at", "open", "top", "link")}


def test_sme2017_version():
    assert sme2017_blob_sha() == SME2017_BLOB


def test_toy_five_values():
    """41 ■5：シールだけ不確かで sig_e の確率が p のとき S_P＝0.1175, 0.2052, 0.5560, 0.9068, 0.9945。"""
    want = {0: 0.1175, 0.1: 0.2052, 0.5: 0.5560, 0.9: 0.9068, 1: 0.9945}
    for p, v in want.items():
        q = {"seal": p, "at": 1, "open": 1, "top": 1, "link": 1}
        got = cstar_score(toy_def(), TOY_SCENE, TOY_M, q)
        assert abs(got - v) < 5e-5, (p, got, v)
        assert abs(got - (0.1175 + 0.877 * p)) < 1e-12


def test_toy_hand_breakdown():
    """手計算：一致なら link .0005、top .0005+8·.0005、seal 同、at・open .0005+8·.0045、d 8·(.0045+.0365+.0365)、
    s 8·.0365 → 0.9945。不一致なら seal・link が落ち、top .0005、at・open .0045、d 8·.009、s 8·.0045 → 0.1175。"""
    hit = 0.0005 + 0.0045 + 0.0045 + 0.0365 + 0.0365 + 8 * 0.0775 + 8 * 0.0365
    miss = 0.0005 + 0.0045 + 0.0045 + 8 * 0.009 + 8 * 0.0045
    assert abs(hit - 0.9945) < 1e-12 and abs(miss - 0.1175) < 1e-12
    assert abs(T_def(toy_def()) - hit) < 1e-12
    assert abs(T_scene(TOY_SCENE) - hit) < 1e-12


def test_zero_one_limit_equals_plain_sme():
    """名前の不確かさを 0/1 にした極限で、通常の名前一致の照合（sme2017 の Matcher の第一位）に戻る（GPT 照合 §3 93 行）。"""
    m = sme2017.Matcher(sme2017.Settings(), tie_seed=0)
    R = scene_graph(TOY_SCENE)
    for name, p in (("sig_e", 1), ("sig_n", 0)):
        names = {"seal": name, "at": "at", "open": "open", "top": "implies", "link": "attach"}
        plain = m.match(def_graph(toy_def(), names), R).best.score
        q = {"seal": p, "at": 1, "open": 1, "top": 1, "link": 1}
        assert abs(cstar_score(toy_def(), TOY_SCENE, TOY_M, q) - plain) < 1e-12


def shared_child():
    """物 e・e2。c(e) を p1(c)・p2(c) が共有。独立の枝 k(e2)。"""
    d = Definition("sc", 0, ("e", "e2"), (Seat("c", ("e",), "U"), Seat("p1", ("c",), "F", "p1"),
                                          Seat("p2", ("c",), "F", "p2"), Seat("k", ("e2",), "F", "k")))
    sc = Scene(("e", "e2"), (("c", "c", ("e",)), ("p1", "p1", ("c",)), ("p2", "p2", ("c",)), ("k", "k", ("e2",))))
    return d, sc, {"c": "c", "p1": "p1", "p2": "p2", "k": "k"}


def test_shared_child_counted_once():
    """共有された子の確率を二度掛けない（41 ■5、GPT 照合 §9 関門 4）。依存しない枝の点は残る（関門 5）。
    手計算：c が合えば p1 .0005、p2 .0005、c .0005＋8·.001＝.0085、e 8·.0085＝.068 → .0775。合わなければ p1・p2 も
    落ち、e も対に残らない → 0。独立の枝 k .0005＋e2 8·.0005＝.0045。よって S_P＝.0045＋.0775q（q² は出ない）。"""
    d, sc, M = shared_child()
    for qc in (0.0, 0.3, 0.5, 1.0):
        q = {"c": qc, "p1": 1, "p2": 1, "k": 1}
        got = cstar_score(d, sc, M, q)
        assert abs(got - (0.0045 + 0.0775 * qc)) < 1e-12, (qc, got)


def test_two_independent_children_product():
    """二つの独立な子：親 p(c1,c2)。四つの場合を手で：両方 .0005·3＋8·(…)。ここでは列挙の S0 を手の値と照らす。"""
    d = Definition("two", 0, ("e1", "e2"), (Seat("c1", ("e1",), "U"), Seat("c2", ("e2",), "U"),
                                            Seat("p", ("c1", "c2"), "F", "p")))
    sc = Scene(("e1", "e2"), (("c1", "a", ("e1",)), ("c2", "b", ("e2",)), ("p", "p", ("c1", "c2"))))
    M = {"c1": "c1", "c2": "c2", "p": "p"}
    both = 0.0005 + 2 * (0.0005 + 8 * 0.0005) + 2 * 8 * 0.0045      # p, c1, c2, e1, e2
    one = 0.0005 + 8 * 0.0005                                         # c1 と e1 だけ（p は落ちる）
    q1, q2 = 0.3, 0.6
    want = q1 * q2 * both + q1 * (1 - q2) * one + (1 - q1) * q2 * one
    got = cstar_score(d, sc, M, {"c1": q1, "c2": q2, "p": 1})
    assert abs(got - want) < 1e-12, (got, want)


def test_hidden_position_marginalized():
    """伏せた位置は一致を評価しない（名前を替えても点が変わらない）。局所の名前の点は 0（GPT 照合 §4 146–150 行）。
    手計算：p(c) で c が伏せた位置：p .0005、c 0＋8·.0005 → .0045（c は引数を持たないので e は対にならない）。"""
    sc = Scene(("e",), (("p", "p", ("c",)),), ("c",))
    for st, fx in (("U", None), ("F", "x"), ("F", "y")):
        d = Definition("h", 0, ("e",), (Seat("c", ("e",), st, fx), Seat("p", ("c",), "F", "p")))
        got = cstar_score(d, sc, {"c": "c", "p": "p"}, {"p": 1})
        assert abs(got - 0.0045) < 1e-12


def test_T_invariant_to_labels():
    """同じ構造で F/H/U の札だけ替えても T は変わらない（41 ■5、GPT 照合 §9 関門 7）。"""
    base = T_def(toy_def("U"))
    assert T_def(toy_def("F", "sig_n")) == base
    assert T_def(toy_def("H", None, (("sig_n", 2), ("sig_e", 1)))) == base
    # 席を消せば縮む
    d = toy_def()
    smaller = Definition("s", 0, d.entities, tuple(s for s in d.seats if s.key != "link"))
    assert T_def(smaller) < base


def test_Q_P_toy():
    q = {"seal": 0.5, "at": 1, "open": 1, "top": 1, "link": 1}
    sp = cstar_score(toy_def(), TOY_SCENE, TOY_M, q)
    assert abs(Q_P(sp, T_def(toy_def()), T_scene(TOY_SCENE)) - sp / 0.9945) < 1e-12
    assert Q_P(0.0, 0.0, 0.0) is None


def test_zero_probability_not_candidate():
    """確率 0 の名前は C* では q＝0 として候補にしない（41′ 1）。"""
    d = toy_def("F", "sig_n")
    Pm = {"seal": {"sig_n": 1.0}, "at": {"at": 1.0}, "open": {"open": 1.0}, "top": {"implies": 1.0},
          "link": {"attach": 1.0}}
    for M in enumerate_mappings(d, TOY_SCENE, Pm):
        assert "seal" not in M
    best, arg = best_mappings(d, TOY_SCENE, Pm)
    assert abs(best - 0.1175) < 1e-12 and len(arg) == 1


def _random_case(rng):
    ents = tuple(f"e{i}" for i in range(rng.randint(1, 3)))
    seats = []
    keys = []
    for i in range(rng.randint(2, 4)):
        pool = list(ents) + keys
        ar = rng.randint(1, 2)
        args = tuple(rng.choice(pool) for _ in range(ar))
        if len(set(args)) != len(args):
            args = args[:1]
        k = f"r{i}"
        seats.append(Seat(k, args, "U", slot=i))
        keys.append(k)
    d = Definition("rand", 0, ents, tuple(seats))
    names = ["a", "b", "c"]
    hidden = set(k for k in keys if rng.random() < 0.25 and any(k in s.args for s in seats))
    vis = tuple((s.key, rng.choice(names), s.args) for s in seats if s.key not in hidden)
    sc = Scene(ents, vis, tuple(sorted(hidden)))
    # 伏せた鍵を引数に持つ関係は見えている（親が見えていない伏せた鍵は場面に入らないので、ここでは作らない）
    M = {s.key: s.key for s in seats}
    P = {}
    for s in seats:
        w = [rng.random() for _ in names]
        z = sum(w)
        P[s.key] = {x: v / z for x, v in zip(names, w)}
    return d, sc, M, P


def test_random_binary_equals_full_name_enumeration():
    """固定した M で、無作為の小さな図 200 個：一致・不一致の 2^k 列挙と、名前の全場合の列挙が一致する
    （参照の中の照らし合わせ。実装の速い計算との照合は手順 2 で行う）。"""
    rng = random.Random(20261007)
    n = 0
    while n < 200:
        d, sc, M, P = _random_case(rng)
        try:
            q = {k: P[k].get(sc.name_of(M[k]), 0.0) for k in M if sc.name_of(M[k]) is not None}
            a = cstar_score(d, sc, M, q)
        except ValueError:
            continue
        b = cstar_score_fullnames(d, sc, M, P)
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15), (a, b)
        n += 1
