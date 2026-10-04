"""実際の候補選びには未接続。緩めた構造の支持・点の上限。"""
from functools import lru_cache
from fractions import Fraction
import math

def possible_pairs(left,right):
    lb,rb=left.by_id,right.by_id
    @lru_cache(None)
    def possible(a,b):
        x,y=lb[a],rb[b]
        if 'entity' in (x.kind,y.kind):return x.kind==y.kind=='entity'
        unknown='unknown' in (x.kind,y.kind)
        if not unknown and x.kind!=y.kind:return False
        if x.args is not None and y.args is not None and len(x.args)!=len(y.args):return False
        structural=unknown or x.state=='U' or y.state=='U'
        if not structural and not (x.names & y.names) and x.kind!='function':return False
        # 根でも関数の名前の違う対応を許す、制約を緩めた集合。
        return unknown or all(possible(p,q) for p,q in zip(x.args or (),y.args or ()))
    return frozenset((x.key,y.key) for x in left.nodes for y in right.nodes if possible(x.key,y.key))

def support_upper(left,right,pairs):
    # 一対一だけを課す最大対応。親子と物の矛盾は課さないので上限。
    by={x.key:[] for x in left.nodes if x.kind=='relation' and x.state!='U'}
    for a,b in pairs:
        if a in by and right.by_id[b].kind!='entity':by[a].append(b)
    matched={}
    def augment(a,seen):
        for b in by[a]:
            if b in seen:continue
            seen.add(b)
            if b not in matched or augment(matched[b],seen):matched[b]=a;return True
        return False
    return sum(augment(a,set()) for a in by)

def upper_score(left,right,settings,pairs):
    if settings.same_functor!=.0005 or settings.same_function!=.0002 or settings.trickle_down!=8 or settings.max_local_score is not None:
        raise ValueError('証明の対象は既定の採点の設定だけ')
    def up(v):return math.nextafter(v,math.inf) if v>0 and math.isfinite(v) else v
    def one_side(graph,other,reverse=False):
        by=graph.by_id;parents={n.key:[] for n in graph.nodes}
        for n in graph.nodes:
            for a in n.args or ():parents[a].append(n.key)
        @lru_cache(None)
        def visit(k):
            n=by[k];local=0.
            if n.kind not in ('entity','unknown') and n.state!='U':
                for q in other.nodes:
                    pair=(q.key,n.key) if reverse else (n.key,q.key)
                    if pair not in pairs or q.state=='U' or q.kind=='unknown':continue
                    v=settings.same_functor if n.names&q.names else settings.same_function if n.kind==q.kind=='function' else 0.
                    local=max(local,v)
            total=up(math.fsum(visit(p) for p in parents[k]))
            return up(local+up(settings.trickle_down*total))
        return up(math.fsum(visit(n.key) for n in graph.nodes))
    return min(one_side(left,right),one_side(right,left,True))

def bound(left,right,settings,dd,xx):
    pairs=possible_pairs(left,right);s=upper_score(left,right,settings,pairs)
    n3=None if dd+xx<=0 or not math.isfinite(s) else 2*Fraction(s)/(Fraction(dd)+Fraction(xx))
    return support_upper(left,right,pairs),s,n3
