"""新関門の材料を既存の腕Rの読み手に渡し、表示とCSVを補う。"""
from pathlib import Path
import argparse,csv,gzip,json,subprocess,sys
import seal_mac_intervention as mac
import seal_intervention_batch as batch

ROOT=Path(__file__).resolve().parents[2]
EX=ROOT.parent/'codex_explore3_2026-10-04/source'

def one(root,dest,seed):
    if seed not in range(1,21):raise ValueError('種は1〜20だけ')
    mac.gate(root,seed);before=batch.fingerprints(root,seed)
    dest.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(EX/'tools'),str(EX)]
    import explore3_rdiag as rdiag
    result=rdiag.one(root,seed,dest)
    if before!=batch.fingerprints(root,seed):raise RuntimeError('腕Rで入力の指紋が変わった')
    rows=[];flags=json.loads((root/'flag.json').read_text())
    with gzip.open(dest/f'seed{seed:03d}.rdiag.jsonl.gz','rt') as stream:
        for raw in stream:
            rec=json.loads(raw)
            row={'arm':root.name,'world':flags['shop_world'],'seed':seed,'trial':rec['trial'],'day':rec['cue'],'material':mac.LABEL}
            for rule,key in [('今の規則','current'),('N3','N3'),('r','r')]:
                ans=rec['answers'][rule]
                row.update({key+'_R':ans['R'],key+'_outcome':ans['outcome'],key+'_classification':ans['classification']})
            rows.append(row)
    with (dest/f'seed{seed:03d}.cases.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    check={'seed':seed,'rows':len(rows),'input_files_unchanged':before,'material':mac.LABEL,
           'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=EX,text=True).strip()}
    mac.write_json(dest/f'seed{seed:03d}.mac_check.json',check)
    return result

def aggregate(root,dest):
    rows=[];code_versions=set()
    for seed in range(1,21):
        check=json.loads((dest/f'seed{seed:03d}.mac_check.json').read_text())
        code_versions.add(check['source_commit'])
        if check['input_files_unchanged']!=batch.fingerprints(root,seed):raise RuntimeError('腕R集計で入力指紋が不一致')
        with (dest/f'seed{seed:03d}.cases.csv').open(newline='') as stream:rows.extend(csv.DictReader(stream))
    sys.path[:0]=[str(EX/'tools'),str(EX)]
    import explore3_rdiag as rdiag
    rdiag.tables(dest,root.name)
    data=json.loads((dest/'summary.json').read_text());data.update(material=mac.LABEL,input_files_unchanged=True,original_body_status='未照合',source_commits=sorted(code_versions))
    with (dest/'all_doors.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    mac.write_json(dest/'summary.json',data);return data

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',type=Path);ap.add_argument('dest',type=Path)
    ap.add_argument('--seed',type=int);ap.add_argument('--aggregate',action='store_true');a=ap.parse_args()
    result=aggregate(a.root.resolve(),a.dest.resolve()) if a.aggregate else one(a.root.resolve(),a.dest.resolve(),a.seed)
    print(json.dumps(result,ensure_ascii=False),flush=True)
