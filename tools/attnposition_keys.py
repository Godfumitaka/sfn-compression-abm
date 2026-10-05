"""名前とIDを鍵に入れず、関係の木の構造だけで位置を作る。

ancestor_parentsは過去の公開場面で確認した親の記録。定義から落ちた
祖先を検出してm=0とするためだけに使い、失った鍵を回復しない。
"""
from collections import Counter, defaultdict
import json
import math


def shape(row, entities):
    args = row['arguments']
    return (len(args), tuple('entity' if a in entities else 'relation' for a in args))


def position_index(rows, entities, *, ancestor_parents=None):
    by_id = {r['relation_id']: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError('同じ関係IDの重複')
    parents = defaultdict(list)
    for parent in rows:
        for index, child in enumerate(parent['arguments']):
            if child not in entities:
                parents[child].append((parent['relation_id'], index))
    cache, failures, visiting = {}, {}, set()

    def paths(node):
        if node in cache:
            return cache[node]
        if node in visiting:
            failures[node] = 'cycle'
            return None
        if ancestor_parents is not None:
            absent = [p for p, _ in ancestor_parents.get(node, ()) if p not in by_id]
            if absent:
                failures[node] = 'missing_ancestor'
                cache[node] = None
                return None
        visiting.add(node)
        found = []
        if not parents[node]:
            found.append(())
        for parent, index in parents[node]:
            above = paths(parent)
            if above is None:
                failures[node] = failures.get(parent, 'missing_ancestor')
                cache[node] = None
                visiting.remove(node)
                return None
            found.extend(path+((shape(by_id[parent], entities), index),) for path in above)
        visiting.remove(node)
        cache[node] = tuple(sorted(found))
        return cache[node]

    keys = {}
    for node, row in by_id.items():
        p = paths(node)
        keys[node] = None if p is None else json.dumps((p, shape(row, entities)), separators=(',',':'))
    counts = Counter(k for k in keys.values() if k is not None)
    # 問われた非可視の関係についても、親からの道だけは求められる。
    for child in parents:
        if child not in by_id:
            paths(child)
    return {'keys': keys, 'paths': cache, 'counts': dict(counts), 'failures': failures}


def normalized(counts):
    positive = {p: n for p, n in sorted(counts.items()) if n > 0}
    total = sum(positive.values())
    return {p: n/total for p, n in positive.items()} if total else {}


def observed_probability(state, name):
    vocab = max(len(state['alive_vocab']), 1)
    if state['total'] == 0:
        return 1./vocab
    empirical = state['counts'].get(name, 0)/state['total']
    return empirical if empirical else state['lambda_mix']/vocab


def global_and_history(seat, definition_rows, history, p_hat, scene, hop, local_lambda):
    """腕Lのprobabilitiesが呼ぶu_answer・_distributionと同じ計算。

    署名の判定には、その実装と同じ場面と定義の構造を使う。
    _predicate_has_signatureの出現の判定には元の記録を使う。
    名前への食い違いは、Fの固定名とHの履歴だけから計算する。
    """
    ids = {r['relation_id'] for r in definition_rows}
    scene_ids = {r['relation_id'] for r in scene}
    sig = (len(seat['arguments']), tuple('relation' if a in ids else 'entity' for a in seat['arguments']))
    higher = any(a in ids for a in seat['arguments'])
    occurrences = defaultdict(list)
    for row in (*scene, *definition_rows):
        if row.get('predicate') is not None:
            occurrences[row['predicate']].append(row)

    def compatible(name):
        # abm/filling.py:_predicate_has_signatureは両側の出現をtargetで測る。
        return not occurrences[name] or any(
            (len(r['arguments']), tuple('relation' if a in scene_ids else 'entity' for a in r['arguments'])) == sig
            for r in occurrences[name])

    pool = sorted(p for p in p_hat['alive_vocab'] if compatible(p) and ((p in hop) == higher))
    unscaled = [(p, observed_probability(p_hat, p)) for p in pool]
    total = sum(w for _, w in unscaled)
    b = {p: w/total for p, w in unscaled} if total else {}
    hp = sorted(p for p, n in history.items() if n > 0 and ((p in hop) == higher))
    denominator = sum(history[p] for p in hp)
    raw = [(p, ((history[p]/denominator)**local_lambda if local_lambda and denominator else 1.) *
            observed_probability(p_hat,p)) for p in hp]
    total = sum(w for _, w in raw)
    q = {p: w/total for p, w in raw} if total else dict(b)
    return b, q, not bool(total)


def code_length(name, p_hat):
    counts = {p:n for p,n in p_hat['counts'].items() if n > 0}
    lengths = ({p:0 for p in counts} if len(counts)<=1 else
               {p:int(math.ceil(-math.log2(n/p_hat['total']))) for p,n in counts.items()})
    return lengths.get(name, max(lengths.values(), default=0)+1)


def distribution(state, fixed, q, b):
    if state == 'U':
        return dict(b)
    names = sorted(set(q)|set(b)|({fixed} if fixed is not None else set()))
    if state == 'F':
        return {p:.5*(p==fixed)+.5*b.get(p,0.) for p in names}
    return {p:.5*q.get(p,0.)+.5*b.get(p,0.) for p in names}


def surprise(probabilities, name, p_hat):
    probability = probabilities.get(name,0.)
    zero = probability == 0
    value = code_length(name,p_hat)*math.log(2.) if zero else -math.log(probability)
    more_costly_names = [p for p,pb in probabilities.items() if pb>0 and -math.log(pb)>value] if zero else []
    return value, zero, more_costly_names


def enrich(public, table):
    """予測前の公開入力だけで3方式のmを作る。正解・研究者ラベルは受けない。"""
    scene, entities = public['scene'], set(public['entities'])
    si = position_index(scene, entities)
    query_paths = si['paths'].get(public['query_id'])
    by_key = defaultdict(list)
    for row in scene:
        key = si['keys'][row['relation_id']]
        if key is not None:
            by_key[key].append(row)
    result, audit = [], []
    for candidate in public['candidates']:
        rows = candidate['seats']
        di = position_index(rows, set(public['known_entities']), ancestor_parents=public['ancestor_parents'])
        terms = {'binary':{}, 'global':{}, 'position':{}}
        details = []
        for seat in rows:
            rid, st = seat['relation_id'], seat['state']
            key = di['keys'][rid]
            reason = di['failures'].get(rid)
            if query_paths is not None and di['paths'].get(rid) == query_paths:
                reason = 'queried_hidden_position'
            elif reason is None and di['counts'].get(key,0)>1:
                reason = 'definition_key_collision'
            elif reason is None and si['counts'].get(key,0)>1:
                reason = 'scene_key_collision'
            elif reason is None and key not in by_key:
                reason = 'no_visible_position'
            item = {'slot':seat['slot'],'state':st,'key':key,'reason':reason}
            if reason is not None:
                details.append(item)
                audit.append({'R':candidate['R'],**item})
                continue
            visible = by_key[key][0]
            name = visible['predicate']
            h = seat.get('history',{})
            fixed = seat.get('predicate')
            b,q,q_fallback = global_and_history(seat, candidate['signature_rows'], h, public['p_hat'],scene,set(public['higher_order_predicates']),public['local_lambda'])
            bp = normalized({p:n for p,n in table.get(key,{}).items()
                             if ((p in public['higher_order_predicates']) == any(a not in entities for a in visible['arguments']))})
            fallback = not bp
            if fallback:
                bp = b.copy()
            qp = bp if q_fallback else q
            pg,pp = distribution(st,fixed,q,b),distribution(st,fixed,qp,bp)
            mg,zg,rg = surprise(pg,name,public['p_hat'])
            mp,zp,rp = surprise(pp,name,public['p_hat'])
            mb = float(st=='F' and fixed!=name or st=='H' and h.get(name,0)<=0)
            terms['binary'][key] = mb
            terms['global'][key] = mg
            terms['position'][key] = mp
            item.update(visible_name=name,m_binary=mb,m_global=mg,m_position=mp,
                        p_global=pg.get(name,0.),p_position=pp.get(name,0.),
                        zero_global=zg,zero_position=zp,inversion_global=rg,inversion_position=rp,
                        b_global=b,b_position=bp,q_H=q,q_H_position=qp,q_H_empty_fallback=q_fallback,position_empty_fallback=fallback,
                        position_counts_before=dict(table.get(key,{})))
            details.append(item)
        result.append({**{k:v for k,v in candidate.items() if k!='seats'},'m':terms,'details':details})
    return result, audit, si


def count_after(table, public, scene_index):
    """今の予測が確定した後、一つの可視関係を一回、実開示を一回だけ数える。"""
    for row in public['scene']:
        key = scene_index['keys'][row['relation_id']]
        if key is not None:
            counts = table.setdefault(key,{})
            counts[row['predicate']] = counts.get(row['predicate'],0)+1
    feedback = public['feedback']
    if feedback['f_fired']:
        row = feedback['feedback_content']
        assert row['relation_id'] not in {r['relation_id'] for r in public['scene']}
        index = position_index([*public['scene'],row],set(public['entities']))
        key = index['keys'][row['relation_id']]
        if key is not None:
            counts = table.setdefault(key,{})
            counts[row['predicate']] = counts.get(row['predicate'],0)+1
