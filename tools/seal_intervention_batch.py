"""注意の固定材料を読むだけで、全ドアの介入を同じ鍵のCSVへ並べる。"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,sys
from collections import Counter
import seal_intervention_diag as diag

WORK=Path(__file__).resolve().parents[2]
ATTN=WORK.parent/'codex_attn_2026-10-03'
ROOTS={1:ATTN/'world1_rebuild/n3_w1_A_L50',2:ATTN/'material_rebuild_2026-10-04/n3_w2_A_L50'}
JAPANESE={'correct':'正解','wrong':'外れ','silent':'黙り'}


def fingerprints(root,seed):
    paths=[root/'flag.json',*root.glob(f'ledgers/cells/*/seed{seed:03d}.jsonl.gz'),
           *root.glob(f'ledgers/cells/*/seed{seed:03d}.done'),*root.glob(f'side/*/seed{seed:03d}.*')]
    result={}
    for p in paths:
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
        result[str(p)]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
    return result


def flatten(rec):
    row={k:rec[k] for k in ('world','seed','trial','day','shop','selector','classification')}
    row.update(baseline_R=rec['original_R'],baseline_outcome=rec['original']['outcome'],
               baseline_predicate=rec['original']['predicate'],baseline_arguments=json.dumps(rec['original']['arguments'],ensure_ascii=False),
               condition_birth_status='未復元' if rec['unrestored'] else '適用',
               condition_birth_restored=len(rec['restored']),condition_birth_unrestored=len(rec['unrestored']))
    for field,result in [('condition_birth',rec['i']),('researcher_selection',rec['ii']),
                         ('iii_a',rec['iii_a']),('iii_b',rec['iii_b']),('iii_c',rec['iii_c'])]:
        result=result or {}
        for key in ('status','outcome','predicate','reason','selected_R','R_used','added_R','added_selected'):
            column=field+'_'+key
            row[column]=result.get(key,row.get(column,''))
        row[field+'_arguments']=json.dumps(result.get('arguments'),ensure_ascii=False)
    if rec['iii_a'] is not None:
        added=rec['iii_a'].get('R',f'DIAG_CONTENT_{rec["seed"]}_{rec["trial"]}')
        row['iii_a_added_R']=added
        row['iii_b_added_R']=added
    row['iii_c_material_trials']=json.dumps((rec['iii_c'] or {}).get('material_trials',[]))
    return row


def export(world,seed,dest):
    cases=ATTN/f'stageCD_doors_2026-10-05/cases/n3_w{world}_A_L50/seed{seed:03d}.cases.jsonl.gz'
    reference={}
    with gzip.open(cases,'rt') as stream:
        for raw in stream:
            c=json.loads(raw)
            if c['door_task']:reference[c['trial']]=c
    rows=[];classes=Counter()
    with gzip.open(dest/f'seed{seed:03d}.interventions.jsonl.gz','rt') as stream:
        for raw in stream:
            rec=json.loads(raw);ref=reference[rec['trial']]
            assert (rec['world'],rec['seed'])==(world,seed)
            assert rec['original']['outcome']==JAPANESE[ref['baseline_outcome']]
            pe=ref['baseline']['predicted_edge'] or {}
            assert rec['original_R']==ref['baseline']['R_used']
            assert rec['original']['predicate']==pe.get('predicate')
            assert rec['original']['arguments']==pe.get('arguments')
            if ref['baseline_outcome']=='wrong':
                expected='selection_mistake' if ref['actual_correct_candidates'] else 'distinction_loss'
                assert rec['classification']==expected,(world,seed,rec['trial'],expected,rec['classification'])
                if rec['day']=='e':classes[expected]+=1
            row=flatten(rec);row['attention_availability']=ref['availability']
            row['attention_correct_candidates']=ref['actual_correct_candidates']
            rows.append(row)
    assert len(rows)==len(reference) and {r['trial'] for r in rows}==set(reference)
    with (dest/f'seed{seed:03d}.cases.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'world':world,'seed':seed,'door_cases':len(rows),'attention_keys_and_classifications_match':True,
            'exception_wrong_classes':dict(classes)}
    previous=dest/f'seed{seed:03d}.join_check.json'
    if previous.exists():
        checked=json.loads(previous.read_text())
        if 'input_files_unchanged' in checked:
            result['input_files_unchanged']=checked['input_files_unchanged']
    (dest/f'seed{seed:03d}.join_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def one(world,seed,dest):
    if seed not in diag.SEEDS:raise ValueError('種は1〜20だけ')
    root=ROOTS[world];before=fingerprints(root,seed)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/f'seed{seed:03d}.input_before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n')
    result=diag.one(root,dest,seed,all_doors=True)
    after=fingerprints(root,seed)
    assert before==after,'注意の入力材料の指紋が変わった'
    check=export(world,seed,dest);check['input_files_unchanged']=len(before)
    (dest/f'seed{seed:03d}.join_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
    return result,check


def aggregate(world,dest):
    summaries=[json.loads((dest/f'seed{s:03d}.summary.json').read_text()) for s in diag.SEEDS]
    joins=[json.loads((dest/f'seed{s:03d}.join_check.json').read_text()) for s in diag.SEEDS]
    counts=Counter();checks=Counter();classes=Counter();rows=[]
    for s,summary,join in zip(diag.SEEDS,summaries,joins):
        assert summary['seed']==join['seed']==s and summary['all_doors'] and summary['limit'] is None
        assert join['attention_keys_and_classifications_match'] and join['input_files_unchanged']>0
        counts.update(summary['counts']);checks.update(summary['checks']);classes.update(join['exception_wrong_classes'])
        with (dest/f'seed{s:03d}.cases.csv').open(newline='') as stream:rows.extend(csv.DictReader(stream))
    assert len(rows)==counts['door_cases']==checks['original_state_unchanged']==checks['prediction_reproduced']
    assert len({(r['world'],r['seed'],r['trial']) for r in rows})==len(rows)
    if world==2:assert classes=={'selection_mistake':136,'distinction_loss':43},dict(classes)
    with (dest/'all_doors.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    focused=[r for r in rows if r['day']=='e' and r['baseline_outcome']=='外れ']
    with (dest/'exception_wrong.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(focused)
    data={'world':world,'seeds':list(diag.SEEDS),'counts':dict(counts),'checks':dict(checks),
          'exception_wrong_classes':dict(classes),'attention_keys_and_classifications_match':True,
          'input_files_unchanged':True,'all_door_rows':len(rows),'exception_wrong_rows':len(focused)}
    (dest/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return data


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--world',type=int,choices=(1,2),required=True)
    ap.add_argument('--seed',type=int);ap.add_argument('--aggregate',action='store_true');ap.add_argument('dest',type=Path)
    a=ap.parse_args()
    if a.aggregate:print(json.dumps(aggregate(a.world,a.dest.resolve()),ensure_ascii=False))
    elif a.seed is not None:print(json.dumps(one(a.world,a.seed,a.dest.resolve()),ensure_ascii=False))
    else:ap.error('--seedまたは--aggregateが必要')
