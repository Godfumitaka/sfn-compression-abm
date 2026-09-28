"""v3.8 の会計（旗 --own-evidence、tools/v38.py、D-08〜D-11）の小さな例（2026-09-28 夕、付録 5 節の T02・T04・T05・T09・T12・T13 と D-09）。

主の世界の実データ（主 hide の 8 本）では、反証（T13）・引数違い（T05）・外れ＋開示の ①（T09 の罰の側）に当てはまる試行が無かったので、
分類と回数の更新を、tools/v38.py の包みそのものに小さく組み立てた場面・行・蓄積を渡して確かめる。
例の場面：物 a・b・c。a と b の間に fold が見えている（wrap は伏せられている）。写し x→a・y→b・z→c。
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import abm.accounting as A  # noqa: E402
import abm.loop as loop  # noqa: E402
from abm.accounting import decay_ladder, initial_merit  # noqa: E402
from abm.definition import Constituent, FrozenPrice  # noqa: E402
from abm.domains import Abstain, EdgePrediction, Entity, Relation, RelationGraph  # noqa: E402
from abm.feedback import FeedbackCoinResult  # noqa: E402
from abm.accounting import OracleScore  # noqa: E402

PRICE = FrozenPrice(1.0, 0, 0.0, 3)
SCENE = RelationGraph("scene", (Entity("a"), Entity("b"), Entity("c")), (Relation("s_fold", "fold", ("a", "b")),))
EMAP = {"x": "a", "y": "b", "z": "c"}
RMAP: dict = {}
WRAP_AB = Relation("h_wrap", "wrap", ("a", "b"))          # 伏せ辺（研究者用）
PUSH_BA = Relation("h_push", "push", ("b", "a"))


def row(slot, pred, args, rid=None):
    return Constituent(slot, 3, Relation(rid or f"r{slot}", pred, args), PRICE, True)


_ORIG = {"classify_row": loop.classify_row, "update_merit": loop.update_merit, "participation": A.participation}


class _Fresh:
    """本番と同じ順（--no-charge2 → --own-evidence）で入れ直す。前の検査の差し替えは外してから。"""

    def install(self, fo):
        import importlib
        import nocharge2
        import v38
        loop.classify_row = _ORIG["classify_row"]; loop.update_merit = _ORIG["update_merit"]; A.participation = _ORIG["participation"]
        nocharge2._REAL.clear(); v38._REAL.clear()
        importlib.reload(nocharge2).install()
        m = importlib.reload(v38)
        m.install(fo)
        self.m = m
        return m


def fresh():
    loop.classify_row = _ORIG["classify_row"]; loop.update_merit = _ORIG["update_merit"]; A.participation = _ORIG["participation"]
    return _Fresh()


def classify(v38, r, received=None, src_row=None, pred_matches=False):
    v38 = getattr(v38, "m", v38)
    v38.CTX.clear(); v38.CTX.update(active=True, received=received, src_row=src_row, rows=[], pred_matches_received=pred_matches)
    return loop.classify_row(r, SCENE, EMAP, RMAP)


def test_t04_visible_other_predicate_is_neutral_until_disclosed():
    v38 = fresh(); v38.install(io.StringIO())
    wrap = row(0, "wrap", ("x", "y"))
    assert classify(v38, wrap) == "③"                       # fold が見えていることだけでは罰も反証も無い（開示なし＝未確認）
    assert classify(v38, wrap, received=WRAP_AB) == "充足"    # wrap(a,b) の開示で、完全一致として確認
    assert classify(v38, row(1, "fold", ("x", "y"))) == "充足"  # 見えている関係は今までどおり確認


def test_t05_same_predicate_other_arguments_is_not_confirmed():
    v38 = fresh(); v38.install(io.StringIO())
    push = row(0, "push", ("x", "y"))                        # push(a,b)
    assert classify(v38, push, received=PUSH_BA) == "反証"    # push(b,a)（引数が逆）の開示では確認にしない
    assert classify(v38, push, received=Relation("h", "push", ("c", "a"))) == "反証"


def test_t13_refutation_only_with_disclosure_and_determined_position():
    v38 = fresh(); v38.install(io.StringIO())
    lock = row(0, "lock", ("x", "y"))
    assert classify(v38, lock) == "③"                        # 開示なし：中立
    assert classify(v38, lock, received=WRAP_AB) == "反証"    # 開示あり・位置が決まる・見えている＋開示に無い：反証


def test_t12_undetermined_higher_order_row_not_refuted_but_confirmable_by_prediction():
    v38 = fresh(); v38.install(io.StringIO())
    child = row(0, "wrap", ("x", "y"), rid="c0")             # 子（写しに無い）
    parent = row(1, "allow", ("c0", "z"), rid="p1")           # 子を引数に持つ高階の行：位置が決まらない
    assert classify(v38, parent, received=WRAP_AB) in ("③", "判定不能")
    assert classify(v38, parent, received=WRAP_AB, src_row="p1", pred_matches=True) == "充足"
    assert classify(v38, child, received=WRAP_AB) == "充足"


def test_d09_counts_confirm_evaluate_use():
    v38 = fresh(); v38.install(io.StringIO())
    decay = decay_ladder(1740)
    base = initial_merit(0, 3, 0, 1740)

    def step(reason_row, received):
        classify(v38, reason_row, received=received)
        new = v38.m.CTX["rows"][-1]["新"]
        return loop.update_merit(base, decay, matched=new == "充足", filled_scored=False, alpha=0.0, applied=True), new

    conf, r1 = step(row(0, "wrap", ("x", "y")), WRAP_AB)
    refu, r2 = step(row(0, "lock", ("x", "y")), WRAP_AB)
    unc, r3 = step(row(0, "lock", ("x", "y")), None)
    assert (r1, r2, r3) == ("充足", "反証", "③")
    f = decay
    exp_basis_conf = tuple(b * k + 1.0 for b, k in zip(base.basis, f))
    exp_basis_none = tuple(b * k for b, k in zip(base.basis, f))
    exp_opp = tuple(b * k + 1.0 for b, k in zip(base.opportunity_basis, f))
    exp_eval_plus = tuple(b * k + 1.0 for b, k in zip(base.opportunity_basis, f))
    exp_eval_zero = tuple(b * k for b, k in zip(base.opportunity_basis, f))
    assert conf.basis == exp_basis_conf and conf.eval_basis == exp_eval_plus and conf.opportunity_basis == exp_opp
    assert refu.basis == exp_basis_none and refu.eval_basis == exp_eval_plus and refu.opportunity_basis == exp_opp
    assert unc.basis == exp_basis_none and unc.eval_basis == exp_eval_zero and unc.opportunity_basis == exp_opp
    # 参加率は Σbasis ÷ Σeval_basis（未確認は分母も分子も増やさない。生まれたときの seed は basis・eval とも同じ）
    assert A.participation(unc) == sum(unc.basis) / sum(unc.eval_basis)
    assert A.participation(base) == 1.0


def test_t09_t02_received_evidence_survives_internal_flag_and_research_answer_is_not_read():
    seen = []

    def inner(state, output, scene, config, horizon, score, coin, revealed_edge):
        import v38 as m
        seen.append((coin.f_fired, m.CTX.get("received")))
        return SimpleNamespace(), {}

    def d32_like(state, output, scene, config, horizon, score, coin, revealed_edge):
        from dataclasses import replace
        return inner(state, output, scene, config, horizon, score, replace(coin, f_fired=False), revealed_edge)

    saved = loop._update_accounting
    try:
        loop._update_accounting = d32_like
        v38 = fresh(); v38.install(io.StringIO())
        cfg = SimpleNamespace(alpha=0.0, pending_claims=False, local_lambda=1.0)
        out = SimpleNamespace(prediction=Abstain("x"), trace={"R_used": None})
        miss = OracleScore("失敗", False, 1.0)
        loop._update_accounting(None, out, SCENE, cfg, 1740, miss, FeedbackCoinResult("agent", 7, 0.1, 0.5, True), WRAP_AB)
        loop._update_accounting(None, out, SCENE, cfg, 1740, miss, FeedbackCoinResult("agent", 8, 0.9, 0.5, False), WRAP_AB)
        loop._update_accounting(None, out, SCENE, cfg, 1740, miss, FeedbackCoinResult("agent", 9, 0.9, 0.5, False), PUSH_BA)
    finally:
        fresh()
        loop._update_accounting = saved
    assert seen[0] == (False, WRAP_AB)      # 内側は f_fired＝False で呼ばれても、受け取った開示は届く（T09）
    assert seen[1] == (False, None)         # 開示なし：研究者用の伏せ辺は読まない（T02）
    assert seen[2] == (False, None)         # 伏せ辺だけを変えても、内側に届くものは同じ（T02）


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
