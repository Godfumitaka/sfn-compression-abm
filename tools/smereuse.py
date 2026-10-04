"""匿名の図の匿名の図の一意の位置だけを再利用する部品。"""
from dataclasses import dataclass,replace
import json

@dataclass(frozen=True)
class Positions:
    code:str
    left:tuple
    right:tuple
    names:tuple

def positions(left,right):
    labels,edges,ids,words=[],[],{},{}
    for side,g in enumerate((left,right)):
        for n in g.nodes:
            ids[side,n.key]=len(labels)
            labels.append((side,n.kind,n.state,len(n.names),len(n.args) if n.args is not None else -1,n.ubiquitous))
        for n in g.nodes:
            for i,a in enumerate(n.args or ()):
                edges.append((ids[side,n.key],ids[side,a],f'arg{i}'))
            for word in n.names:
                if word not in words:words[word]=len(labels);labels.append((2,'name'))
                edges.append((ids[side,n.key],words[word],'allows'))
    incoming=[[] for _ in labels];outgoing=[[] for _ in labels]
    for a,b,p in edges:outgoing[a].append((p,b));incoming[b].append((p,a))
    def ranks(values):
        xs=[json.dumps(v,separators=(',',':')) for v in values];d={v:i for i,v in enumerate(sorted(set(xs)))}
        return tuple(d[v] for v in xs)
    colors=ranks(labels)
    while True:
        nxt=ranks([(colors[i],sorted((p,colors[j]) for p,j in outgoing[i]),sorted((p,colors[j]) for p,j in incoming[i])) for i in range(len(labels))])
        if len(set(nxt))==len(set(colors)):colors=nxt;break
        colors=nxt
    if len(set(colors))!=len(labels):return None
    order=sorted(range(len(labels)),key=colors.__getitem__);at={v:i for i,v in enumerate(order)}
    code=json.dumps(([labels[v] for v in order],sorted((at[a],at[b],p) for a,b,p in edges)),separators=(',',':'))
    return Positions(code,tuple(sorted((at[v],k) for (side,k),v in ids.items() if side==0)),
                     tuple(sorted((at[v],k) for (side,k),v in ids.items() if side==1)),
                     tuple(sorted((at[v],k) for k,v in words.items())))

def relabel(result,old,new,left,right):
    assert old.code==new.code
    ld={k:dict(new.left)[i] for i,k in old.left};rd={k:dict(new.right)[i] for i,k in old.right};names={k:dict(new.names)[i] for i,k in old.names}
    def pairs(ps):return tuple(sorted((ld[a],rd[b]) for a,b in ps))
    def expr(x):
        if x[0]=='mapped':return ('mapped',rd[x[1]])
        if x[0]=='skolem':return ('skolem',ld[x[1]])
        kind,ws,args=x;return kind,tuple(sorted(names[w] for w in ws)),tuple(expr(a) for a in args)
    cs=[]
    for c in result.candidates:
        cs.append(replace(c,relation_mapping=pairs(c.relation_mapping),entity_mapping=pairs(c.entity_mapping),
            match_kinds=tuple(sorted((ld[a],rd[b],k) for a,b,k in c.match_kinds)),
            breakdown=tuple(sorted((ld[a],rd[b],v,td) for a,b,v,td in c.breakdown)),
            inferences=tuple(sorted((ld[k],expr(x)) for k,x in c.inferences))))
    hs=tuple(replace(h,left=ld[h.left],right=rd[h.right],name_pair=None if h.name_pair is None else tuple(names[w] for w in h.name_pair)) for h in result.hypotheses)
    return replace(result,left_fingerprint=left.fingerprint(),right_fingerprint=right.fingerprint(),candidates=tuple(cs),hypotheses=hs)
