"""お店の四葉の各部分木を、二つの経路に置く。研究者の世界生成だけ。

一つ目の入口と出口は元のa,b。シール・周縁・媒介・高階の木を変えない。
型・通常／例外によって配置を替えない。旗を切れば読み込まない。
"""
from dataclasses import replace
from abm.domains import Entity, Relation, RelationGraph
from abm.world import opaque_id

VERSION = "shop-scatter-two-paths-1"


def scatter(tr, run_seed, trial_index):
    rels = {r.relation_id: r for r in tr.G_star.relations}
    a = opaque_id(run_seed, trial_index, "entity:a")
    b = opaque_id(run_seed, trial_index, "entity:b")
    entities = list(tr.G_star.entities)
    changes = {}
    for block in (0, 1):
        def eid(role):
            return opaque_id(run_seed, trial_index, f"entity:scatter:{block}:{role}")
        u, v = (a, b) if block == 0 else (eid("u"), eid("v"))
        x, y = eid("a"), eid("b")
        entities.extend(Entity(k) for k in ((x, y) if block == 0 else (u, v, x, y)))
        positions = ((u, x), (x, v), (u, y), (y, v))
        paths = (f"{block}.0.0", f"{block}.0.1", f"{block}.1.0", f"{block}.1.1")
        for path, args in zip(paths, positions):
            rid = opaque_id(run_seed, trial_index, f"relation:tree:{path}")
            if rid not in rels or len(rels[rid].arguments) != 2 or rels[rid].arguments != (a, b):
                raise ValueError("指定の八葉のお店の元の配置と一致しない")
            changes[rid] = args
    rows = tuple(Relation(r.relation_id, r.predicate, changes[r.relation_id], r.attributes)
                 if r.relation_id in changes else r for r in tr.G_star.relations)
    complete = RelationGraph(tr.G_star.graph_id, tuple(entities), rows)
    hid = tr.held_out_edge.relation_id
    visible = tuple(r for r in rows if r.relation_id != hid)
    visible_ids = {r.relation_id for r in visible}
    entity_ids = {e.entity_id for e in entities}
    reachable = {a for r in visible for a in r.arguments if a not in visible_ids and a in entity_ids}
    partial = RelationGraph(tr.target_graph_partial.graph_id, tuple(e for e in entities if e.entity_id in reachable), visible)
    held = next(r for r in rows if r.relation_id == hid)
    return replace(tr, G_star=complete, target_graph_partial=partial, held_out_edge=held)


def install():
    import shopworld
    original = shopworld.build

    def build(tr, run_seed, trial_index, *, cue, world):
        out, info = original(tr, run_seed, trial_index, cue=cue, world=world)
        return scatter(out, run_seed, trial_index), info

    # 固定の試験も同じbuildを通るので、そこでの配置も同じ規則になる。
    shopworld.build = build
