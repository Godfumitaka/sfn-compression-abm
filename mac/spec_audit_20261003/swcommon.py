"""（共通の部品。run_cases.py の頭を切り出したもの。SW_TREE で作業場所＝版を選ぶ）小さな世界の局所検査（local_expectations.json）を、v3.10hs-main（ecb355f）のコードで一件ずつ走らせる。
★ コードは読むだけ（作業場所 sfn-compression-abm-v3.10hs-main を import する）。直さない。期待値を書き換えない。
各件は初期状態から作り直す。出力：~/sw_audit/results.json（件ごとに 実際の値・比べ・メモ）。
使い方  python3.12 run_cases.py [T]   T は予定試行数（既定 16。減衰の τ は 3T まで：コード abm/accounting.py decay_ladder）"""
import json
import math
import sys
from dataclasses import replace
from random import Random
from types import SimpleNamespace

import os
W = os.environ.get("SW_TREE", "/Users/tatsu-admin/sfn/sfn-compression-abm-v3.10hs-main")
sys.path[:0] = [W + "/tools", W]
import v39  # noqa: E402
import v310be as B  # noqa: E402
import histrole  # noqa: E402
import abm.abstraction as ab  # noqa: E402
import abm.sme as sme  # noqa: E402
from abm.accounting import decay_ladder  # noqa: E402
from abm.agent_runtime import _need  # noqa: E402
from abm.definition import Constituent, FrequencyTable, FrozenPrice, NamedDefinition  # noqa: E402
from abm.domains import Entity, Prototype, Relation, RelationGraph, VerbatimTrace  # noqa: E402

T_PLAN = int(os.environ.get("SW_T", "16"))
DICT = ["push", "fold", "cut", "turn", "wrap", "stack", "bind_s", "bind_a", "bind_b"]
HOP = frozenset({"bind_s", "bind_a", "bind_b"})
CONFIG = SimpleNamespace(threshold=0.0, tau_acc=0.67, local_lambda=1.0, higher_order_predicates=HOP,
                         fill_selection="most_frequent", verbatim_threshold=0.3842)
PRICE = FrozenPrice(1.0, 0, 0.0, 6)
KW = dict(base_written_at=0, horizon=T_PLAN, pricing_rule="legacy", refill_rule="legacy", local_lambda=1.0)
LAM = 0.0625

# 一度だけ入れる差し替え（本番の tools/v3_run.py worker と同じ順：fix_order2 → fix2 → v31（extend none）… → v39 → v310be）
import fixorder2  # noqa: E402
import fix2  # noqa: E402
import v31  # noqa: E402
fixorder2.install()                                 # tools/v3_run.py:380-386（sme.map_graphs を名前・番号に依らない写しに差し替え、読み込み済みのモジュールも張り替える）
fix2.install(full=True)                             # tools/v3_run.py:387-392（REG に無いグラフは元のまま）
v31.install("none", "v2", 2.1, 0.0, 1.0, 0.0)       # tools/v3_run.py:352-357（ab._extend_definition＝_extend_none。charge1 は会計だけなので v2）
v39._install_candidates()
_ORIG_THREE = v39.three_answers
v39.three_answers = B.three_answers_role(_ORIG_THREE)
v39.score_answers = B.score_answers_role
v39._init_rec = B.init_rec
v39._candidates = B.candidates
_ORIG_M1 = ab.m1
ab.m1 = histrole.make(_ORIG_M1, real=False)
# 版ごとの旗（SW_FLAGS に u_struct・relearn_init）：tools/v3_run.py:440-446 と同じく、v39・v310be のあとに入れる
import io as _io
SW_FLAGS = set(filter(None, os.environ.get("SW_FLAGS", "").split(",")))
_FO = _io.StringIO()
if "u_struct" in SW_FLAGS:
    import ustruct  # noqa: E402
    ustruct.install(_FO)
if "relearn_init" in SW_FLAGS:
    import relearninit  # noqa: E402
    relearninit.install(_FO)
if "tie_struct" in SW_FLAGS:              # tools/v3_run.py（v3.10urta）:450-453
    import tiestruct  # noqa: E402
    tiestruct.install()


def reconcile_with_scene(state, trial, why, scene):
    """本番では loop.m1／会計の包み（tools/relearninit.py:32-43）が場面を控えてから reconcile が呼ばれる。その控えを同じく置く。"""
    if "relearn_init" in SW_FLAGS:
        relearninit.CTX["scene"] = scene
    return v39.reconcile(state, trial, why)


S39 = v39._state_class()


def setup(T=T_PLAN, lam=LAM, u_abstain=False):
    for d in (v39.STATS, v39.CFG, v39.CTX, v39.REG, v39._POW):
        d.clear()
    v39.CFG.update(seed=1, T=T, budget=None, init="two", a=0.5, u_abstain=u_abstain, decay=decay_ladder(T), D=len(DICT),
                   dict_index={p: i for i, p in enumerate(DICT)}, rho=None, argmax=False, commons=False,
                   mean_weights=v39.actr_weights(T), price=lam)
    v39.CTX.update(struct_cache={}, births_rec=[], relearn=[], drift=[], cost_mismatch=[], answers=None, output=None,
                   config=CONFIG)
    if "amb_local" in SW_FLAGS:           # tools/v3_run.py（v3.10urta）:447-449：v39.CFG["amb_local"]＝True（v39.CFG は件ごとに作り直すので、ここで毎回入れる）
        v39.CFG["amb_local"] = True
    for d in (B.STATS, B.CFG, B.CTX):
        d.clear()
    B.CFG.update(seed=1, alpha=1.0, lam=lam, nohash=True)
    B.STATS.update(commons_lt2=0, chose_new=0, chose_existing=0, ties=0, new_excluded_structure=0, assim_impossible=0,
                   no_candidate=0, dC_mismatch=0, assim_match0=0, assim_hist0=0, zero_release=0, retire_candidate_evals=0,
                   score_other_position=0, score_role_scored=0, score_role_scored_pos_differs=0, score_role_other_target=0,
                   score_role_old_would_score_other=0, score_role_old_would_score_no_target=0, cfg={})
    B.CTX.update(R_B_trial=0.0, R_E_trial=0.0, disclosed=None, L_score={})
    histrole.STATS.clear()
    histrole.STATS.update(histrole._stats_zero())


