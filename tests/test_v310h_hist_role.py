"""v3.10h（旗 --hist-role、tools/histrole.py）の小例：m1 の一階の席の履歴を、親の行の写しで集める。
例の場面：物 A・B の上に一階の関係が四本（hold・brk・wrap・pull）、二階の cause(hold, brk)。土台は物 a・b の上の hold・brk・wrap と cause(hold, brk)。
今の集め方（物の組）では、一階の席に同じ物の組の四本の述語が全部入る。直したあとは、親の cause が写った場面の関係の同じ位置の子だけ。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_v39_budget as T  # noqa: E402
import abm.abstraction as ab  # noqa: E402
import histrole  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
from abm.sme import map_graphs  # noqa: E402

KW = dict(base_written_at=0, horizon=100, pricing_rule="legacy", refill_rule="legacy", local_lambda=1.0)
ORIG = ab.m1
NEW = histrole.make(ORIG, real=True)
BASE = RelationGraph("base", (Entity("a"), Entity("b")),
                     (Relation("r1", "hold", ("a", "b")), Relation("r2", "brk", ("a", "b")), Relation("r3", "wrap", ("a", "b")),
                      Relation("c1", "cause", ("r1", "r2"))))


def scene(parent="cause", hide=()):
    rels = [Relation("s1", "hold", ("A", "B")), Relation("s2", "brk", ("A", "B")), Relation("s3", "wrap", ("A", "B")),
            Relation("s4", "pull", ("A", "B")), Relation("t1", parent, ("s1", "s2"))]
    return RelationGraph("scene", (Entity("A"), Entity("B")), tuple(r for r in rels if r.relation_id not in hide))


def run(m1, st, target, name=None, trial=5):
    histrole.STATS.clear()
    histrole.STATS.update(histrole._stats_zero())
    al = map_graphs(BASE, target).alignment
    return m1(st, BASE, target, al, trial, name=name, **KW)


def slots(st, R):
    d = st.definitions[R]
    return {row.relation.relation_id: st.slot_history.get((R, row.slot_index)) for row in d.constituents}


def born():
    T.setup()
    st0 = T.state([], {}, {})
    return st0, run(ORIG, st0, scene()), run(NEW, st0, scene())


def same_except_first(o, n, R):
    """高階の席の履歴と、履歴の外の状態は元の m1 と同じ。"""
    assert o.definitions == n.definitions and o.merit == n.merit and o.embed == n.embed and o.exceptions == n.exceptions
    assert slots(o, R)["c1"] == slots(n, R)["c1"]


def test_birth_first_order_seat_takes_child_of_mapped_parent():
    _, (o, ro), (n, rn) = born()
    R = ro["R"]
    assert rn["R"] == R
    assert slots(o, R)["r1"] == {"hold": 1, "brk": 1, "wrap": 1, "pull": 1}   # 今：物の組の四本が全部
    assert slots(n, R) == {"c1": {"cause": 1}, "r1": {"hold": 1}, "r2": {"brk": 1}}
    same_except_first(o, n, R)
    assert histrole.STATS["first_observed"] == 2 and histrole.STATS["obs_old_first"] == 8 and histrole.STATS["obs_new_first"] == 2


def test_parent_not_mapped_adds_nothing():
    _, _, (n, rn) = born()
    R = rn["R"]
    (o2, _), (n2, _) = run(ORIG, n, scene(parent="enable"), name=R, trial=6), run(NEW, n, scene(parent="enable"), name=R, trial=6)
    assert slots(n2, R)["r1"] == {"hold": 1} and slots(n2, R)["r2"] == {"brk": 1}   # 足さない（推測で足さない）
    assert slots(o2, R)["r1"] == {"hold": 2, "brk": 1, "wrap": 1, "pull": 1}
    assert slots(n2, R)["c1"] == slots(o2, R)["c1"] == {"cause": 1, "enable": 1}     # 高階は今のまま
    assert histrole.STATS["first_parent_unmapped"] == 2


def test_parentless_first_order_rows_get_no_observation():
    T.setup()
    st0 = T.state([], {}, {})
    (o, ro), (n, rn) = run(ORIG, st0, scene(parent="enable")), run(NEW, st0, scene(parent="enable"))
    R = ro["R"]
    assert set(slots(n, R)) == {"r1", "r2"}                       # 親の cause は材料に入らない（述語が違う）
    assert slots(n, R) == {"r1": None, "r2": None}               # 鍵も作らない
    assert slots(o, R)["r1"] == {"hold": 1, "brk": 1, "wrap": 1, "pull": 1}
    assert histrole.STATS["first_no_parent"] == 2 and histrole.STATS["birth_first_parentless"] == 2


def test_hidden_child_adds_nothing():
    _, _, (n, rn) = born()
    R = rn["R"]
    tg = scene(hide=("s1",))
    (o2, _), (n2, _) = run(ORIG, n, tg, name=R, trial=6), run(NEW, n, tg, name=R, trial=6)
    assert slots(n2, R)["r1"] == {"hold": 1}                     # 子（伏せられた hold）が見えない：足さない
    assert slots(n2, R)["r2"] == {"brk": 2}
    assert slots(o2, R)["r1"] == {"hold": 1, "brk": 1, "wrap": 1, "pull": 1}
    same_except_first(o2, n2, R) if o2.definitions == n2.definitions else None


def test_off_is_untouched():
    # 旗を切れば包みは入らない（install を呼ばない限り abm.abstraction.m1 は元のまま）
    import abm.loop as loop
    assert ab.m1 is ORIG and loop.m1 is ORIG


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
