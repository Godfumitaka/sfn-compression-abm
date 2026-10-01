"""照合器の検査 3-3：模型の層を一つずつ（2026-10-01 朝の委任書）。★ 検査だけ。旗なし（今）と旗あり（--strict-pc）を並べる。
定義 D（物 a・b）：s0 hold(a,b)・s1 wrap(a,b)・s2 P(s0,s1)・s3 push(a,b)（親なし）。場面（物 x・y）は件ごとに作る。
期待は、各層の今の決まり（tools/v39.py・tools/ustruct.py・abm/sme.py・tools/answergap.py の説明）から、旗ありの写像で決まるものを書く。
使い方  SW_TREE=<作業場所> SW_FLAGS=u_struct,relearn_init,tie_struct,amb_local python3.12 tools/model_layer_checks.py <出力の .json>"""
import json
import os
import sys
from random import Random

sys.path.insert(0, os.path.expanduser("~/sw_audit"))
import swcommon as sw  # noqa: E402
import abm.sme as sme  # noqa: E402
from abm.definition import Constituent, NamedDefinition  # noqa: E402
from abm.domains import Entity, Relation, RelationGraph  # noqa: E402
import answergap  # noqa: E402
import strictpc  # noqa: E402
import v39  # noqa: E402


def G(rels, hidden=()):
    rs = tuple(Relation(i, p, tuple(a)) for i, p, a in rels if i not in hidden)
    return RelationGraph("t", (Entity("x"), Entity("y")), rs)


def D(states):
    """states：{席: "F"／"H"／"U"}。H の履歴は HIST、U は履歴なし。"""
    base = [("s0", "hold", ("a", "b")), ("s1", "wrap", ("a", "b")), ("s2", "P", ("s0", "s1")), ("s3", "push", ("a", "b"))]
    rows = tuple(Constituent(k, 0, Relation(i, p, a), sw.PRICE, states.get(k, "F") == "F") for k, (i, p, a) in enumerate(base))
    d = NamedDefinition("D", rows, 4, 0, 1)
    hist = {}
    for k, (_i, p, _a) in enumerate(base):
        st = states.get(k, "F")
        if st == "F":
            hist[("D", k)] = {p: 2}
        elif st == "H":
            hist[("D", k)] = HIST.get(k, {p: 2})
    return d, hist


HIST = {0: {"hold": 1, "cut": 1}}
SC_HOLD = [("d0", "hold", ("x", "y")), ("d1", "wrap", ("x", "y")), ("Q", "P", ("d0", "d1")), ("d3", "push", ("x", "y"))]
SC_PUSH = [("d0", "tilt", ("x", "y")), ("d1", "wrap", ("x", "y")), ("Q", "P", ("d0", "d1"))]   # d0 の名は定義に無い tilt（s3 push と取り合わないため）
SC_CUT = [("d0", "cut", ("x", "y")), ("d1", "wrap", ("x", "y")), ("Q", "P", ("d0", "d1"))]
SC_HID = [("d1", "wrap", ("x", "y")), ("Q", "P", ("dH", "d1"))]    # s0 の位置が伏せられている


def amap(states, sc):
    d, hist = D(states)
    _g, al = v39.map_v39(d, hist, sc)
    return d, hist, al


def tri(d, hist, al, sc):
    vis = {r.relation_id for r in sc.relations}
    t = [0, 0, 0]
    for row in d.constituents:
        if v39.seat_state(d, row, hist) == "U":
            continue
        m = al.relation_mapping.get(row.relation.relation_id)
        t[0 if m in vis else 1 if m is not None else 2] += 1
    return {"見えている関係に対応": t[0], "親から伏せた位置に対応": t[1], "対応先なし": t[2]}