def ptable(**over):
    c = {p: 16 for p in DICT}
    c.update(over)
    return FrequencyTable(c, sum(c.values()), 0.1, frozenset(p for p, n in c.items() if n > 0))


# 定義：席の番号 0〜5 が s1〜s6。一階の四本は物 x・y の組に載る
LAYOUT = {"A": ["push", "fold", "bind_s", "cut", "turn", "bind_a"], "B": ["push", "fold", "bind_s", "wrap", "stack", "bind_b"]}


def make_def(name, typ="A", slots=range(6), alive=None, preds=None, reg_count=1, registered_at=0):
    names = list(LAYOUT[typ])
    if preds:
        for s, p in preds.items():
            names[s] = p
    rid = lambda s: f"{name}_s{s + 1}"  # noqa: E731
    rows = []
    for s in slots:
        if s == 2:
            args = (rid(0), rid(1))
        elif s == 5:
            args = (rid(3), rid(4))
        else:
            args = ("x", "y")
        rows.append(Constituent(s, registered_at, Relation(rid(s), names[s], args), PRICE,
                                True if alive is None else alive.get(s, True)))
    return NamedDefinition(name, tuple(rows), len(rows), registered_at, reg_count)


def make_scene(typ, hide=None, gid="scene", tag="q"):
    """型 typ の場面（物 a・b）。hide は伏せる述語（その関係を除き、親の引数には ID を残す）。関係の ID は述語ごとに q_<述語>。"""
    names = LAYOUT[typ]
    rid = {s: f"{tag}_{names[s]}" for s in range(6)}
    rels = []
    for s in range(6):
        if s == 2:
            args = (rid[0], rid[1])
        elif s == 5:
            args = (rid[3], rid[4])
        else:
            args = ("a", "b")
        r = Relation(rid[s], names[s], args)
        if names[s] != hide:
            rels.append(r)
    hidden = None if hide is None else Relation(f"{tag}_{hide}", hide, ("a", "b"))
    return RelationGraph(gid, (Entity("a"), Entity("b")), tuple(rels)), hidden


def zero_rec(st="F", t=10, gen=0):
    return v39.SeatRec(gen, st, t, t, v39.ZERO4, v39.ZERO4)


def make_state(defs, hist=None, seats=None, ph=None, traces=()):
    if hist is None:
        hist = {}
        for d in defs:
            for row in d.constituents:
                if row.alive:
                    hist[(d.name, row.slot_index)] = {row.relation.predicate: 2}
    if seats is None:
        seats = {}
        for d in defs:
            for row in d.constituents:
                seats[(d.name, row.slot_index)] = zero_rec(v39.seat_state(d, row, hist))
    return S39(definitions={d.name: d for d in defs}, slot_history=hist, p_hat=ph or ptable(), v39_seats=seats,
               prototype=Prototype(tuple(traces)))


def predict(state, scene, t=10):
    out, pend = v39.predict(SimpleNamespace(target_graph_partial=scene), state, CONFIG, Random(0))
    tr = out.trace
    pred = out.prediction
    ans = v39.CTX.get("answers")
    return out, {"R_used": tr.get("R_used"), "support": tr.get("support_at_adoption"), "denominator": tr.get("m_live"),
                 "required": _need(0.67, tr.get("m_live")) if tr.get("m_live") else None,
                 "passed": [x["R"] for x in tr.get("tau_passed_defs", [])],
                 "answer": (f"{pred.edge.predicate}({','.join(pred.edge.arguments)})" if hasattr(pred, "edge") else "abstain"),
                 "abstain_reason": getattr(pred, "reason", None), "path": pend.prediction_path,
                 "role_targets": ({it["slot"]: it.get("cid") for it in ans["items"]} if ans else None),
                 "role_why": ({it["slot"]: it.get("cid_why") for it in ans["items"]} if ans else None),
                 "answers": ({it["slot"]: it.get("ans") for it in ans["items"]} if ans else None)}, ans


def score(state, ans, received, t=10):
    B.CTX["L_score"] = v39.code_lengths(state.p_hat)
    before = {k: v39.rec_means(r, t) for k, r in state.v39_seats.items()}
    seats, scored = v39.score_answers(state.v39_seats, ans, received, t)
    inc = {}
    for k, r in seats.items():
        a = v39.rec_means(r, t)
        d = tuple(round(x - y, 12) for x, y in zip(a[:3], before[k][:3]))
        if any(d):
            inc[f"s{k[1] + 1}"] = {"F": d[0], "H": d[1], "U": d[2]}
    return seats, inc, scored



RES = []


def case(cid, expected, actual, checks, note="", status=None):
    ok = all(v for _, v in checks)
    st = status or ("PASS" if ok else "DIFFERENCE")
    RES.append({"id": cid, "status": st, "expected": expected, "actual": actual, "checks": [[n, bool(v)] for n, v in checks],
                "pass": ok, "note": note})
    print(cid, st, [n for n, v in checks if not v])
