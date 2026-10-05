"""確定済みの診断を再出力し、CSVの識別欄以外が変わらないことを照合する。"""
from pathlib import Path
import argparse,csv,hashlib,json
import seal_intervention_batch as batch

REPAIRED={'condition_birth_status','iii_a_added_R','iii_b_added_R'}

def rows(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))

def refresh(world,dest):
    summary=dest/'summary.json';before=json.loads(summary.read_text());checks=[]
    for seed in range(1,21):
        path=dest/f'seed{seed:03d}.cases.csv'
        old=rows(path);old_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        inputs=json.loads((dest/f'seed{seed:03d}.input_before.json').read_text())
        assert batch.fingerprints(batch.ROOTS[world],seed)==inputs
        batch.export(world,seed,dest)
        new=rows(path);assert len(old)==len(new)
        for a,b in zip(old,new):
            assert {k:v for k,v in a.items() if k not in REPAIRED}=={k:v for k,v in b.items() if k not in REPAIRED}
            assert b['condition_birth_status'] in ('適用','未復元')
            assert b['iii_a_added_R']==b['iii_b_added_R']!=''
        checks.append({'seed':seed,'rows':len(new),'before_csv_sha256':old_hash,
                       'after_csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                       'input_files_unchanged':len(inputs),'other_columns_unchanged':True})
    after=batch.aggregate(world,dest)
    assert before==after,'CSVの識別欄の補完で集計が変わった'
    proof={'world':world,'seeds':list(range(1,21)),'repaired_columns':sorted(REPAIRED),
           'raw_diagnostic_records_modified':False,'summary_unchanged':True,'checks':checks}
    (dest/'csv_refresh.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'world':world,'rows':sum(c['rows'] for c in checks),'summary_unchanged':True}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--world',type=int,choices=(1,2),required=True)
    ap.add_argument('dest',type=Path);a=ap.parse_args();refresh(a.world,a.dest.resolve())
