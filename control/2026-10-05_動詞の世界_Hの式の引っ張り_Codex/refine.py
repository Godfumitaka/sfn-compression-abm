"""H回答の席を重みを使わず同定し、席無しと記録不足を区別する。段1だけ。"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
import resource
import time
import audit


def main():
    began=time.monotonic()
    plan=json.loads((audit.OLD/'plan.json').read_text())
    initial=json.loads((audit.OUT/'gate_result.json').read_text())
    assert initial['runs']==30 and not initial['stage2_executed']
    hop=audit.higher_order_predicates(audit.load_seed(audit.SOURCE/'tools/verb/U-011_seed_verb.json'))
    original=list(csv.DictReader((audit.OUT/'missing_fields.csv').open()))
    missing=[r for r in original if r['phase']=='training']
    rows=[]
    examples=[]
    errors=[]
    totals=Counter()
    for run in plan['runs']:
        assert 1<=run['seed']<=5
        root=audit.OLD/run['label']/'run'
        ledger=next((root/'ledgers/cells').glob(f'*/seed{run["seed"]:03d}.jsonl.gz'))
        probe=root/'side'/ledger.parent.name/f'seed{run["seed"]:03d}.probe.jsonl'
        points=defaultdict(list)
        for p in map(json.loads,probe.open()):
            assert p['level']==1 and p['verb_probe']=='past'
            points[p['t']].append(p)
        counter=Counter()
        gaps=Counter()
        state=None
        with gzip.open(ledger,'rt') as f:
            header=json.loads(next(f))
            assert header['run_seed']==run['seed'] and header['trial_count']==5000
            for t,line in enumerate(f):
                row=json.loads(line)
                assert row['prediction_order']==t
                snap=row['state_snapshot']
                state=snap['value'] if snap['kind']=='full' else audit._apply(state,snap['changes'])
                if not points.get(t+1):
                    continue
                assert hashlib.sha256(audit._json_bytes(state)).hexdigest()==row['agent_state_snapshot_hash']
                counter['state_hashes']+=1
                for p in points[t+1]:
                    counter['probe_past']+=1
                    if not p.get('R_used'):
                        counter['probe_no_used_definition']+=1
                        continue
                    name,born=p['R'].rsplit('@',1)
                    d=state['definitions'][name]
                    assert d['registered_at']==int(born)
                    if p['answer'] is None:
                        reason=p['abstain']
                        if reason=='no_projectable_relation':
                            counter['probe_known_no_answer_seat']+=1
                        else:
                            gaps['probeの黙りに対象の席・写像・分布の記録が無い:'+reason]+=1
                            if sum(e['run']==run['label'] and e['phase']=='probe_silence' for e in examples)<3:
                                examples.append({'run':run['label'],'phase':'probe_silence','t':p['t'],'verb':p['verb_name'],
                                                 'record':p,'path':str(probe.relative_to(audit.ROOT))})
                        continue
                    src=p['source']
                    st='F' if src=='F_proj' else src.removesuffix('_fill')
                    counter['probe_answer_source_'+st]+=1
                    if st!='H':
                        continue
                    # 同定では履歴の回数・p_hat・式の答えを使わない。
                    # Hからの出力名は同じ階・同じアリティの席の履歴に含まれる必要がある。
                    possible=[]
                    ids={rr['relation']['relation_id'] for rr in d['constituents']}
                    for rr in d['constituents']:
                        s,hist=audit.seat(d,rr,state)
                        higher=any(a in ids for a in rr['relation']['arguments'])
                        if (s=='H' and p['answer'] in hist and len(rr['relation']['arguments'])==len(p['args'])
                                and (p['answer'] in hop)==higher):
                            possible.append(rr)
                    if len(possible)!=1:
                        gaps[f'H回答の席が履歴の名・階・アリティだけでは一意でない:{len(possible)}']+=1
                        examples.append({'run':run['label'],'phase':'probe_H_nonunique','t':p['t'],'verb':p['verb_name'],
                                         'record':p,'possible_slots':[r['slot_index'] for r in possible],
                                         'path':str(probe.relative_to(audit.ROOT))})
                        continue
                    rr=possible[0]
                    calc,weights,status=audit.formula(d,rr,state,hop,1.0)
                    counter['independent_H_checked']+=1
                    if calc!=p['answer']:
                        counter['independent_H_mismatches']+=1
                        errors.append({'run':run['label'],'t':p['t'],'verb':p['verb_name'],'R':p['R'],'slot':rr['slot_index'],
                                       'recorded':p['answer'],'calculated':calc,'history':audit.seat(d,rr,state)[1],
                                       'p_hat':state['p_hat'],'weights':weights})
            assert t==4999
        for detail,count in gaps.items():
            missing.append({'run':run['label'],'arm':run['arm'],'U':run['U'],'seed':run['seed'],
                            'phase':'probe','field':'answer_slot','detail':detail,'count':count})
        rows.append({'run':run['label'],'arm':run['arm'],'U':run['U'],'seed':run['seed'],**dict(counter),'missing_probe':sum(gaps.values())})
        totals.update(counter)
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
    audit.csv_out(audit.OUT/'probe_independent_checks.csv',rows)
    audit.csv_out(audit.OUT/'missing_fields_refined.csv',missing)
    audit.dump(audit.OUT/'missing_examples_refined.json',examples)
    audit.dump(audit.OUT/'independent_H_probe_mismatches.json',errors)
    result={'runs':30,'gate1_mismatch_rows':initial['gate1_mismatch_rows'],'counts':dict(totals),
            'training_answer_checked':initial['gate2_counts'].get('training_answer:checked',0),
            'training_answer_mismatches':initial['gate2_counts'].get('training_answer:mismatch',0),
            'missing_training':sum(int(r['count']) for r in missing if r['phase']=='training'),
            'missing_probe':sum(int(r['count']) for r in missing if r['phase']=='probe'),
            'stage2_executed':False,'model_reruns':0,'elapsed_seconds':time.monotonic()-began,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'slot_identification_uses_H_weight':False}
    result['stop_at_stage1']=bool(result['missing_training'] or result['missing_probe'] or errors or result['gate1_mismatch_rows'] or result['training_answer_mismatches'])
    audit.dump(audit.OUT/'gate_result_refined.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
