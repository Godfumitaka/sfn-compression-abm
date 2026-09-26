"""研究者側だけの場面同一性と主張真偽。入力・模型には返さない。"""
from __future__ import annotations
from itertools import permutations,product
import json
from abm.domains import RelationGraph


def expression(edge, context, atoms=None, trail=()):
    if edge.relation_id in trail: raise ValueError('循環関係はこの解析の対象外')
    args=[]
    for arg in edge.arguments:
        if arg in context:
            args.append(('relation',expression(context[arg],context,atoms,(*trail,edge.relation_id))))
        else:args.append(('atom',atoms[arg] if atoms is not None else arg))
    return (edge.predicate,tuple(args),json.dumps(dict(edge.attributes),sort_keys=True))


def scene_key(graph):
    """不透明IDのみを改名。全述語・順序・属性・実体宣言・多重度を保存。"""
    context={r.relation_id:r for r in graph.relations}
    declared={e.entity_id:e for e in graph.entities}
    atomset=set(declared)|{a for r in graph.relations for a in r.arguments if a not in context}
    groups={}
    for a in atomset:
        e=declared.get(a)
        color=('declared',e.label,json.dumps(dict(e.attributes),sort_keys=True)) if e else ('undeclared',None,'{}')
        groups.setdefault(color,[]).append(a)
    grouped=[(color,sorted(values)) for color,values in sorted(groups.items())]
    # この種の参照先には意味の同一な別relationがない。展開による同一性の損失を拒否。
    refs={a for r in graph.relations for a in r.arguments if a in context}
    refexpr=[expression(context[x],context) for x in refs]
    if len(set(refexpr))!=len(refexpr):raise ValueError('同じ意味の別参照relation: 完全グラフ同型判定が必要')
    best=None
    for combination in product(*(permutations(values) for _,values in grouped)):
        mapping={}
        for (color,values),ordered in zip(grouped,combination):
            for i,a in enumerate(ordered):mapping[a]=(color,i)
        value=(tuple((color,len(values)) for color,values in grouped),
               tuple(sorted(expression(r,context,mapping) for r in graph.relations)))
        if best is None or value<best:best=value
    return repr(best)


def claim_truth(pred,world,extra=()):
    if pred is None:return None
    context={r.relation_id:r for r in (*world.relations,*extra,pred)}
    q=expression(pred,context)
    worldctx={r.relation_id:r for r in world.relations}
    return q in {expression(r,worldctx) for r in world.relations}


def claim_key(pred,scene,extra=()):
    if pred is None:return None
    context={r.relation_id:r for r in (*scene.relations,*extra,pred)}
    return repr(expression(pred,context))
