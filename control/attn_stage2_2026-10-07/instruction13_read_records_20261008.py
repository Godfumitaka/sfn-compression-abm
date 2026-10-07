"""指示13。固定した既存記録を読むだけ。模型のモジュールは読み込まない。"""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[2]
ROOT = BASE / 'stage2_attention_2026-10-07/instruction8_3368df41_20261007'
OUT = Path(__file__).resolve().parent
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
PROVENANCE = []

def stream(path, cutoff):
    start = path.stat(); digest = hashlib.sha256(); count = 0; partial = False
    opener = gzip.open if path.suffix == '.gz' else open
    try:
        with opener(path, 'rb') as f:
            while True:
                try: line = f.readline()
                except EOFError:
                    partial = True; break
                if not line: break
                if not line.endswith(b'\n'):
                    partial = True; break
                row = json.loads(line)
                trial = row.get('trial', row.get('prediction_order'))
                if trial is not None and trial > cutoff: break
                digest.update(line); count += 1
                yield row
    finally:
        PROVENANCE.append(dict(path=str(path),size_at_start=start.st_size,
            size_at_end=path.stat().st_size,mtime_at_start=start.st_mtime,
            accepted_lines=count,logical_prefix_sha256=digest.hexdigest(),
            incomplete_gzip_tail=partial,cutoff_zero_based=cutoff))

