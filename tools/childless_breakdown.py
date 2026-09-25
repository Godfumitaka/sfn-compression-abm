"""読むだけ（2026-09-25）：外していく生まれ方の確かめの台帳一本で、共通構造の全体の中の高階の行の「子が欠ける」理由を数える。
★ 模型は走らせない。世界を作り直し、土台（直前の試行の見えている場面＋開示された辺）と今の場面を map_graphs で写す。
   逐語の枚は 1 試行しか残らない設定（verbatim_theta 無し）なので、土台はいつも直前の試行の場面（2026-09-24 の確認）。
★ 共通構造の全体 ＝ m1 と同じ手順（abstraction.py:74-85）の対。子が欠けた高階の行ごとに、欠けた子の理由を分ける：
   A SME の写しに無い（relation_mapping のキーに無い）
   B 写しにはあるが、写った先が今の場面の関係で、述語が違う（引数の対応だけで写った）
   C 写しにはあるが、写った先が今の場面の関係ではない（見えていない位置＝伏せ辺など）
   D 写った先の述語は同じだが、共通構造の全体に入っていない（起きないはず）
   E 子そのものが、先に「子の無い高階」として外された（連鎖）
   F 子が土台の場面に無い（前の試行で伏せられて開示も無かった）
★ side の記録（pool・childless_dropped_at_start）と、ここで作り直した値が一致するかを検算する。
使い方  python3.12 tools/childless_breakdown.py <side.jsonl> <種番号> <f>"""
import collections, json, sys
sys.path.insert(0, "/Users/tatsu-admin/sfn/sfn-compression-abm")
from abm.world import generate_world
from abm.seed import load_seed
from abm.sme import map_graphs
from abm.domains import RelationGraph
from abm.abstraction import _structural_relation_ids

side, seed_i, f = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
sd = load_seed("seeds/U-011_seed_v3a2.json")
w = generate_world(seed_i, 1740, ("agent",), seed=sd, holdout_include_second_order=True)
ev = [json.loads(l) for l in open(side) if '"kind": "prune"' in l]


def base_scene(t):
    tr = w.trials[t]
    g = tr.target_graph_partial
    if tr.u_coins["agent"] < f:   # 開示（loop.py:88-89）。_append_relation と同じく関係だけを足す（agent_runtime.py:384-391）
        rel = tr.held_out_edge
        if not any(r.relation_id == rel.relation_id for r in g.relations):
            g = RelationGraph(g.graph_id, tuple(g.entities), (*g.relations, rel))
    return g


reason = collections.Counter(); per_event = []; mism = 0; kinds = collections.Counter()
for e in ev:
    t = e["trial"]
    base = base_scene(t - 1); tgt = w.trials[t].target_graph_partial
    al = map_graphs(base, tgt).alignment
    base_by_id = {r.relation_id: r for r in base.relations}
    tgt_by_id = {r.relation_id: r for r in tgt.relations}
    raw = [(base_by_id[l], tgt_by_id[r]) for l, r in sorted(al.relation_mapping.items()) if l in base_by_id and r in tgt_by_id]
    sids = _structural_relation_ids(base)
    pool = [p[0] for p in raw if p[0].relation_id in sids and p[0].predicate == p[1].predicate]
    base_ids = set(base_by_id)
    S = list(pool); dropped = 0; first_round = True; cascade_ids = set()
    while True:
        ids = {r.relation_id for r in S}
        bad = [r for r in S if any(a in base_ids and a not in ids for a in r.arguments)]
        if not bad:
            break
        for r in bad:
            for a in r.arguments:
                if a in base_ids and a not in ids:
                    if a in cascade_ids:
                        k = "E 連鎖（子が先に外された）"
                    elif a not in al.relation_mapping:
                        k = "A 写しに無い"
                    else:
                        tgt_id = al.relation_mapping[a]
                        if tgt_id not in tgt_by_id:
                            k = "C 写った先が場面に無い（見えていない位置）"
                        elif tgt_by_id[tgt_id].predicate != base_by_id[a].predicate:
                            k = "B 写った先の述語が違う"
                        else:
                            k = "D 述語は同じだが全体に入っていない"
                    reason[k] += 1
                    kinds[(base_by_id[r.relation_id].predicate, base_by_id[a].predicate, k[0])] += 1
        dropped += len(bad)
        cascade_ids |= {r.relation_id for r in bad}
        S = [r for r in S if r.relation_id not in {b.relation_id for b in bad}]
    # 子が土台に無い（F）：高階の行の引数で、土台の関係 ID でも実体でもないもの
    for r in pool:
        for a in r.arguments:
            if a not in base_ids and a not in {x.entity_id for x in base.entities}:
                reason["F 子が土台の場面に無い（参考：外す対象ではない）"] += 1
    ok = (len(pool) == e["pool"] and dropped == e["childless_dropped_at_start"])
    mism += not ok
    per_event.append((t, w.trials[t - 1].motif, w.trials[t].motif, len(pool), dropped))
print(f"外していく処理 {len(ev)} 回　side との食い違い {mism}")
print(f"最初に子の無い高階を外した回 {sum(1 for x in per_event if x[4] > 0)}　外した高階の行の延べ {sum(x[4] for x in per_event)}")
same = sum(1 for x in per_event if x[4] > 0 and x[1] == x[2]); diff = sum(1 for x in per_event if x[4] > 0 and x[1] != x[2])
print(f"  そのうち 直前と同じモチーフ {same}／違うモチーフ {diff}")
print("欠けた子の理由（高階の行 × 欠けた子 の延べ）")
for k, v in sorted(reason.items()):
    print(f"  {k}: {v}")
print("よく出た組（親の述語, 欠けた子の述語, 理由）")
for (pp, cp, k), v in kinds.most_common(12):
    print(f"  {pp} ← {cp}  {k}: {v}")
