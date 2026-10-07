"""公開グラフと記憶だけから、位置ごとの案1・案2′を作る。

k1は過去に見た引数の順と祖先を用いる従来の読み手。
k2は既に採用されたSMEの対応先の、可視グラフの位置を用いる。
研究者の型・正解・世界の完全グラフはこの部品に渡さない。
"""
from collections import defaultdict
import attnposition_keys as K


class Observations:
    def __init__(self):
        self.entities = set()
        self.arguments = {}
        self.parents = defaultdict(list)
        self.shapes = defaultdict(set)
        self.table = {}
        self.names = set()
        self.events = []
        self.last_trial = -1

    def structure(self, scene, entities):
        # 今の可視構造は使える。今の名前を頻度表へ足すのは回答確定後。
        self.entities.update(entities)
        for row in scene:
            self.arguments[row['relation_id']] = tuple(row['arguments'])
            for i, child in enumerate(row['arguments']):
                if child not in entities:
                    pair = (row['relation_id'], i)
                    if pair not in self.parents[child]:
                        self.parents[child].append(pair)

    def after(self, trial, scene, entities, disclosed=None):
        if trial <= self.last_trial:
            raise ValueError('観察の順が不正')
        rows = list(scene) + ([disclosed] if disclosed is not None else [])
        self.structure(rows, entities)
        visible = K.position_index(scene, set(entities))
        full = K.position_index(rows, set(entities))
        for row in rows:
            key = (visible if row in scene else full)['keys'][row['relation_id']]
            name = row['predicate']
            self.names.add(name)
            self.shapes[name].add(K.shape(row, set(entities)))
            if key is not None:
                counts = self.table.setdefault(key, {})
                counts[name] = counts.get(name, 0)+1
        self.events.append({'trial':trial, 'visible_names':[r['predicate'] for r in scene],
                            'disclosed_name':None if disclosed is None else disclosed['predicate']})
        self.last_trial = trial


def common_bases(scene, entities, p_hat, hop, observations):
    si = K.position_index(scene, set(entities))
    bases = {}
    for row in scene:
        key = si['keys'][row['relation_id']]
        if key is None:
            continue
        local = K.shape(row, set(entities))
        higher = 'relation' in local[1]
        pool = sorted(p for p in p_hat['alive_vocab']
                      if local in observations.shapes.get(p, set()) and ((p in hop)==higher))
        bg = K.normalized({p:K.observed_probability(p_hat,p) for p in pool})
        bp = K.normalized({p:n for p,n in observations.table.get(key,{}).items()
                           if ((p in hop)==higher)})
        bases[key] = {'global':bg,'position':bp or dict(bg),'position_empty_fallback':not bp,
                      'position_counts_before':dict(observations.table.get(key,{})),
                      'local_shape':local}
    return bases, si


def features(scene, entities, p_hat, hop, local_lambda, observations, candidates, *, position, mode, epsilon=.5):
    """候補は席と採用済み対応のみ。伏せた名前や正解は引数に無い。"""
    if position not in ('k1','k2') or mode not in ('binary','global','position'):
        raise ValueError('位置又は食い違いの方式が不正')
    bases, si = common_bases(scene,entities,p_hat,hop,observations)
    by_id = {r['relation_id']:r for r in scene}
    by_key = defaultdict(list)
    for row in scene:
        by_key[si['keys'][row['relation_id']]].append(row)
    gaps = {a for r in scene for a in r['arguments'] if a not in entities and a not in by_id}
    query_paths = {si['paths'].get(g) for g in gaps}
    query_paths.discard(None)
    result = []
    for candidate in candidates:
        seats = candidate['seats']
        di = K.position_index(seats,observations.entities,ancestor_parents=observations.parents) if position=='k1' else None
        terms, details = {}, []
        for seat in seats:
            rid, st = seat['relation_id'],seat['state']
            if position=='k1':
                key = di['keys'][rid]
                reason = di['failures'].get(rid)
                visible = by_key[key][0] if len(by_key[key])==1 else None
                if di['paths'].get(rid) in query_paths:
                    reason = 'queried_hidden_position'
                elif reason is None and di['counts'].get(key,0)>1:
                    reason = 'definition_key_collision'
                elif reason is None and si['counts'].get(key,0)>1:
                    reason = 'scene_key_collision'
                elif reason is None and visible is None:
                    reason = 'no_visible_position'
            else:
                dest = candidate['relation_mapping'].get(rid)
                visible = by_id.get(dest)
                key = si['keys'].get(dest)
                reason = ('queried_hidden_position' if dest in gaps else
                          'unmapped_seat' if dest is None else
                          'not_visible' if visible is None else
                          si['failures'].get(dest))
                if reason is None and si['counts'].get(key,0)>1:
                    reason = 'scene_key_collision'
            item = {'slot':seat['slot'],'state':st,'key':key,'reason':reason,
                    'mapped_to':candidate['relation_mapping'].get(rid)}
            if reason is not None:
                item['m'] = 0.
                details.append(item)
                continue
            name = visible['predicate']
            h = seat.get('history',{})
            fixed = seat.get('predicate')
            base = bases[key]['global' if mode=='binary' else mode]
            # q_Hは腕Lと同じ、履歴の局所頻度×本人の全体頻度。
            _,q,fallback = K.global_and_history(seat,candidate['signature_rows'],h,p_hat,scene,hop,local_lambda)
            if fallback:
                q = dict(base)
            probs = K.distribution(st,fixed,q,base,epsilon=epsilon)
            cp,zp,ip = K.surprise(probs,name,p_hat)
            cb,zb,ib = K.surprise(base,name,p_hat)
            mb = float(st=='F' and fixed!=name or st=='H' and h.get(name,0)<=0)
            value = mb if mode=='binary' else 0. if st=='U' else cp-cb
            terms[key] = terms.get(key,0.)+value
            item.update(visible_name=name, m=value, m_binary=mb, P=probs.get(name,0.),
                        b=base.get(name,0.),q_H=q.get(name,0.),q_H_empty_fallback=fallback,
                        fixed_name=fixed,history=dict(h),L_of_bits=K.code_length(name,p_hat),
                        c_P=cp,c_b=cb,zero_P=zp,zero_b=zb,inversion_P=ip,inversion_b=ib,
                        position_counts_before=bases[key]['position_counts_before'])
            details.append(item)
        result.append({**candidate,'m':terms,'details':details})
    return result,bases,si
