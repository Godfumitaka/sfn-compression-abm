"""X/Yからの変換漏れによる出生ラベルだけを保存記録から修正する。"""
import csv
import json
import resource
import time
from stage1 import ARMS,ROOT,sha

def read(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def write(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    start=time.monotonic();c=0;changed_defs=0;checked_defs=0;before=[]
    for arm in ARMS:
        for seed in range(1,21):
            root=ROOT/'stage2'/arm;bp=root/f'seed{seed:03d}.births.csv';dp=root/f'seed{seed:03d}.definitions.csv'
            b=read(bp);d=read(dp);source={}
            before.extend({'path':str(p),'before_sha256':sha(p)} for p in (bp,dp))
            for row in b:
                original={k:v for k,v in row.items() if k!='door_birth_group'}
                old=row['door_birth_group'];assert old in ('その他の答え','ドア席なし')
                if old=='その他の答え':
                    row['door_birth_group']='共通' if row['world']=='1' else '通常' if row['base_day']=='n' else '例外'
                    c+=1
                assert original=={k:v for k,v in row.items() if k!='door_birth_group'}
                source[row['R'],row['trial']]=row
            for row in d:
                original={k:v for k,v in row.items() if k!='birth_door_group'}
                born=source[row['R'],row['registered_at']]
                if row['birth_door_group']=='その他の答え':
                    origins={x['origin_trial'] for x in json.loads(row['current_door_details'])}
                    assert int(born['base_trial']) in origins,(arm,seed,row['R'],born,origins)
                    checked_defs+=1
                if row['birth_door_group']!=born['door_birth_group']:changed_defs+=1
                row['birth_door_group']=born['door_birth_group']
                assert original=={k:v for k,v in row.items() if k!='birth_door_group'}
            write(bp,b);write(dp,d)
    for row in before:row['after_sha256']=sha(__import__('pathlib').Path(row['path']))
    result={'only_birth_labels_changed':True,'origin_base_checked':True,'birth_label_changes':c,
            'definition_label_changes':changed_defs,'definition_origin_checks':checked_defs,
            'original_model_inputs_not_opened':True,'seconds':time.monotonic()-start,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (ROOT/'birth_label_repair_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'birth_label_repair_files.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
