"""U の席を子に持つ親の照合（2026-09-30 の委任書「U の席の問題の大きさを測る・名前の付け替えの確かめ」の 1）。★ 記録だけ。模型は変えない。
tools/v3_run.py をこの過程の中で一本だけ走らせ（台帳・side は包みの無い走行と一字一句同じであることを別に確かめる）、次を数える。
  「仮の照合」：tools/v39.py の照合の候補の規則のうち、U の子の引数だけを緩めたもの（U の子は見えている関係にも当てはまってよい。物には当てはまらない）。
  ほかは同じ（F は名前の一致、H は履歴の名、fixorder2 の写し）。本当の照合と比べ、U の子のせいで外れた親を見分ける。
  1 定義ごとの、U の子を持つ F・H の親の席の数（100 試行ごとの予測の前の状態と、走行の終わり）
  2 選ばれた定義（予測の select_definition の一番）について、U の子を持つ F・H の親のうち、
      本当の照合で写らず、仮の照合では場面の関係 Q に写り、Q のその子の位置の関係が見えているもの（＝その子の位置の関係が見えている場面で照合から外れた）
    その数・支持の割合の下がり（その数 ÷ F＋H）・門：支持＜必要数 ≦ 支持＋その数 の回数（その親を当てはまったと数えたら通っていた）
  3 m1（実際の鎖、同化）で、その試行の前に U だった席のうち、仮の照合で役割（親の同じ位置）に見えている関係があるのに、この m1 で観察（鍵）を受けなかった席
使い方  python3.12 tools/histrole_checks/uchild.py <出力 jsonl> -- <tools/v3_run.py の引数（--seeds は一つ、--workers 1）>
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
OUT = {"census": [], "select": [], "m1": []}


class Inline:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *a, **k):
        f = concurrent.futures.Future()
        try:
            f.set_result(fn(*a, **k))
        except BaseException as e:  # noqa
            f.set_exception(e)
        return f

    def shutdown(self, *a, **k):
        pass


def cf_candidates(base_graph, partial_graph):
    """tools/v39.py _install_candidates の写し。★ U の子の引数だけ、見えている関係にも当てはまってよい（物には当てはまらない）。"""
    import abm.sme as sme
    import v39
    from abm.sme import AlignmentCandidate
    _, hallow, ushield = v39.REG[id(base_graph)]
    base_relation_ids = sme._relation_ids(base_graph)
    partial_relation_ids = sme._relation_ids(partial_graph)
    partial_entity_ids = frozenset(e.entity_id for e in partial_graph.entities)
    candidates = []
    for left in sorted(base_graph.relations, key=sme._relation_key):
        allowed = hallow.get(left.relation_id)
        for right in sorted(partial_graph.relations, key=sme._relation_key):
            if len(left.arguments) != len(right.arguments):
                continue
            if right.predicate != left.predicate and (allowed is None or right.predicate not in allowed):
                continue
            entity_pairs, relation_pairs, compatible = [], [], True
            for left_arg, right_arg in zip(left.arguments, right.arguments, strict=True):
                if left_arg in ushield:
                    if right_arg in partial_entity_ids:          # ★ 物には当てはまらない（ここだけ緩める）
                        compatible = False
                        break
                    relation_pairs.append((left_arg, right_arg))
                    continue
                left_is_relation = left_arg in base_relation_ids
                right_is_relation = right_arg in partial_relation_ids
                right_is_unobserved = (not right_is_relation) and (right_arg not in partial_entity_ids)
                if left_is_relation and right_is_unobserved:
                    relation_pairs.append((left_arg, right_arg))
                    continue
                if left_is_relation != right_is_relation:
                    compatible = False
                    break
                if left_is_relation:
                    relation_pairs.append((left_arg, right_arg))
                else:
                    entity_pairs.append((left_arg, right_arg))
            if compatible:
                candidates.append(AlignmentCandidate(
                    base_relation_id=left.relation_id, partial_relation_id=right.relation_id,
                    predicate=left.predicate, arity=len(left.arguments),
                    entity_pairs=tuple(sorted(entity_pairs)), relation_pairs=tuple(sorted(relation_pairs))))
    return tuple(sorted(candidates, key=sme._candidate_order_key))


def cf_map(d, slot_history, scene):
    import abm.sme as sme
    import v39
    g = v39.v39_graph(d, slot_history)
    prev = sme._alignment_candidates
    sme._alignment_candidates = cf_candidates
    try:
        return sme.map_graphs(g, scene).alignment
    finally:
        sme._alignment_candidates = prev
        v39.unregister(g)


def u_parents(d, hist):
    """U の子を持つ F・H の親：[(親の行, 子の位置 k, U の子の行)]"""
    import v39
    st = {row.relation.relation_id: v39.seat_state(d, row, hist) for row in d.constituents}
    by_id = {row.relation.relation_id: row for row in d.constituents}
    out = []
    for p in d.constituents:
        if st[p.relation.relation_id] == "U":
            continue
        for k, a in enumerate(p.relation.arguments):
            if st.get(a) == "U":
                out.append((p, k, by_id[a]))
    return out


def census(state, t, tag):
    import v39
    per = {}
    for R, d in state.definitions.items():
        n = len({p.relation.relation_id for p, _, _ in u_parents(d, state.slot_history)})
        per[R] = n
    OUT["census"].append({"t": t, "tag": tag, "defs": len(per), "defs_with": sum(1 for v in per.values() if v), "parents": sum(per.values()),
                          "max": max(per.values(), default=0), "per_def": sorted(per.values(), reverse=True)})


def install_hooks(config_holder):
    import abm.agent_runtime as ar
    import abm.loop as loop
    import v39
    real_select = v39.select_definition

    def select_definition(state, scene, config):
        t = ST["t"]
        if t % 100 == 0:
            census(state, t, "予測の前")
        res = real_select(state, scene, config)
        if res is None:
            return res
        ratio, support, d, graph, al, n, tie, passed = res
        ups = u_parents(d, state.slot_history)
        vis = {r.relation_id: r for r in scene.relations}
        rec = {"t": t, "R": d.name, "n": n, "support": support, "need": ar._need(config.tau_acc, n), "u_parents": len({p.relation.relation_id for p, _, _ in ups})}
        if ups:
            cf = cf_map(d, state.slot_history, scene)
            excl = set()
            for p, k, u in ups:
                pid = p.relation.relation_id
                if pid in al.relation_mapping:
                    continue
                Q = vis.get(cf.relation_mapping.get(pid))
                if Q is None or k >= len(Q.arguments):
                    continue
                if Q.arguments[k] in vis:
                    excl.add(pid)
            rec["excluded"] = len(excl)
        else:
            rec["excluded"] = 0
        OUT["select"].append(rec)
        return res

    v39.select_definition = select_definition

    real_m1 = loop.m1

    def m1(state, base, target, alignment, trial, **kw):
        out, reg = real_m1(state, base, target, alignment, trial, **kw)
        if reg is not None and reg["was_extension"]:
            R = reg["R"]
            d = state.definitions.get(R)
            if d is not None:
                pre = state.slot_history
                us = [row for row in d.constituents if v39.seat_state(d, row, pre) == "U"]
                if us:
                    from abm.filling import _is_higher
                    rel_ids = {row.relation.relation_id for row in d.constituents}
                    cf = cf_map(d, pre, target)
                    vis = {r.relation_id: r for r in target.relations}
                    for u in us:
                        uid = u.relation.relation_id
                        role_vis = False
                        for p in d.constituents:
                            if v39.seat_state(d, p, pre) == "U":
                                continue
                            for k, a in enumerate(p.relation.arguments):
                                if a != uid:
                                    continue
                                Q = vis.get(cf.relation_mapping.get(p.relation.relation_id))
                                if Q is not None and k < len(Q.arguments) and Q.arguments[k] in vis:
                                    role_vis = True
                        observed = (R, u.slot_index) in out.slot_history
                        OUT["m1"].append({"t": trial, "R": R, "slot": u.slot_index, "higher": _is_higher(u.relation, rel_ids),
                                          "role_visible": role_vis, "observed": observed})
        return out, reg

    loop.m1 = m1

    real_pred = loop.predict

    def predict(agent_input, state, config, rng):
        config_holder["config"] = config
        return real_pred(agent_input, state, config, rng)

    loop.predict = predict
    real_acc = loop._update_accounting

    def acc(state, output, scene, config, horizon_, score, coin, revealed_edge):
        ST["t"] = coin.t + 1       # 次の試行の予測の番号
        return real_acc(state, output, scene, config, horizon_, score, coin, revealed_edge)

    loop._update_accounting = acc


ST = {"t": 0}


def main():
    out_path = sys.argv[1]
    assert sys.argv[2] == "--"
    run_args = sys.argv[3:]
    import sweep
    import v3_run
    holder = {}
    real_run_one = sweep.run_one

    def run_one(task):
        install_hooks(holder)       # worker の差し替えのあと、世界を作る前
        return real_run_one(task)

    sweep.run_one = run_one
    v3_run.ProcessPoolExecutor = Inline
    sys.argv = ["tools/v3_run.py", *run_args]
    v3_run.main()
    st = v3_run._LAST_STATE["state"]
    census(st, 1740, "走行の終わり")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(OUT, ensure_ascii=False) + "\n")
    S = OUT["select"]
    M = OUT["m1"]
    print(json.dumps({
        "予測で選んだ": len(S), "U の子を持つ親がある": sum(1 for r in S if r["u_parents"]), "外れた親がいた": sum(1 for r in S if r["excluded"]),
        "外れた親（延べ）": sum(r["excluded"] for r in S), "門を通れなかった": sum(1 for r in S if r["support"] < r["need"]),
        "数えたら通っていた": sum(1 for r in S if r["support"] < r["need"] <= r["support"] + r["excluded"]),
        "m1 の U の席": len(M), "役割に見えている関係があるのに観察なし": sum(1 for r in M if r["role_visible"] and not r["observed"]),
        "終わりの U の子を持つ親": OUT["census"][-1]["parents"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
