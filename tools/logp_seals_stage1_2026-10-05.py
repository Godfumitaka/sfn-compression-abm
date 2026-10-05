"""段1のみ。保存済み台帳・採点・分類を読み、模型は呼ばない。"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor

_HERE = Path(__file__).resolve()
_DEFAULT = _HERE.parents[3]/'codex_logp_seals_2026-10-05' if _HERE.parent.name=='tools' else _HERE.parent
ROOT = Path(os.environ.get('LOGP_SEAL_WORKSPACE',str(_DEFAULT))).resolve()
W = ROOT.parent
SRC = W / 'codex_explore3_2026-10-04/source'
sys.path.insert(0, str(SRC))
from abm.loop import _apply, _json_bytes
from abm.world import opaque_id

MAIN = '0.01873710622997919'
ARMS = [f'L-B_w2_A_lam{MAIN}', 'L-B_w2_A_lam0.065', f'L-B_w1_A_lam{MAIN}',
        'n3_w2_A_L50', 'n3_w1_A_L50']

def arm_root(arm):
    if arm.startswith('L-B'):
        return W / 'codex_explore3_2026-10-04/runs' / arm
    if 'w2' in arm:
        return W / 'codex_attn_2026-10-03/material_rebuild_2026-10-04' / arm
    return W / 'codex_attn_2026-10-03/world1_rebuild' / arm

def stored(path):
    return path if path.exists() else Path(str(path)+'.gz')

def op(path):
    return gzip.open(path, 'rt', encoding='utf-8') if path.suffix == '.gz' else path.open(encoding='utf-8')

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(1024*1024): h.update(b)
    return h.hexdigest()

def input_paths(arm, seed):
    root = arm_root(arm)
    cell, = (root/'ledgers/cells').iterdir()
    led = cell/f'seed{seed:03d}.jsonl.gz'
    side = stored(root/'side'/cell.name/f'seed{seed:03d}.jsonl')
    shop = stored(root/'side'/cell.name/f'seed{seed:03d}.shop.jsonl')
    if arm.startswith('L-B'):
        clsroot = W/'codex_explore3_2026-10-04/classification'/arm
        cases = clsroot/'候補'/arm/f'seed{seed:03d}.cases.jsonl'
        check = clsroot/'候補'/arm/f'seed{seed:03d}.check.json'
    else:
        cases = W/'codex_attn_2026-10-03/stageCD_doors_2026-10-05/cases'/arm/f'seed{seed:03d}.cases.jsonl.gz'
        check = None
    paths = {'ledger':led, 'side':side, 'shop':shop, 'cases':cases, 'flag':root/'flag.json'}
    if check: paths['classification_check'] = check
    return paths

def work(job):
    arm, seed = job
    assert 1 <= seed <= 20
    start=time.monotonic(); paths=input_paths(arm,seed)
    for p in paths.values(): assert p.is_file(), p
    before={str(p):sha(p) for p in paths.values()}
    side={}; shop={}; birth_source={}; errors=[]
    with op(paths['side']) as f:
        for line in f:
            r=json.loads(line)
            if r.get('kind')=='v39': side[r['trial']]=r
            if r.get('kind')=='birth': birth_source[(r['trial'],r['R'])]=r
    with op(paths['shop']) as f:
        for line in f:
            r=json.loads(line)
            if r.get('which')=='sig': shop.setdefault(r['trial'],[]).append(r)
    with op(paths['cases']) as f: cases={r['trial']:r for r in map(json.loads,f)}
    if 'classification_check' in paths:
        ck=json.loads(paths['classification_check'].read_text())
        for key in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'):
            if ck[key]: errors.append({'check':key,'count':ck[key]})
    out=ROOT/'stage1'/arm; out.mkdir(parents=True,exist_ok=True)
    counts={day:Counter() for day in ('e','n')}; births=[]; door_rows=[]
    state=None; trials=0; hash_errors=0; cues=[]
    with op(paths['ledger']) as f:
        header=json.loads(next(f)); assert header['run_seed']==seed
        ids={opaque_id(seed,t,'relation:shop:sig'):t for t in range(header['trial_count'])}
        for line in f:
            r=json.loads(line)
            if r.get('record_type','trial')!='trial': continue
            t=r['prediction_order']; assert t==trials
            ss=r['state_snapshot']; state=ss['value'] if ss['kind']=='full' else _apply(state,ss['changes'])
            # 試運転は全試行、全種の集計は誕生・500試行ごと・最後の状態を直接検証する。
            # 既存の分類は全件の予測・選択・候補再現と入力台帳の指紋を検証済み。
            vv=side[t]; rr=(vv.get('m1') or {}).get('reg')
            check_state=os.environ.get('LOGP_SEAL_HASH_MODE','full')=='full' or (rr and not rr[1]) or (t+1)%500==0 or t==header['trial_count']-1
            if check_state and hashlib.sha256(_json_bytes(state)).hexdigest()!=r['agent_state_snapshot_hash']:
                hash_errors+=1
                errors.append({'trial':t,'check':'state_hash'})
            trials+=1
            v=side[t]; m=v.get('m1') or {}; reg=m.get('reg')
            if reg and not reg[1]:
                name=reg[0]; dd=state['definitions'].get(name)
                src=birth_source.get((t,name))
                if dd is None:
                    errors.append({'trial':t,'R':name,'check':'birth_definition_absent_after_trial',
                                   'births_rec':m.get('births_rec'),'retired':name in v.get('retire',[])})
                    births.append({'trial':t,'R':name,'recoverable':False,'reason':'same_trial_retired'})
                else:
                    recs={x['slot']:x for x in m.get('births_rec',[])}
                    seals=[]
                    for c in dd['constituents']:
                        rid=c['relation']['relation_id']
                        if rid not in ids: continue
                        slot=c['slot_index']; born=recs.get(slot)
                        key=str((name,slot)); seat=state['v39_seats'].get(key)
                        h=state['slot_history'].get(key)
                        origin=ids[rid]
                        predicate='sig_'+(r['shop_cue'] if origin==t else cues[origin])
                        if born is None or seat is None or '履歴' not in born:
                            errors.append({'trial':t,'R':name,'slot':slot,'check':'birth_seal_fields_missing'})
                        actual='F' if c['alive'] else 'H' if key in state['slot_history'] else 'U'
                        if seat is not None and seat['state']!=actual:
                            errors.append({'trial':t,'R':name,'slot':slot,'check':'seat_state_mismatch'})
                        stamps=[x for x in shop.get(t,[]) if x['R']==name and x['slot']==slot and x['reg']==dd['registered_at']]
                        if len(stamps)!=1 or stamps[0]['from']!='生まれた' or stamps[0]['to']!=actual:
                            errors.append({'trial':t,'R':name,'slot':slot,'check':'shop_birth_state_mismatch'})
                        seals.append({'slot':slot,'relation_id':rid,'origin_trial':origin,
                                      'birth_predicate':predicate,'post_state':actual,'post_history':h,
                                      'score_history':born.get('履歴') if born else None,
                                      'score':born,'shop':stamps[0] if stamps else None})
                    births.append({'trial':t,'R':name,'recoverable':True,'seal_count':len(seals),
                                   'source':src,'seals':seals})
            cues.append(r['shop_cue'])
            if r['held_out_is_door']:
                day=r['shop_cue']; outcome='黙り' if r['prediction_kind']=='Abstain' else '正解' if r['hit']==1 else '外れ'
                counts[day][outcome]+=1; cl=None; case=cases.get(t)
                if arm.startswith('n3'):
                    if case is None or case['baseline_outcome']!={'正解':'correct','外れ':'wrong','黙り':'silent'}[outcome] or case['baseline']['R_used']!=r['R_used']:
                        errors.append({'trial':t,'check':'case_primary_mismatch'})
                    good=case['actual_correct_candidates'] if case else 0
                else:
                    if case is not None and (case['本物の当たり']!=r['hit'] or case['選ばれた']!=r['R_used']):
                        errors.append({'trial':t,'check':'case_primary_mismatch'})
                    good=len(case['正しく答える候補']) if case else None
                if outcome=='外れ':
                    if good is None: errors.append({'trial':t,'check':'wrong_case_missing'})
                    cl='選び間違い' if good else '区別の喪失'; counts[day][cl]+=1
                door_rows.append({'arm':arm,'seed':seed,'trial':t,'day':day,'outcome':outcome,'class':cl,
                                  'R_used':r['R_used'],'correct_candidates':good})
    after={str(p):sha(p) for p in paths.values()}
    if before!=after: errors.append({'check':'input_changed'})
    result={'arm':arm,'seed':seed,'trials':trials,'expected_trials':header['trial_count'],
            'counts':{d:{k:counts[d][k] for k in ('正解','外れ','黙り','選び間違い','区別の喪失')} for d in ('e','n')},
            'births':len(births),'hash_errors':hash_errors,'errors':errors,
            'hash_mode':os.environ.get('LOGP_SEAL_HASH_MODE','full'),
            'input_sha256':before,'input_unchanged':before==after,'seconds':time.monotonic()-start,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)}
    (out/f'seed{seed:03d}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/f'seed{seed:03d}.birth_records.json').write_text(json.dumps(births,ensure_ascii=False)+'\n')
    (out/f'seed{seed:03d}.door_records.json').write_text(json.dumps(door_rows,ensure_ascii=False)+'\n')
    print(json.dumps({'arm':arm,'seed':seed,'seconds':round(result['seconds'],2),'errors':len(errors),'births':len(births),'peak_rss_bytes':result['peak_rss_bytes']},ensure_ascii=False),flush=True)
    return result

def expected(arm):
    if arm.startswith('L-B'):
        return json.loads((W/'codex_explore3_2026-10-04/classification'/arm/'summary.json').read_text())['days']
    if 'w2' in arm:
        return {'e':dict(zip(('正解','外れ','黙り','選び間違い','区別の喪失'),(370,179,63,136,43))),
                'n':dict(zip(('正解','外れ','黙り','選び間違い','区別の喪失'),(2304,99,138,81,18)))}
    return {'e':dict(zip(('正解','外れ','黙り','選び間違い','区別の喪失'),(528,0,84,0,0))),
            'n':dict(zip(('正解','外れ','黙り','選び間違い','区別の喪失'),(2259,0,282,0,0)))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--workers',type=int,default=1)
    args=ap.parse_args(); seeds=[1] if args.pilot else range(1,21)
    jobs=[(a,s) for a in ARMS for s in seeds]
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for r in pool.map(work,jobs,chunksize=1): results.append(r)
    full=not args.pilot; summed={}; mismatch=[]
    for arm in ARMS:
        rows=[r for r in results if r['arm']==arm]
        count={day:{k:sum(r['counts'][day][k] for r in rows) for k in expected(arm)[day]} for day in ('e','n')}
        summed[arm]={'actual':count,'expected':expected(arm),'full_20':full,'births':sum(r['births'] for r in rows),
                     'errors':sum(len(r['errors']) for r in rows)}
        if full and count!=expected(arm): mismatch.append(arm)
    summary={'stage1_pass':full and not mismatch and all(not r['errors'] for r in results),
             'full_20':full,'seeds':list(seeds),'arms':summed,'count_mismatch_arms':mismatch,
             'max_peak_rss_bytes':max(r['peak_rss_bytes'] for r in results),
             'sum_worker_seconds':sum(r['seconds'] for r in results),'workers':args.workers}
    (ROOT/('pilot_summary.json' if args.pilot else 'stage1_summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': main()
