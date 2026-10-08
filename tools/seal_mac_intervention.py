"""承認済みのマック材料を読むだけで、全ドアの介入をCSVへ出す。"""
from pathlib import Path
from collections import Counter
import argparse,csv,gzip,json,subprocess,time
import seal_intervention_diag as diag
import seal_intervention_batch as batch

LABEL='マックでの作り直し（試行表は元と一致、台帳本体は未照合）'

def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def gate(root,seed):
    proof=json.loads((root/f'seed{seed:03d}.mac_gate.json').read_text())
    if not (proof['seed']==seed and proof['table_match'] and proof['internal_state_match']
            and proof['internal_state_trials']==proof['trials']==1740):
        raise RuntimeError('新しい二関門を通っていない材料')
    if proof.get('input_fingerprints')!=batch.fingerprints(root,seed):raise RuntimeError('関門通過後に材料の指紋が変わった')
    return proof

def one(root,dest,seed):
    if seed not in diag.SEEDS:raise ValueError('種は1〜20だけ')
    proof=gate(root,seed);before=batch.fingerprints(root,seed);start=time.time()
    dest.mkdir(parents=True,exist_ok=True)
    write_json(dest/f'seed{seed:03d}.input_before.json',before)
    result=diag.one(root,dest,seed,all_doors=True)
    if before!=batch.fingerprints(root,seed):raise RuntimeError('入力材料の指紋が変わった')
    rows=[]
    with gzip.open(dest/f'seed{seed:03d}.interventions.jsonl.gz','rt') as stream:
        for raw in stream:
            row=batch.flatten(json.loads(raw))
            row.update(arm=root.name,material=LABEL)
            rows.append(row)
    if len({(r['world'],r['seed'],r['trial']) for r in rows})!=len(rows):raise RuntimeError('CSVの鍵が重複')
    checks=result['checks']
    if not (len(rows)==result['counts']['door_cases']==checks['prediction_reproduced']==checks['original_state_unchanged']):
        raise RuntimeError('元の予測・状態保持・CSV件数の不一致')
    with (dest/f'seed{seed:03d}.cases.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    check={'seed':seed,'rows':len(rows),'input_files_unchanged':len(before),'material':LABEL,
           'gate':proof,'seconds':round(time.time()-start,3)}
    write_json(dest/f'seed{seed:03d}.mac_check.json',check)
    return check

def aggregate(root,dest):
    flags=json.loads((root/'flag.json').read_text());rows=[];inputs={};checks=[]
    for seed in diag.SEEDS:
        gate(root,seed)
        check=json.loads((dest/f'seed{seed:03d}.mac_check.json').read_text())
        if check['seed']!=seed or not check['input_files_unchanged']:raise RuntimeError('入力保持の検証が無い')
        checks.append(check)
        before=json.loads((dest/f'seed{seed:03d}.input_before.json').read_text())
        if before!=batch.fingerprints(root,seed):raise RuntimeError('解析後に入力が変わった')
        inputs.update(before)
        with (dest/f'seed{seed:03d}.cases.csv').open(newline='') as stream:rows.extend(csv.DictReader(stream))
    data=diag.aggregate(dest,root.name)
    data.update(material=LABEL,original_body_status='未照合',world=flags['shop_world'],lambda_=flags['v39_price'],
                mode='D' if '_D_' in root.name else 'C' if flags.get('cf_learn') else 'A',
                selector='N3' if flags.get('select_n3') else 'current',input_files_unchanged=True,
                all_door_rows=len(rows),all_seeds_passed=True)
    data['code_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=diag.W,text=True).strip()
    if len(rows)!=data['counts']['door_cases'] or len({(r['seed'],r['trial']) for r in rows})!=len(rows):
        raise RuntimeError('全種CSVの件数・鍵が一致しない')
    groups=[('all_doors.csv',rows),('exception_wrong.csv',[r for r in rows if r['day']=='e' and r['baseline_outcome']=='外れ'])]
    for name,subset in groups:
        with (dest/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(subset)
    gates=[gate(root,seed) for seed in diag.SEEDS]
    with (dest/'material_gates.csv').open('w',newline='') as stream:
        keys=['arm','seed','trials','table_match','different_table_rows','table_sha256','reference_table_sha256',
              'internal_state_match','internal_state_trials','body_sha256','original_body_status','material_label']
        writer=csv.DictWriter(stream,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(gates)
    with (dest/'input_sha256.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','bytes','sha256']);writer.writeheader()
        writer.writerows({'path':p,**value} for p,value in sorted(inputs.items()))
    write_json(dest/'mac_checks.json',checks);write_json(dest/'summary.json',data)
    return data

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',type=Path);ap.add_argument('dest',type=Path)
    ap.add_argument('--seed',type=int);ap.add_argument('--aggregate',action='store_true');a=ap.parse_args()
    result=aggregate(a.root.resolve(),a.dest.resolve()) if a.aggregate else one(a.root.resolve(),a.dest.resolve(),a.seed)
    print(json.dumps(result,ensure_ascii=False),flush=True)
