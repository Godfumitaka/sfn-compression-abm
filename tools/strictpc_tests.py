"""--strict-pc の小さな例（2026-10-01 朝の委任書の 2-2。例と期待は Claude の手元の例）。★ 検査だけ。
土台：~/sw_audit/swcommon.py（本番と同じ照合の差し替えの一式：fixorder2・fix2・v39 の候補・ustruct ほか）を、この作業場所のコードで読む（SW_TREE）。
旗なし（今の写像）と旗あり（tools/strictpc.py を入れたあと）の写像を並べ、旗ありが期待どおりかを確かめる。
使い方  SW_TREE=<作業場所> SW_FLAGS=u_struct,relearn_init,tie_struct,amb_local python3.12 tools/strictpc_tests.py <出力の .json>"""
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/sw_audit"))
import swcommon as sw  # noqa: E402
import abm.sme as sme  # noqa: E402
from abm.definition import Constituent, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
import strictpc  # noqa: E402
import v39  # noqa: E402


def G(gid, ents, rels):
    return RelationGraph(gid, tuple(Entity(e) for e in ents), tuple(Relation(i, p, a) for i, p, a in rels))


T1B = G("b", "ab", [("c1", "hold", ("a", "b")), ("c2", "wrap", ("a", "b")), ("P", "P", ("c1", "c2"))])
CASES = {
    "T1": (T1B, G("t", "xy", [("d1", "push", ("x", "y")), ("d2", "wrap", ("x", "y")), ("Q", "P", ("d1", "d2"))]),
           {"c2": "d2"}),
    "T2": (G("b", "ab", [("c1", "hold", ("a", "b")), ("c2", "push", ("a", "b")), ("P", "P", ("c1", "c2"))]),
           G("t", "xy", [("d1", "push", ("x", "y")), ("d2", "hold", ("x", "y")), ("Q", "P", ("d1", "d2"))]),
           {"c1": "d2", "c2": "d1"}),
    "T4": (T1B, G("t", "xy", [("d2", "wrap", ("x", "y")), ("Q", "P", ("dHIDDEN", "d2"))]),
           {"P": "Q", "c2": "d2", "c1": "dHIDDEN"}),
    "T5": (G("b", "ab", [("c1", "hold", ("a", "b")), ("m1", "M", ("c1", "c1")), ("c2", "wrap", ("a", "b")), ("P", "P", ("m1", "c2"))]),
           G("t", "xy", [("d1", "push", ("x", "y")), ("n1", "N", ("d1", "d1")), ("d2", "wrap", ("x", "y")), ("Q", "P", ("n1", "d2"))]),
           {"c2": "d2"}),
}


def run_plain():
    return {k: dict(sme.map_graphs(b, t).alignment.relation_mapping) for k, (b, t, _e) in CASES.items()}


def h_seat():
    """ドアの席が H（履歴 {hold, hold_b}）の定義と、ドアが hold_b の場面。期待：ドアの席は写り、親も写る。"""
    rows = (Constituent(0, 0, Relation("c1", "hold", ("a", "b")), sw.PRICE, False),
            Constituent(1, 0, Relation("c2", "wrap", ("a", "b")), sw.PRICE, True),
            Constituent(2, 0, Relation("P", "P", ("c1", "c2")), sw.PRICE, True))
    d = NamedDefinition("D", rows, 3, 0, 1)
    hist = {("D", 0): {"hold": 2, "hold_b": 1}, ("D", 1): {"wrap": 2}, ("D", 2): {"P": 2}}
    sc = G("t", "xy", [("d1", "hold_b", ("x", "y")), ("d2", "wrap", ("x", "y")), ("Q", "P", ("d1", "d2"))])
    _g, al = v39.map_v39(d, hist, sc)
    return dict(al.relation_mapping)


sw.setup()
before = run_plain()
before_h = h_seat()
strictpc.install()
after = run_plain()
after_h = h_seat()
res = {}
for k, (_b, _t, exp) in CASES.items():
    res[k] = {"旗なし": before[k], "旗あり": after[k], "期待（旗あり）": exp, "通った": after[k] == exp}
res["H の席"] = {"旗なし": before_h, "旗あり": after_h, "期待（旗あり）": "c1（H）→d1 と P→Q を含む",
                "通った": after_h.get("c1") == "d1" and after_h.get("P") == "Q"}
res["_strictpc_STATS"] = strictpc.stats()
json.dump(res, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, v in res.items():
    if not k.startswith("_"):
        print(k, "通った" if v["通った"] else "通らない", "旗なし", v["旗なし"], "旗あり", v["旗あり"])
