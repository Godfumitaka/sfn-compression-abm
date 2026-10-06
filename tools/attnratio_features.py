"""保存済み位置の対応を変えず、可視位置共通の基底と案2′の費用を作る。

模型・照合・回答の生成を呼ばない。全件の縮退・漏れの関門だけを数え、
成績は集計しない。形の記録も位置の頻度も前試行までの実観察だけ。
"""
import argparse
from collections import Counter, defaultdict
import copy
from fractions import Fraction
import gzip, itertools, json, math, resource, time
from pathlib import Path
import attnratio as P
import attnposition_keys as K
from attnposition_input import records, fingerprint
from attnposition_features import answer_bytes

FIELDS = ('trial','door_task','scene','entities','query_id','p_hat',
          'higher_order_predicates','local_lambda','baseline','candidates','feedback')


def public_records(path):
    decoder = json.JSONDecoder()
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            yield {key:decoder.raw_decode(line,line.index('"'+key+'": ')+len(key)+4)[0]
                   for key in FIELDS}


def candidate(c,mode):
    answer=c['answer']
    return P.Candidate(c['R'],Fraction(c['q_numerator'],c['q_denominator']),c['n'],
        c['registered_at'],tuple(sorted(c['m'][mode].items())),
        None if answer is None else (answer[0],tuple(answer[1])),c['payload'])


def common_bases(scene,entities,p_hat,hop,table,shapes):
    """候補は引数にない。形は名前を観察した過去の記録からだけ得る。"""
    si=K.position_index(scene,set(entities)); result={}
    for row in scene:
        key=si['keys'][row['relation_id']]
        if key is None:continue
        local=K.shape(row,set(entities));higher=any(t=='relation' for t in local[1])
        pool=sorted(p for p in p_hat['alive_vocab']
                    if local in shapes.get(p,set()) and ((p in hop)==higher))
        raw={p:K.observed_probability(p_hat,p) for p in pool}
        bg=K.normalized(raw)
        bp=K.normalized({p:n for p,n in table.get(key,{}).items() if ((p in hop)==higher)})
        fallback=not bp
        if fallback:bp=dict(bg)
        item={'local_shape':local,'global':bg,'position':bp,
              'position_empty_fallback':fallback,'position_counts_before':dict(table.get(key,{}))}
        if key in result:assert result[key]==item
        result[key]=item
    for row in scene:
        key=si['keys'][row['relation_id']]
        if key is None:continue
        for mode in ('global','position'):
            values=result[key].setdefault('cost_'+mode,{})
            values[row['predicate']]=K.surprise(result[key][mode],row['predicate'],p_hat)[0]
    return result,si


def enrich(scene,entities,p_hat,hop,table,shapes,seats_by_R,old_candidates):
    """正解・開示・研究者の名札は引数にない。位置の読み手も変えない。"""
    bases,si=common_bases(scene,entities,p_hat,hop,table,shapes)
    candidates=[]
    for old in old_candidates:
        c=copy.deepcopy(old);c['m']={'global':{},'position':{}}
        # 可視位置で共通の座標を全候補に置く。無い位置の相対費用は0。
        for mode in c['m']:c['m'][mode]=dict.fromkeys(sorted(bases),0.)
        seats={s['slot']:s for s in seats_by_R[c['R']]}
        for d in c['details']:
            if d['reason'] is not None:continue
            s=seats[d['slot']];key=d['key'];name=d['visible_name'];b=bases[key]
            assert si['counts'][key]==1
            old_bg=d['b_global'].get(name,0.);old_bp=d['b_position'].get(name,0.)
            d['old_b_global_visible']=old_bg;d['old_b_position_visible']=old_bp
            for mode in ('global','position'):
                base=b[mode];q=base if d['q_H_empty_fallback'] else d['q_H']
                probs=K.distribution(s['state'],s.get('predicate'),q,base)
                cp,zp,invp=K.surprise(probs,name,p_hat)
                cb,zb,invb=K.surprise(base,name,p_hat)
                value=0. if s['state']=='U' else cp-cb
                d['m_'+mode]=value;d['p_'+mode]=probs.get(name,0.)
                d['b_'+mode]=base;d['c_P_'+mode]=cp;d['c_b_'+mode]=cb
                d['zero_'+mode]=zp;d['zero_base_'+mode]=zb
                d['inversion_'+mode]=invp;d['inversion_base_'+mode]=invb
                c['m'][mode][key]=value
            d['position_empty_fallback']=b['position_empty_fallback']
            d['position_counts_before']=b['position_counts_before']
        candidates.append(c)
    return candidates,bases,si


def add_after(public,table,shapes,events):
    """確定後に可視名を数える。実開示以外の伏せ名は読まない。"""
    scene=public['scene'];entities=set(public['entities'])
    si=K.position_index(scene,entities)
    rows=list(scene)
    if public['feedback']['f_fired']:
        rows.append(public['feedback']['feedback_content'])
    full=K.position_index(rows,entities)
    for row in rows:
        key=(si if row in scene else full)['keys'][row['relation_id']]
        if key is not None:
            names=table.setdefault(key,{})
            names[row['predicate']]=names.get(row['predicate'],0)+1
            events[public['trial'],key,row['predicate']]+=1
        shapes.setdefault(row['predicate'],set()).add(K.shape(row,entities))


