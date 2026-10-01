"""関門 3 の小さな例（2026-10-01 午前・改訂の段 3）：シールの席を U にすると世界 2 のドアの答えが外れる記憶の状態で、
--cf-learn の積む値（tools/cflearn.py variants_correct と同じ計算、rec_add で積む）から、シールの席の R̄U − R̄H が世界 2 で正、世界 1 で 0 になるか。
記憶の状態（世界ごとに、その世界の場面から作る）：
  D_e：甲・例外の場面の構造の関係を全部 F にした定義（tools/shop/gate2.py と同じ作り）。ただしシールの席は H（履歴 {sig_e: 2}）。登録試行 0。
  D_n：甲・通常の場面から同じく作った定義。シールの席は U（履歴なし）。登録試行 5（同点のときの並べ方で D_n が先に来る）。
問い：甲・例外の場面でドアを伏せたもの。開示はドアの関係。
  シール H のまま：D_e は支持 17/17、D_n は 16/16 で、割合は同じ・F＋H の席の数で D_e が先 → D_e の答え。
  D_e のシールを U にすると：どちらも 16/16 で、登録の新しい D_n が先 → D_n の答え（世界 2 では通常の答え＝外れ、世界 1 では甲は常に X＝当たり）。
使い方  SW_TREE=<作業場所> SW_FLAGS=u_struct,relearn_init,tie_struct,amb_local SW_STRICT=1 python3.12 tools/shop/cflearn_check.py <出力の .json>"""
import json
import os
import sys
from dataclasses import replace
from random import Random
from types import SimpleNamespace

sys.argv_out = sys.argv[1]
sys.argv = [sys.argv[0], "/dev/null"]
import importlib.util  # noqa: E402
import io  # noqa: E402
import contextlib  # noqa: E402

spec = importlib.util.spec_from_file_location("g2", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate2.py"))
g = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(g)          # 場面・定義・予測の部品（本番と同じ差し替え、--strict-pc つき）
import cflearn  # noqa: E402
import shopworld as sh  # noqa: E402
import v39  # noqa: E402
import v310be  # noqa: E402


def run(world):
    g.WORLD = world
    g.setup()
    de, ie = g.make_def("D_e", "甲", "e")
    dn, inn = g.make_def("D_n", "甲", "n")
    dn = replace(dn, registered_at=5)
    se, sn = g.slot_of(de, ie["sig_id"]), g.slot_of(dn, inn["sig_id"])
    de = replace(de, constituents=tuple(replace(r, alive=False) if r.slot_index == se else r for r in de.constituents))
    dn = replace(dn, constituents=tuple(replace(r, alive=False) if r.slot_index == sn else r for r in dn.constituents))
    hist = {}
    for d in (de, dn):
        for r in d.constituents:
            if r.alive:
                hist[(d.name, r.slot_index)] = {r.relation.predicate: 2}
    hist[("D_e", se)] = {sh.SIG_E: 2}
    st = g.state_of([de, dn], hist=hist)
    part, G, info = g.door_hidden("甲", "e")
    door = next(r for r in G.relations if r.relation_id == info["door_id"])
    ai = SimpleNamespace(target_graph_partial=part)
    out, _p = v39.predict(ai, st, g.CONFIG, Random(0))
    res = cflearn.variants_correct(st, ai, g.CONFIG, out.trace.get("R_used"), 10, door, out.prediction, v39.predict, 0)
    L = v39.code_lengths(st.p_hat)
    lp = v310be._ell(door.predicate, L)
    R = out.trace.get("R_used")
    stt, ok = res[se] if R == "D_e" else (None, {})
    rec = st.v39_seats[("D_e", se)]
    r = {k: (0.0 if v else lp) for k, v in ok.items()}
    inc = (0.0, r.get("H", 0.0), r.get("U", 0.0), 1.0)
    rec2 = v39.rec_add(rec, 10, inc)
    m0, m1 = v39.rec_means(rec, 10), v39.rec_means(rec2, 10)
    return {"世界": world, "ドアの正解": door.predicate, "実際の答え": getattr(getattr(out.prediction, "edge", None), "predicate", None),
            "選ばれた定義": R, "シールの席（D_e）の今の状態": stt, "シールの席の写しごとの正解": ok, "積む値": {"H": r.get("H"), "U": r.get("U")},
            "R̄U−R̄H（積む前）": m0[2] - m0[1], "R̄U−R̄H（積んだ後）": m1[2] - m1[1]}


out = {f"世界 {w}": run(w) for w in (2, 1)}
w2, w1 = out["世界 2"], out["世界 1"]
out["関門"] = {"世界 2 で R̄U−R̄H が正": w2["R̄U−R̄H（積んだ後）"] > 0, "世界 1 で 0": abs(w1["R̄U−R̄H（積んだ後）"]) < 1e-12}
json.dump(out, open(sys.argv_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(out, ensure_ascii=False, indent=0, default=str))
