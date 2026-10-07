"""受け箱の指示2・8：候補共通の可視位置の基底とmixtureの学び。

主Uの分布は変更しない。注意の基底だけは可視位置の形と階で絞り、
候補側の出現を使わない。Uを含む席の実際のPとの比を符号つきで測る。
"""
from dataclasses import replace
import math
import attnposition_keys as K
import attnstage2_readout as R


def relative_mismatch(distribution, background, name, *, epsilon, length_of):
    """確率0だけ既存の退避符号。小さい確率も0切りも足さない。"""
    if not 0<epsilon<1:raise ValueError('注意の比のepsilonは0と1の間')
    p=R.probability(distribution,name)
    b=R.probability(background,name)
    cp=-math.log(p) if p>0 else length_of(name)*math.log(2.)
    cb=-math.log(b) if b>0 else length_of(name)*math.log(2.)
    value=math.log(b/p)/(-math.log(epsilon)) if p>0 and b>0 else (cp-cb)/(-math.log(epsilon))
    if not math.isfinite(value):raise ArithmeticError('注意の比が有限でない')
    return value,{'P':p,'b':b,'c_P':cp,'c_b':cb,'zero_P':p==0,'zero_b':b==0}


def visible_positions(scene, entities, native_bases):
    """名前・IDを含まないk2の役割の鍵。基底は可視関係IDごとに共通。"""
    index=K.position_index(scene,set(entities))
    positions=[]
    for row in scene:
        rid=row['relation_id'];key=index['keys'][rid]
        reason=index['failures'].get(rid)
        if reason is None and index['counts'].get(key,0)>1:reason='scene_key_collision'
        if reason is None and rid not in native_bases:
            raise ValueError(('可視位置の主のUの基底が未接続',rid))
        positions.append({'relation_id':rid,'key':key,'name':row['predicate'],
                          'reason':reason,'b':None if reason is not None else dict(native_bases[rid])})
    return tuple(positions),index


def candidate_features(positions, candidate, *, distribution_reader, epsilon, length_of):
    """全候補で共通の可視位置を使い、対応なしはP=b・m=0とする。"""
    by_destination={}
    for seat in candidate['seats']:
        dest=candidate['relation_mapping'].get(seat['relation_id'])
        if dest is not None:
            if dest in by_destination:raise ValueError('SMEの対応が一対一でない')
            by_destination[dest]=seat
    terms,details={},[]
    for position in positions:
        key=position['key'];seat=by_destination.get(position['relation_id'])
        item={k:position[k] for k in ('relation_id','key','reason')}
        if position['reason'] is not None:
            item['m']=0.;details.append(item);continue
        if seat is None:
            value=0.;item.update(state=None,reason='unmapped_background',P=position['b'].get(position['name'],0.),
                                b=position['b'].get(position['name'],0.))
        else:
            # 同じ位置のbを全候補で使う。正解・型の名札は渡さない。
            distribution=distribution_reader(seat,position['relation_id'],dict(position['b']))
            value,audit=relative_mismatch(distribution,position['b'],position['name'],
                                          epsilon=epsilon,length_of=length_of)
            item.update(state=seat['state'],slot=seat['slot'],reason='native_distribution',**audit)
        terms[key]=terms.get(key,0.)+value
        details.append({**item,'m':value})
    return terms,details


def learn(candidates, attention, *, disclosed, door_task, feedback_reader,
          background, eta=.1):
    """保持top1に対する自然対数mixtureの代理。現回答を選び直さない。"""
    if not math.isfinite(eta) or eta<0:raise ValueError('学びの幅は有限で負でない')
    before=dict(attention)
    if not door_task or not disclosed:
        return before,{'L':None,'gradient':{},'updated':False,
                       'reason':'non_door' if not door_task else 'not_disclosed'}
    correct,ell=feedback_reader()
    value,gradient,reason=R.mixture_gradient(candidates,before,correct,ell,
                                            background=background,bits=False,temperature=1.)
    after=dict(before)
    for key,g in gradient.items():
        if not math.isfinite(g):raise ArithmeticError('注意の勾配が有限でない')
        after[key]=min(10.,max(0.,before.get(key,0.)-eta*g))
    updated=after!=before
    return after,{'L':value,'gradient':gradient,'updated':updated,
                  'reason':reason or ('updated' if updated else 'zero_or_clipped_step'),
                  'loss':'mixture_distribution_natural','retention_loss':'top1',
                  'temperature':1.,'normalization':'none','a_before':before,'a_after':dict(after)}
