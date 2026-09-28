"""v3.8 の検査 T02（付録 5 節）：同じ本人の状態・可視部・開示なしで、研究者用の伏せた正解だけを変えても、本人の学習結果が同じ。
同じプロセスの中で走らせ（~/diag0928/sync_exec.py）、開示の無い試行ごとに、会計（一番外の包み）を二回呼ぶ：
一回目は本当の伏せ辺、二回目は伏せ辺を場面の別の関係に差し替えたもの。返った次の状態と会計の記録が一致するかを比べる（研究者用の採点は比べない）。
走行は一回目の結果で進む。模型は変えない。
使い方（作業場所の根で）：T02_OUT=<json> python3.12 t02.py <v3_run.py の引数…（--own-evidence を含む）>"""
import json, os, runpy, sys
from dataclasses import replace
ROOT = os.path.abspath(".")
sys.path[:0] = [ROOT, ROOT + "/tools", os.path.expanduser("~/diag0928")]
import sync_exec  # noqa: F401
import sweep
OUT = os.environ["T02_OUT"]
real_run_one = sweep.run_one
RES = {"比べた試行": 0, "一致": 0, "違う": 0, "違う例": [], "差し替えられなかった": 0}


def run_one(task):
    import abm.loop as loop
    inner = loop._update_accounting          # ★ 一番外（checks・v38 を含む）

    def acc(state, output, scene, config, horizon, score, coin, revealed_edge):
        out1 = inner(state, output, scene, config, horizon, score, coin, revealed_edge)
        if not coin.f_fired:
            other = next((r for r in scene.relations if (r.predicate, r.arguments) != (revealed_edge.predicate, revealed_edge.arguments)), None)
            if other is None:
                RES["差し替えられなかった"] += 1
            else:
                fake = replace(revealed_edge, predicate=other.predicate, arguments=other.arguments)
                out2 = inner(state, output, scene, config, horizon, score, coin, fake)
                RES["比べた試行"] += 1
                same = (out1[0] == out2[0]) and (out1[1] == out2[1])
                RES["一致" if same else "違う"] += 1
                if not same and len(RES["違う例"]) < 3:
                    RES["違う例"].append({"t": coin.t, "状態が同じ": out1[0] == out2[0], "記録が同じ": out1[1] == out2[1]})
        return out1

    loop._update_accounting = acc
    try:
        return real_run_one(task)
    finally:
        json.dump(RES, open(OUT, "w"), ensure_ascii=False, indent=1)


sweep.run_one = run_one
sys.argv = ["v3_run.py"] + sys.argv[1:]
runpy.run_path(ROOT + "/tools/v3_run.py", run_name="__main__")