def run():
    out = {}
    # L1 F の名の条件
    _d, _h, a1 = amap({}, G(SC_HOLD))
    _d, _h, a2 = amap({}, G(SC_PUSH))
    out["L1 F の名の条件"] = {"hold の場面": dict(a1.relation_mapping), "tilt の場面": dict(a2.relation_mapping),
                          "期待（旗あり）": "hold の場面で s0→d0・s2→Q。tilt の場面で s0 も s2 も写らない",
                          "通った": a1.relation_mapping.get("s0") == "d0" and a1.relation_mapping.get("s2") == "Q"
                          and "s0" not in a2.relation_mapping and "s2" not in a2.relation_mapping}
    # L2 H の名の条件（履歴 {hold, cut}）
    _d, _h, b1 = amap({0: "H"}, G(SC_CUT))
    _d, _h, b2 = amap({0: "H"}, G(SC_PUSH))
    out["L2 H の名の条件（履歴 hold・cut）"] = {"cut の場面": dict(b1.relation_mapping), "tilt の場面": dict(b2.relation_mapping),
                                         "期待（旗あり）": "cut の場面で s0→d0・s2→Q。tilt の場面で s0 も s2 も写らない",
                                         "通った": b1.relation_mapping.get("s0") == "d0" and b1.relation_mapping.get("s2") == "Q"
                                         and "s0" not in b2.relation_mapping and "s2" not in b2.relation_mapping}
    # L3 U と --u-struct
    _d, _h, c1 = amap({0: "U"}, G(SC_HID, ()))
    _d, _h, c2 = amap({0: "U"}, G(SC_PUSH))
    out["L3 U の席と --u-struct"] = {"s0 の位置が伏せられた場面": dict(c1.relation_mapping), "s0 の位置に tilt が見えている場面": dict(c2.relation_mapping),
                                   "期待（旗あり）": "伏せた場面で s2→Q・s0→dH（見えていない位置）。見えている場面では、U の席は自分の対の候補を持たないので、"
                                                     "並行連結の (b) を満たせず s2 は写らない（記録。--u-struct の『U の子が見えている関係に当たる』は旗ありでは起きない）",
                                   "通った": c1.relation_mapping.get("s2") == "Q" and c1.relation_mapping.get("s0") == "dH"
                                   and "s2" not in c2.relation_mapping}
    # L4 支持の三分類（全部 F、s0 の位置が伏せられた場面。s3 push は場面に無い）
    d, h, al = amap({}, G(SC_HID))
    t = tri(d, h, al, G(SC_HID))
    out["L4 支持の三分類"] = {"三分類": t, "写像": dict(al.relation_mapping),
                          "期待（旗あり）": {"見えている関係に対応": 2, "親から伏せた位置に対応": 1, "対応先なし": 1},
                          "通った": t == {"見えている関係に対応": 2, "親から伏せた位置に対応": 1, "対応先なし": 1}}
    # L5 投影（s3 push は場面に無く、物は写っている → push(x,y) を投影）
    g, al = v39.map_v39(d, h, G(SC_HID))
    pr = sme.project(al, v39.v39_graph(d, h), G(SC_HID))
    ans = getattr(getattr(pr, "edge", None), "predicate", None), list(getattr(getattr(pr, "edge", None), "arguments", ()) or ())
    # 期待：投影の候補は s0 hold（見えていない位置 dH に写り、物も写っている）と s3 push（写らない）。順位は写った親の数
    #   （abm/sme.py:381-392 _projection_support）で、s0 は親 P が写っているので 1、s3 は 0 → hold(x,y)。
    #   ★ 最初は push を期待に書いたが、コードの決まりから書き直した（報告に書く）
    out["L5 投影"] = {"答え": ans, "棄権": getattr(pr, "reason", None), "期待（旗あり）": ["hold", ["x", "y"]],
                    "通った": ans == ("hold", ["x", "y"])}
    # L6 穴埋め（s0 が H 履歴 {hold:1, cut:1}… 同点になるので履歴を {hold:2, cut:1} にして、伏せた位置 dH を hold で埋める）
    HIST[0] = {"hold": 2, "cut": 1}
    d6, h6 = D({0: "H"})
    _g, al6 = v39.map_v39(d6, h6, G(SC_HID))
    ph = sw.ptable(hold=16, cut=16, wrap=16, push=16, P=16)
    fl = v39.fill_v39(d6, G(SC_HID), al6.entity_mapping, al6.relation_mapping, h6, ph, "most_frequent", Random(0),
                      higher_order_predicates=frozenset({"P"}), local_lambda=1.0)
    got = [(r.predicate, list(r.arguments)) for r in fl.relations]
    out["L6 穴埋め"] = {"穴埋めの候補": got, "あいまい": fl.ambiguous, "期待（旗あり）": [["hold", ["x", "y"]]],
                      "通った": got[:1] == [("hold", ["x", "y"])]}
    HIST[0] = {"hold": 1, "cut": 1}
    # L7 --answer-gap の欠けた位置の集合
    gaps = sorted(answergap.gap_ids(G(SC_HID)))
    out["L7 --answer-gap の欠けた位置"] = {"D": gaps, "期待": ["dH"], "通った": gaps == ["dH"]}
    return out


sw.setup()
res = {"旗なし": run()}
strictpc.install()
sw.setup()
res["旗あり"] = run()
json.dump(res, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, v in res["旗あり"].items():
    print(k, "通った" if v["通った"] else "通らない", "| 旗なしで期待どおりか：", res["旗なし"][k]["通った"])