def distribution(values):
    s=sorted(values); n=len(s)
    if not n: return {'n':0}
    return dict(n=n,zero=sum(v==0 for v in s),negative=sum(v<0 for v in s),
        positive=sum(v>0 for v in s),min=s[0],median=s[(n-1)//2],
        p90=s[int((n-1)*.9)],max=s[-1],mean=sum(s)/n)

def read_mode(mode, cutoff):
    directory=ROOT/mode; trials={}; side={}; born={}; initial={}; initial_values=[]
    ledger=directory/'output/ledgers/cells'/CELL/'seed001.jsonl.gz'
    event_counts=Counter(); removed_reasons=Counter(); example=None; birth_fh_points=[]; fh_release=[]
    header=None
    for row in stream(ledger,cutoff):
        if row.get('record_type') != 'trial':
            header=row;continue
        t=row['prediction_order']; reg=row.get('registration_event')
        events=row.get('deletion_event') or []; removed=[e for e in events if e['kind']=='definition_removed']
        conversions=[e for e in events if e.get('v39') in ('FH','HU')]
        reasons=Counter()
        for e in removed:
            chain=[x for x in conversions if x['R']==e['R']]
            reason='all_U:'+','.join(sorted({x['why'] for x in chain})) if chain else 'other_no_chain'
            reasons[reason]+=1;removed_reasons[reason]+=1
        if reg and not reg['was_extension']: born[t,reg['R']]=reg
        if reg and not reg['was_extension']:
            for e in conversions:
                if e['R']==reg['R'] and e['v39']=='FH':
                    birth_fh_points.append(e['V']);fh_release.append(e['dC'])
        if example is None and reg and removed:
            example=dict(trial=t,registration=reg,deletions=events,m_alloc=row['m_alloc'],m_live=row['m_live'])
        for e in conversions:event_counts[e['v39']+':'+e['why']]+=1
        trials[t]=dict(trial=t,disclosed=row['f_fired'],births=int(bool(reg) and not reg['was_extension']),
            assimilation=int(bool(reg) and reg['was_extension']),removed=len(removed),
            immediate_birth_removed=int(bool(reg) and any(e['R']==reg['R'] for e in removed)),
            removed_reasons=dict(reasons),m_alloc=row['m_alloc'],m_live=row['m_live'],
            support_gate_failures=sum(not x.get('passed',True) for x in (row.get('tau_passed_defs') or [])),
            conversions=len(conversions))
    for row in stream(directory/'output/side'/CELL/'seed001.jsonl',cutoff):
        t=row.get('trial')
        if t not in trials:continue
        if row['kind']=='v39':
            trials[t].update({k:row[k] for k in ['F','H','U','defs','bits_before','bits_after']})
            trials[t]['birth_noop'] = bool((row.get('m1') or {}).get('birth_noop'))
        if row['kind']=='v310be':side[t]=row
    perf={x['trial']:x for x in stream(directory/'performance.jsonl',cutoff)}
    stage2path=directory/'output/stage2'/CELL/'seed001.jsonl.gz'
    stage_rows=[]; stages=[]; birth_seconds=[]; birth_deltas=[]; initial_examples=[]; classes=Counter(); virtual_work=Counter()
    if stage2path.exists():
        for row in stream(stage2path,cutoff):
            if row['trial'] not in trials:continue
            stages.append({k:row[k] for k in ['trial','f_fired','seconds','wrapper_seconds','thinned_seats','rerankings']})
            if row['f_fired']:
                stage_rows.extend(x['delta'] for x in row['rows'])
        for row in stream(Path(str(stage2path)+'.initial.jsonl.gz'),cutoff):
            if row.get('kind')!='stage2_birth_virtual':continue
            key=(row['trial'],row['R'])
            initial[key]=row
            vals=list(row['delta_by_slot'].values()); initial_values.extend(vals)
            birth_seconds.append(row['seconds'])
            birth_deltas.extend(x['delta'] for q in row['records'] for x in q['rows'])
            for q in row['records']:
                classes[q['class']+':questions']+=1
                classes[q['class']+':seats']+=len(q['rows'])
                classes[q['class']+':zero_seats']+=sum(x['delta']==0 for x in q['rows'])
            for k in ['virtual_questions','evaluated_questions','thinned_seats','rerankings']:virtual_work[k]+=row[k]
            if len(initial_examples)<3:
                initial_examples.append({k:row[k] for k in ['trial','R','delta_by_slot','mass_by_slot','question_counts','virtual_counts','seconds']})
    actual_vals=[v for k,row in initial.items() if k in born for v in row['delta_by_slot'].values()]
    actual_seconds=sum(row['seconds'] for k,row in initial.items() if k in born)
    rows=[]
    for t,row in sorted(trials.items()):
        if (t+1)%100==0 or t==max(trials):
            first=(t//100)*100
            block=[x for i,x in trials.items() if first<=i<=t]
            reasons=Counter();
            for x in block:reasons.update(x['removed_reasons'])
            p=perf.get(t,{})
            rows.append(dict(completed=t+1,end_trial=t,block_start=first+1,
                definitions=row['defs'],F=row['F'],H=row['H'],U=row['U'],bits=row['bits_after'],
                births=sum(x['births'] for x in block),removed=sum(x['removed'] for x in block),
                immediate_birth_removed=sum(x['immediate_birth_removed'] for x in block),
                removed_reasons=dict(reasons),elapsed=p.get('elapsed_seconds'),
                stage2_seconds=sum(x['seconds'] for x in stages if first<=x['trial']<=t),
                birth_seconds=sum(x['seconds'] for x in initial.values() if first<=x['trial']<=t)))
    if set(trials)!=set(range(cutoff+1)):raise RuntimeError((mode,'incomplete ledger',len(trials),cutoff))
    if any('defs' not in x for x in trials.values()):raise RuntimeError('missing v39 rows')
    lambdas=sorted({row['lam'] for row in side.values() if 'lam' in row})
    command=json.loads((directory/'native_command.json').read_text())
    price={x:float(command[command.index(x)+1]) for x in ['--v39-price','--e-price']}
    elapsed=perf[cutoff].get('elapsed_seconds')
    summary=dict(mode=mode,completed=len(trials),header=header,prices=price,E_lam_recorded=lambdas,
        final=trials[cutoff],zero_definition_trials=sum(x['defs']==0 for x in trials.values()),
        max_definitions=max(x['defs'] for x in trials.values()),max_bits=max(x['bits_after'] for x in trials.values()),
        births=len(born),removals=sum(x['removed'] for x in trials.values()),
        immediate_birth_removed=sum(x['immediate_birth_removed'] for x in trials.values()),
        birth_noop_trials=sum(x['birth_noop'] for x in trials.values()),
        assimilation=sum(x['assimilation'] for x in trials.values()),
        removal_reasons=dict(removed_reasons),conversion_reasons=dict(event_counts),
        actual_birth_initial_records=sum(k in initial for k in born),
        virtual_initial_records=len(initial),virtual_records_not_actual_birth=sum(k not in born for k in initial),
        actual_birth_delta=distribution(actual_vals),all_virtual_initial_delta=distribution(initial_values),
        immediate_birth_FH_converted_V=distribution(birth_fh_points),FH_release_bits=distribution(fh_release),
        virtual_work=dict(virtual_work),virtual_class_counts=dict(classes),
        virtual_question_seat_delta=distribution(birth_deltas),
        disclosed_trials=sum(x['disclosed'] for x in trials.values()),
        stage2_recorded_trials=len(stages),stage2_recorded_disclosed_trials=sum(x['f_fired'] for x in stages),
        missing_stage2_trials=sorted(set(trials)-{x['trial'] for x in stages}) if stage2path.exists() else [],
        disclosed_trials_no_stage2_seats=sum(x['f_fired'] and x['thinned_seats']==0 for x in stages),
        disclosed_seat_delta=distribution(stage_rows),
        elapsed=elapsed,seconds_per_trial=None if elapsed is None else elapsed/len(trials),
        performance_seconds_sum=sum(x['seconds'] for x in perf.values()),
        stage2_additional_seconds=sum(x['seconds'] for x in stages),
        stage2_wrapper_seconds=sum(x['wrapper_seconds'] for x in stages),
        all_recorded_birth_seconds=sum(birth_seconds),actual_birth_seconds=actual_seconds,
        unassigned_elapsed=None if elapsed is None else elapsed-sum(x['seconds'] for x in stages)-sum(birth_seconds),
        max_prediction_candidates=max((p.get('candidates',0) for p in perf.values()),default=0),
        initial_examples=initial_examples,registration_retirement_example=example,
        blocks=rows,unmeasured=['model_only','snapshot_encoding','snapshot_hash','save','restore'])
    with (OUT/(mode+'_trials.csv')).open('w') as f:
        fields=['trial','defs','F','H','U','bits_before','bits_after','births','assimilation','removed','immediate_birth_removed','disclosed','m_alloc','m_live','conversions','birth_noop']
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(trials.values())
    return summary

result={'at':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
    'fixed_cutoff_note':'ON全長は04:17:51に確認した番号1173まで。模型・原記録へ書かない。',
    'modes':[read_mode('on_full',1173),read_mode('on_preflight',19),read_mode('off',1739)],
    'provenance':PROVENANCE}
(OUT/'diagnosis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{k:v for k,v in x.items() if k not in ['header','blocks','initial_examples','registration_retirement_example','final']} for x in result['modes']],ensure_ascii=False,indent=2))
