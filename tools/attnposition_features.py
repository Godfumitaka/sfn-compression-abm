"""固定材料の全試行で、位置・頻度表の時点とa=0の回答を検査する。

成績表は作らない。キー衝突やP=0の記録は、下見の条件別集計へ
使えるように原記録に残す。非開示の正解は渡されない。
"""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import resource
import sys
import time

W=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(W/'tools'))
import attnposition as P
import attnposition_keys as K
from attnposition_input import records,fingerprint

ANSWER_FIELDS=('prediction_kind','predicted_edge','abstain_reason','R_used','support_at_adoption')


def numerical_candidate(c,mode):
    answer=c['answer']
    return P.Candidate(c['R'],Fraction(c['q_numerator'],c['q_denominator']),c['n'],c['registered_at'],tuple(sorted(c['m'][mode].items())),
                       None if answer is None else (answer[0],tuple(answer[1])),c['payload'])


def answer_bytes(payload):
    return json.dumps({k:payload[k] for k in ANSWER_FIELDS},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def check_gradient(candidates,correct):
    keys=sorted({key for c in candidates for key,_ in c.mismatch})
    a=dict.fromkeys(keys,.3)
    loss,g,reason=P.loss_gradient(candidates,a,correct)
    assert reason is None
    comparisons=[]
    for key in keys:
        plus,minus=dict(a),dict(a)
        plus[key]+=1e-5;minus[key]-=1e-5
        numeric=(P.loss_gradient(candidates,plus,correct)[0]-P.loss_gradient(candidates,minus,correct)[0])/2e-5
        analytic=g.get(key,0.)
        if abs(numeric-analytic)>2e-9+1e-7*abs(analytic):
            raise RuntimeError('関門2の不一致：'+json.dumps({'key':key,'analytic':analytic,'finite_difference':numeric}))
        comparisons.append({'key':key,'analytic':analytic,'finite_difference':numeric,'abs_difference':abs(numeric-analytic)})
    norm=sum(v*v for v in g.values())
    if norm<=1e-10:
        return None
    small={key:a[key]-1e-5*g.get(key,0.) for key in a}
    actual=(P.loss_gradient(candidates,small,correct)[0]-loss)/1e-5
    assert abs(actual+norm)<2e-4*(1+norm), ('更新方向',actual,-norm)
    return {'a':a,'L':loss,'gradient_comparison':comparisons,'directional_actual':actual,
            'directional_expected':-norm,'finite_difference_step':1e-5}


def features(input_root,world,seed,out):
    assert world in (1,2) and seed in range(1,21)
    name=f'n3_w{world}_A_L50'
    source=input_root/name/f'seed{seed:03d}.public.jsonl.gz'
    check_path=input_root/name/f'seed{seed:03d}.input.check.json'
    assert json.loads(check_path.read_text())['passed']
    folder=out/name;folder.mkdir(parents=True,exist_ok=True)
    destination=folder/f'seed{seed:03d}.features.jsonl.gz'
    resultpath=folder/f'seed{seed:03d}.features.check.json'
    if destination.exists() or resultpath.exists():raise RuntimeError('特徴と関門を重複しない')
    inputs=[fingerprint(source),fingerprint(check_path)]
    table,independent,seen={},Counter(),set()
    examples={};counts=Counter();gate1=gate4=0
    started=time.monotonic()
    failure=None
    try:
        with gzip.open(destination,'wt',encoding='utf-8') as stream:
            for public in records(source):
                trial=public['trial']
                assert trial==gate1
                assert set(public['p_hat']['counts'])<=seen
                assert all(t<trial for t,_,_ in independent)
                expected={}
                # 頻度表は、原始観察イベントの試行を持つ別の会計から照合する。
                for (_t,key,name_),n in independent.items():
                    d=expected.setdefault(key,{})
                    d[name_]=d.get(name_,0)+n
                assert table==expected, (trial,'位置の表の予測前の時点')
                candidates,audit,si=K.enrich(public,table)
                poisoned=dict(public)
                poisoned.update(feedback={'f_fired':True,'feedback_content':{'predicate':'__禁止の正解__'}},
                                shop_type='__禁止の型__',shop_cue='__禁止の日__',
                                held_out_content={'predicate':'__禁止の伏せた名前__'},truth='__禁止の正解__')
                # すべての試行で、正解・研究者欄を替えてもm・鍵・bが変わらない。
                assert K.enrich(poisoned,table)==(candidates,audit,si), (trial,'正解・名札に依存した特徴')
                for c in candidates:
                    by_slot={r['slot']:r for r in next(x['seats'] for x in public['candidates'] if x['R']==c['R'])}
                    sig_rows={r['relation_id']:r for r in next(x['signature_rows'] for x in public['candidates'] if x['R']==c['R'])}
                    for detail in c['details']:
                        seat=by_slot[detail['slot']]
                        if seat['state']=='F':assert seat['predicate'] in seen
                        if seat['state']=='H':assert set(seat['history'])<=seen
                        if detail['reason'] is not None:
                            counts[detail['reason']]+=1
                            continue
                        assert detail['visible_name'] in {r['predicate'] for r in public['scene']}
                        assert detail['position_counts_before']==table.get(detail['key'],{})
                        assert si['counts'][detail['key']]==1
                        # ドア名の区分は検査専用。mや選択の分岐には使わない。
                        assert sig_rows[seat['relation_id']].get('predicate') not in ('hold','hold_b'), (trial,c['R'],detail['slot'],'ドアの席がmに入った')
                        for mode in ('global','position'):
                            if detail['zero_'+mode]:counts['zero_'+mode]+=1
                            if detail['inversion_'+mode]:counts['inversion_event_'+mode]+=1
                            counts['inversion_name_pairs_'+mode]+=len(detail['inversion_'+mode])
                # Gate1は全方式の全候補で厳密に比較する。許容を入れない。
                for mode in ('binary','global','position'):
                    cs=tuple(numerical_candidate(c,mode) for c in candidates)
                    selected=P.select(cs,{}) if public['door_task'] else None
                    payload=public['baseline'] if selected is None else selected.payload
                    if answer_bytes(payload)!=answer_bytes(public['baseline']):
                        failure={'gate':1,'world':world,'seed':seed,'trial':trial,'mode':mode,
                                 'actual':payload,'expected':public['baseline']}
                        raise RuntimeError('a=0の元N3の回答不一致')
                    if mode not in examples and public['door_task'] and public['feedback']['f_fired']:
                        edge=public['feedback']['feedback_content']
                        correct=(edge['predicate'],tuple(edge['arguments']))
                        positive=[c for c in cs if c.q>0]
                        if any(c.answer==correct for c in positive) and any(c.answer!=correct for c in positive):
                            example=check_gradient(cs,correct)
                            if example is not None:
                                examples[mode]={'world':world,'seed':seed,'trial':trial,'mode':mode,**example}
                stream.write(json.dumps({'trial':trial,'door_task':public['door_task'],
                       'baseline':public['baseline'],'feedback':public['feedback'],
                       'candidates':[{k:v for k,v in c.items() if k!='signature_rows'} for c in candidates],
                       'audit':audit},ensure_ascii=False)+'\n')
                # 予測の後にだけ数える。重複する鍵でも一つの関係を一回数える。
                for row in public['scene']:
                    key=si['keys'][row['relation_id']]
                    if key is not None:independent[trial,key,row['predicate']]+=1
                if public['feedback']['f_fired']:
                    row=public['feedback']['feedback_content']
                    index=K.position_index([*public['scene'],row],set(public['entities']))
                    key=index['keys'][row['relation_id']]
                    if key is not None:independent[trial,key,row['predicate']]+=1
                K.count_after(table,public,si)
                seen.update(r['predicate'] for r in public['scene'])
                if public['feedback']['f_fired']:seen.add(public['feedback']['feedback_content']['predicate'])
                gate1+=1;gate4+=1
    except BaseException as error:
        if failure is None:failure={'gate':'input_or_information_or_gradient','world':world,'seed':seed,
                                    'trial':gate1,'error':repr(error)}
        raise
    finally:
        result={'passed':failure is None and gate1==1740,'world':world,'seed':seed,'trials':gate1,
                'gate1_trials':gate1,'gate4_trials':gate4,'modes':['binary','global','position'],
                'gradient_examples':examples,'counts':dict(counts),'failure':failure,
                'frequency_table_final_keys':len(table),'frequency_table_final_events':sum(sum(v.values()) for v in table.values()),
                'inputs':inputs,'output':fingerprint(destination),
                'model_or_memory_updated':False,'rng_consumed':False,
                'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        resultpath.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert inputs==[fingerprint(source),fingerprint(check_path)]
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--world',type=int,choices=(1,2),required=True)
    p.add_argument('--seed',type=int,choices=range(1,21),required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();features(a.input,a.world,a.seed,a.output)


if __name__=='__main__':main()