def build(base,world,seed,output):
    assert world in (1,2) and seed in range(1,21)
    old=base/'position_attention_2026-10-06';name=f'n3_w{world}_A_L50'
    publicpath=old/'input'/name/f'seed{seed:03d}.public.jsonl.gz'
    featurepath=old/'features'/name/f'seed{seed:03d}.features.jsonl.gz'
    assert json.loads(featurepath.with_name(f'seed{seed:03d}.features.check.json').read_text())['passed']
    folder=output/name;folder.mkdir(parents=True,exist_ok=True)
    dest=folder/f'seed{seed:03d}.features.jsonl.gz';check=folder/f'seed{seed:03d}.features.check.json'
    if dest.exists() or check.exists():raise RuntimeError('共通基底の特徴の重複を禁止')
    inputs=[fingerprint(p) for p in (publicpath,featurepath)]
    table,shapes,events={}, {},Counter();compared=Counter();excluded=Counter();count=0;failure=None
    started=time.monotonic()
    try:
        with gzip.open(dest,'wt',encoding='utf-8') as f:
            for public,oldframe in itertools.zip_longest(public_records(publicpath),records(featurepath)):
                assert public is not None and oldframe is not None
                assert public['trial']==oldframe['trial']==count
                expected={}
                for (t,key,n),v in events.items():
                    assert t<count
                    d=expected.setdefault(key,{});d[n]=d.get(n,0)+v
                assert table==expected
                assert set(public['p_hat']['counts'])<=set(shapes)
                seats={c['R']:c['seats'] for c in public['candidates']}
                args=(public['scene'],public['entities'],public['p_hat'],
                    set(public['higher_order_predicates']),table,shapes,seats,oldframe['candidates'])
                cs,bases,si=enrich(*args)
                # 正解・型を替えても引数に入らず同じ結果。時点の表も全件検査。
                poisoned=dict(public);poisoned.update(truth='禁止',shop_type='禁止',
                    feedback={'f_fired':True,'feedback_content':{'predicate':'禁止'}})
                poisonedargs=(poisoned['scene'],poisoned['entities'],poisoned['p_hat'],
                    set(poisoned['higher_order_predicates']),table,shapes,seats,oldframe['candidates'])
                assert enrich(*poisonedargs)==(cs,bases,si)
                for c in cs:
                    for seat in seats[c['R']]:
                        if seat['state']=='F':assert seat['predicate'] in shapes
                        if seat['state']=='H':assert set(seat['history'])<=set(shapes)
                    for d in c['details']:
                        if d['reason'] is not None:
                            excluded[d['key'],d['state'],d['reason']]+=1;continue
                        assert d['visible_name'] in {r['predicate'] for r in public['scene']}
                        assert d['position_counts_before']==table.get(d['key'],{})
                        assert d['key'] in bases and si['counts'][d['key']]==1
                        for mode in ('global','position'):
                            old_b=d['old_b_'+mode+'_visible'];new_b=d['b_'+mode].get(d['visible_name'],0.)
                            compared[d['key'],d['state'],mode,old_b!=new_b]+=1
                            if d['state']=='U':assert d['m_'+mode]==0.
                            assert math.isfinite(d['m_'+mode])
                for mode in ('global','position'):
                    numerical=tuple(candidate(c,mode) for c in cs)
                    selected=P.select(numerical,{}) if public['door_task'] else None
                    payload=public['baseline'] if selected is None else selected.payload
                    if answer_bytes(payload)!=answer_bytes(public['baseline']):
                        failure={'gate':1,'world':world,'seed':seed,'trial':count,'mode':mode,
                                 'expected':public['baseline'],'actual':payload}
                        raise RuntimeError('a=0の回答全欄が不一致')
                f.write(json.dumps({'trial':count,'door_task':public['door_task'],
                    'baseline':public['baseline'],'feedback':public['feedback'],
                    'candidates':cs,'audit':oldframe['audit'],'common_bases':bases,
                    'visible_positions':[{'key':si['keys'][r['relation_id']],
                                         'visible_name':r['predicate']} for r in public['scene']]},ensure_ascii=False)+'\n')
                add_after(public,table,shapes,events);count+=1
    except BaseException as e:
        if failure is None:failure={'trial':count,'error':repr(e)}
        raise
    finally:
        result={'passed':failure is None and count==1740,'world':world,'seed':seed,'trials':count,
          'gate1_trials':count,'gate5_trials':count,'failure':failure,
          'baseline_comparisons':[{'key':k,'state':s,'base':b,'changed':ch,'seats_trials':v}
                                  for (k,s,b,ch),v in sorted(compared.items())],
          'old_baseline_unavailable_excluded':[{'key':k,'state':s,'reason':r,'seats_trials':v}
                    for (k,s,r),v in sorted(excluded.items(),key=lambda kv:str(kv[0]))],
          'inputs':inputs,'output':fingerprint(dest),'model_called':False,'position_reader_changed':False,
          'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        check.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert inputs==[fingerprint(p) for p in (publicpath,featurepath)]
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--world',type=int,choices=(1,2),required=True)
    p.add_argument('--seed',type=int,choices=range(1,21),required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.base,a.world,a.seed,a.output)
