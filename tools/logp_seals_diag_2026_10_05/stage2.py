"""誕生・選択シール・記憶量を保存記録から数える。更新関数は呼ばない。"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace as NS
from stage1 import ARMS,MAIN,ROOT,SRC,input_paths,op,sha,_apply,opaque_id

sys.path.insert(0,str(SRC/'tools'))
import v39
from sealmem import mem_parts,_hist
from abm.seed import load_seed,higher_order_predicates
from abm.definition import FrequencyTable

def seal_info(d,hist,ids):
    out=[]
    for row in d['constituents']:
        if row['relation']['relation_id'] not in ids:continue
        key=str((d['name'],row['slot_index']));h=hist.get(key)
        st='F' if row['alive'] else 'H' if key in hist else 'U'
        if st=='F': cls='F '+row['relation']['predicate']
        elif st=='U': cls='U'
        else:
            names={p for p,n in h.items() if n>=1} if isinstance(h,dict) else set(h or ())
            cls='H[sig_n]' if names=={'sig_n'} else 'H[sig_e]' if names=={'sig_e'} else 'H[両方]' if names=={'sig_n','sig_e'} else 'H[その他/空]'
        out.append({'slot':row['slot_index'],'state':st,'class':cls,'history':h,
                    'name':row['relation']['predicate'] if st=='F' else None})
    return out

def compact_seal(seals):
    return seals[0]['class'] if len(seals)==1 else 'シール席なし' if not seals else '複数:'+','.join(s['class'] for s in seals)

def normal_pred(shop):return 'hold' if shop=='甲' else 'hold_b'

def strict_structure(d,relation_ids):
    """strict-pcの関係位置の符号。IDの種類を記録から復元して費用だけを数える。"""
    own={r['relation']['relation_id'] for r in d['constituents']}
    relpos={a for r in d['constituents'] for a in r['relation']['arguments'] if a not in own and a in relation_ids}
    ents={a for r in d['constituents'] for a in r['relation']['arguments'] if a not in own and a not in relpos}
    m=len({r['slot_index'] for r in d['constituents']});e=len(ents)
    bits=v39.clog2(v39.CFG['T'])+v39.I(m)+v39.I(e)
    for r in d['constituents']:
        args=r['relation']['arguments'];bits+=v39.I(len(args))
        bits+=sum(1+(v39.clog2(m) if a in own or a in relpos else v39.clog2(e)) for a in args)
    return bits

def group_answer(pred,shop,world):
    pred={'X':'hold','Y':'hold_b'}.get(pred,pred)
    if pred is None:return '未確定'
    n=normal_pred(shop);e=n if world==1 else 'hold_b' if n=='hold' else 'hold'
    if pred==n==e:return '共通'
    if pred==n:return '通常'
    if pred==e:return '例外'
    return 'その他の答え'

def current_group(d,state,door_ids,info,world,hop):
    answer=[]; details=[]
    rows=[NS(slot_index=r['slot_index'],alive=r['alive'],relation=NS(**{**r['relation'],'arguments':tuple(r['relation']['arguments'])})) for r in d['constituents']]
    dn=NS(name=d['name'],constituents=rows)
    ph=FrequencyTable(**{**state['p_hat'],'alive_vocab':frozenset(state['p_hat']['alive_vocab'])});hist=_hist(state['slot_history'])
    for row in rows:
        origin=door_ids.get(row.relation.relation_id)
        if origin is None:continue
        key=(d['name'],row.slot_index)
        if row.alive:p=row.relation.predicate;kind='F'
        elif key in hist:p,_=v39.h_answer(dn,row,hist,ph,1.0,hop);kind='H'
        else:p=None;kind='U'
        group='U（名前なし）' if kind=='U' else group_answer(p,info[origin]['shop_type'],world)
        answer.append(group);details.append({'slot':row.slot_index,'state':kind,'answer':p,'group':group,'origin_trial':origin})
    return (answer[0] if len(set(answer))==1 else '複数の答え' if answer else 'ドア席なし'),details

def write_csv(path,rows,fields=None):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def work(job):
    arm,seed=job;start=time.monotonic();paths=input_paths(arm,seed)
    old=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.json').read_text())['input_sha256']
    assert old=={str(p):sha(p) for p in paths.values()}
    sd=load_seed(SRC/'tools/shop/U-011_seed_shop.json');dictionary=list(sd.data['marginal'])
    for p in ('sig_n','sig_e','attach','hold_b'):
        if p not in dictionary:dictionary.append(p)
    v39.CFG.update(T=1740,D=len(dictionary),dict_index={p:i for i,p in enumerate(dictionary)})
    hop=higher_order_predicates(sd)|{'attach'}
    vrecords={}
    with op(paths['side']) as f:
        for line in f:
            r=json.loads(line)
            if r.get('kind')=='v39':vrecords[r['trial']]=r
    birth_records=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.birth_records.json').read_text())
    born_by_t={b['trial']:b for b in birth_records}
    doors_saved={r['trial']:r for r in json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.door_records.json').read_text())}
    world=2 if 'w2' in arm else 1;price=0.065 if arm.endswith('0.065') else float(MAIN)
    ids={opaque_id(seed,t,'relation:shop:sig'):t for t in range(1740)}
    door_ids={opaque_id(seed,t,'relation:tree:0.0.0'):t for t in range(1740)}
    info={};state=None;births=[];doors=[];checkpoints=[];definitions=[];birth_groups={};count=Counter();relation_ids=set()
    with op(paths['ledger']) as f:
        header=json.loads(next(f));assert header['run_seed']==seed and header['trial_count']==1740
        for line in f:
            row=json.loads(line)
            if row.get('record_type','trial')!='trial':continue
            t=row['prediction_order'];info[t]={k:row[k] for k in ('shop_type','shop_cue','door_pred')}
            relation_ids.update(row['observable_mask_edges'])
            relation_ids.add(row['held_out_content']['relation_id'])
            pre=state;ss=row['state_snapshot']
            if ss['kind']=='full':state={k:ss['value'][k] for k in ('definitions','slot_history','p_hat')}
            else:
                delta={k:v for k,v in ss['changes'].items() if k in ('definitions','slot_history','p_hat')}
                state=_apply(state,delta)
            if t in born_by_t:
                b=born_by_t[t];dd=state['definitions'][b['R']];source=b['source'];base=source['base_written_at']
                days='+'.join(sorted((info[base]['shop_cue'],info[t]['shop_cue'])))
                group=set()
                for c in dd['constituents']:
                    origin=door_ids.get(c['relation']['relation_id'])
                    if origin is not None:group.add(group_answer(info[origin]['door_pred'],info[origin]['shop_type'],world))
                birth_group=next(iter(group)) if len(group)==1 else '複数' if group else 'ドア席なし'
                birth_groups[(dd['name'],dd['registered_at'])]=birth_group
                seals=seal_info(dd,state['slot_history'],ids)
                assert len(seals)==b['seal_count']
                rowborn={'arm':arm,'world':world,'lambda':price,'seed':seed,'trial':t,'R':b['R'],'base_trial':base,
                         'base_day':info[base]['shop_cue'],'current_day':info[t]['shop_cue'],'material_days':days,
                         'door_birth_group':birth_group,'seal_count':len(seals),'score_immediate_state':'F' if seals else '',
                         'post_state':seals[0]['state'] if len(seals)==1 else '席なし' if not seals else '複数',
                         'seal_details':json.dumps(seals,ensure_ascii=False),
                         'birth_names_and_histories':json.dumps(b['seals'],ensure_ascii=False)}
                births.append(rowborn)
                count[('birth',days,rowborn['post_state'])]+=1
            if row['held_out_is_door'] and row['shop_cue']=='e':
                saved=doors_saved[t];R=vrecords[t].get('R_used') or row['R_used']
                if row['R_used'] and vrecords[t].get('R_used'):assert row['R_used']==vrecords[t]['R_used']
                seals=seal_info(pre['definitions'][R],pre['slot_history'],ids) if R else []
                category=compact_seal(seals) if R else '選択なし'
                doors.append({'arm':arm,'world':world,'lambda':price,'seed':seed,'trial':t,'shop_type':row['shop_type'],
                              'day':'e','outcome':saved['outcome'],'classification':saved['class'] or '',
                              'R_used':row['R_used'] or '', 'R_selected':R or '',
                              'selection_source':'side v39.R_used' if vrecords[t].get('R_used') else '台帳 R_used' if R else '記録に選択なし',
                              'seal_class':category,'seal_count':len(seals),
                              'seal_details':json.dumps(seals,ensure_ascii=False),'correct_candidates':saved['correct_candidates'],
                              'correct_exception_definition_exists':None if saved['correct_candidates'] is None else bool(saved['correct_candidates'])})
            if (t+1)%500==0 or t==1739:
                m=mem_parts(v39,state);v=vrecords[t]
                S=sum(strict_structure(d,relation_ids) for d in state['definitions'].values())
                m['strict_pc_structure_adjustment']=S-m['S'];m['total']+=S-m['S'];m['S']=S
                assert m['total']==v['bits_after'],(arm,seed,t,m['total'],v['bits_after'])
                assert (m['defs'],m['nF'],m['nH'],m['nU'])==(v['defs'],v['F'],v['H'],v['U'])
                checkpoints.append({'arm':arm,'world':world,'lambda':price,'seed':seed,'trial':t,'trials_completed':t+1,**m,
                                    'side_total':v['bits_after'],'side_match':True})
                for dd in state['definitions'].values():
                    cgroup,details=current_group(dd,state,door_ids,info,world,hop)
                    seals=seal_info(dd,state['slot_history'],ids)
                    definitions.append({'arm':arm,'world':world,'lambda':price,'seed':seed,'trial':t,'trials_completed':t+1,
                                        'R':dd['name'],'registered_at':dd['registered_at'],
                                        'birth_door_group':birth_groups[(dd['name'],dd['registered_at'])],
                                        'current_door_group':cgroup,'current_door_details':json.dumps(details,ensure_ascii=False),
                                        'seal_class':compact_seal(seals),'seal_count':len(seals),'seal_details':json.dumps(seals,ensure_ascii=False)})
    assert old=={str(p):sha(p) for p in paths.values()}
    dest=ROOT/'stage2'/arm;dest.mkdir(parents=True,exist_ok=True)
    for name,rows in [('births',births),('doors',doors),('memory',checkpoints),('definitions',definitions)]:
        write_csv(dest/f'seed{seed:03d}.{name}.csv',rows)
    result={'arm':arm,'seed':seed,'births':len(births),'exception_door_cases':len(doors),'checkpoints':len(checkpoints),
            'input_unchanged':True,'memory_side_matches':True,'seconds':time.monotonic()-start,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (dest/f'seed{seed:03d}.check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    assert json.loads((ROOT/'stage1_summary.json').read_text())['stage1_pass']
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--workers',type=int,default=2)
    args=ap.parse_args();jobs=[(a,s) for a in ARMS for s in ([1] if args.pilot else range(1,21))]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:results=list(pool.map(work,jobs,chunksize=1))
    (ROOT/('stage2_pilot_summary.json' if args.pilot else 'stage2_summary.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
