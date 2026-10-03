"""見積もり専用。模型のファイルを変更せず、順序付き非巡回グラフだけを測る。

試作は公開 SME v4 の完全な実装ではない。関数・属性・可換引数・U/H・
伏せ位置・候補推論・複数の全体対応・二段の統合・正規化を含めない。
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import statistics
import sys
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'source'), str(ROOT / 'source/tools')]
from abm.domains import Entity, Relation, RelationGraph
import abm.sme as sme
import fixorder2
import strictpc

# 登録された定義でない F だけのグラフでは、他の旗の候補ラッパーは元へ委譲する。
fixorder2.install()
strictpc.install()


def graph(name, entities, rows):
    return RelationGraph(name, tuple(Entity(e) for e in entities),
                         tuple(Relation(r, p, tuple(a)) for r, p, a in rows))


def compatible(nodes):
    forward, backward = {}, {}
    for kind, left, right in nodes:
        lk, rk = (kind, left), (kind, right)
        if forward.get(lk, rk) != rk or backward.get(rk, lk) != lk:
            return False
        forward[lk], backward[rk] = rk, lk
    return True


def prototype(base, target):
    """MH の閉包・親からの点・まとまりの点順統合を測る限定試作。"""
    br = {r.relation_id: r for r in base.relations}
    tr = {r.relation_id: r for r in target.relations}
    be = {e.entity_id for e in base.entities}
    te = {e.entity_id for e in target.entities}
    pairs = {(l.relation_id, r.relation_id) for l in br.values() for r in tr.values()
             if l.predicate == r.predicate and len(l.arguments) == len(r.arguments)}
    children, invalid = {}, set()
    for left, right in pairs:
        node = ('r', left, right)
        children[node] = []
        for a, b in zip(br[left].arguments, tr[right].arguments):
            if a in be and b in te:
                children[node].append(('e', a, b))
            elif (a, b) in pairs:
                children[node].append(('r', a, b))
            else:
                invalid.add(node)

    @lru_cache(None)
    def closure(node):
        if node in invalid:
            return None
        result = {node}
        for child in children.get(node, ()):
            sub = closure(child)
            if sub is None:
                return None
            result.update(sub)
        return frozenset(result) if compatible(result) else None

    valid = {n for n in children if closure(n) is not None}
    nodes = set().union(*(closure(n) for n in valid)) if valid else set()
    parents = defaultdict(set)
    for n in valid:
        for c in children[n]:
            parents[c].add(n)

    @lru_cache(None)
    def depth(n):
        return 0 if not children.get(n) else 1 + max(depth(c) for c in children[n])

    scores = {}
    for n in sorted(nodes, key=lambda n: (-depth(n), n)):
        score = 0.0005 if n[0] == 'r' else 0.0
        # 公開資料の親の貪欲な一対一選び。この試作では閉包同士も確認する。
        admitted = {n}
        for p in sorted(parents[n], key=lambda p: (-scores[p], p)):
            if compatible(admitted | set(closure(p))):
                admitted.update(closure(p))
                score += 8.0 * scores[p]
        scores[n] = score
    kernels = [closure(n) for n in valid if not parents[n]]
    kernels.sort(key=lambda k: (-sum(scores[n] for n in k), tuple(sorted(k))))
    selected = set()
    for kernel in kernels:
        if compatible(selected | set(kernel)):
            selected.update(kernel)
    return {'relation_mapping': {l: r for k, l, r in selected if k == 'r'},
            'entity_mapping': {l: r for k, l, r in selected if k == 'e'},
            'mh': len(nodes), 'kernels': len(kernels), 'local_pairs': len(pairs)}


def tree(name, leaves, repeated):
    entities, rows, layer = [], [], []
    for i in range(leaves):
        a, b, r = f'{name}_a{i}', f'{name}_b{i}', f'{name}_leaf{i}'
        entities += [a, b]
        rows.append((r, 'leaf' if repeated else f'leaf{i}', (a, b)))
        layer.append(r)
    level = 0
    while len(layer) > 1:
        nxt = []
        for j in range(0, len(layer), 2):
            r = f'{name}_level{level}_{j//2}'
            rows.append((r, f'parent{level}', (layer[j], layer[j+1])))
            nxt.append(r)
        layer = nxt
        level += 1
    return graph(name, entities, rows)


def elapsed(fn, repeats):
    for _ in range(3):
        fn()
    values = []
    for _ in range(repeats):
        t = time.perf_counter_ns()
        fn()
        values.append((time.perf_counter_ns() - t) / 1e6)
    values.sort()
    return statistics.median(values), values[int(0.90 * (len(values)-1))]


def main():
    base = graph('base', ['a', 'b'], [('bp', 'p', ['a','b']),
                 ('bq','q',['bp']), ('br','r',['bq']), ('bm','mark',['a','b'])])
    target = graph('target', ['u','v','w','z'], [('tp0','p',['u','v']),
                   ('tq0','q',['tp0']), ('tp1','p',['w','z']),
                   ('tq1','q',['tp1']), ('tr','r',['tq1']), ('tm','mark',['u','v'])])
    alignment = sme.map_graphs(base, target).alignment
    result = {'base':base.to_dict(), 'target':target.to_dict(),
              'current': {'relations': dict(alignment.relation_mapping),
                          'entities':dict(alignment.entity_mapping)},
              'prototype':prototype(base,target)}
    (ROOT/'small_example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    rows = []
    for leaves in (8,16,32):
        for repeated in (False,True):
            b,t = tree('b', leaves, repeated), tree('t',leaves,repeated)
            count = 80 if leaves < 32 else 30
            cur,cp = elapsed(lambda:sme.map_graphs(b,t),count)
            new,np = elapsed(lambda:prototype(b,t),count)
            state = prototype(b,t)
            rows.append({'leaves':leaves,'relations':len(b.relations),'entities':len(b.entities),
                         'repeated_names':repeated,'repeats':count,
                         'current_median_ms':cur,'current_p90_ms':cp,
                         'prototype_median_ms':new,'prototype_p90_ms':np,
                         'ratio_medians':new/cur,'local_pairs':state['local_pairs'],
                         'mh':state['mh'],'kernels':state['kernels']})
    with (ROOT/'matcher_timings.csv').open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    meta = {'python':sys.version,'platform':platform.platform(),
            'current':'fixorder2.install + strictpc.install、登録なし F のみ',
            'prototype_limitations':__doc__,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_commit':'3380344add7f85ce2c3608656de5805995dcf971',
            'parallelism':1}
    (ROOT/'measurement_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'small_example':result['current'],'prototype':result['prototype'],
                      'timings':rows},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
