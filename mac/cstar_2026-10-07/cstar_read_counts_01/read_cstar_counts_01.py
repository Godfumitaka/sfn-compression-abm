"""完成した種1の照合の記録を一行ずつ集計する。模型を走らせない。"""
from pathlib import Path
from collections import Counter, defaultdict
import gzip, hashlib, json, sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions, now, save

OUT=ROOT/'cstar_full_counts_01.json'
assert not OUT.exists(), '完成した集計を重複して作らない'
assert json.loads((ROOT/'native_full_01/complete.json').read_text())['passed']
path=next((ROOT/'native_full_01/on_own/output/side').rglob('seed001.sme.jsonl.gz'))
safe=conditions()
assert safe['free_bytes'] >= 20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
counts=defaultdict(Counter)
bins=defaultdict(Counter)
examples=defaultdict(list)
records=0
with gzip.open(path,'rt',encoding='utf-8') as stream:
    for line in stream:
        row=json.loads(line)
        if row.get('kind')!='sme_result' or row.get('version')!='sme-cstar-expectation-1':
            continue
        records+=1
        trial=row['trial']
        caller=row['caller']
        key=(trial//100)*100
        c=counts[caller]
        c['computed_records']+=1
        c['retained_candidates']+=row['candidates']
        c['no_candidates']+=row['candidates']==0
        c['hypothesis_count_missing']+=row.get('hypotheses') is None
        bins[key]['computed_records']+=1
        bins[key]['retained_candidates']+=row['candidates']
        left={n['key']:n for n in row['left_nodes']}
        right={n['key']:n for n in row['right_nodes']}
        for a,b in row['new_relation_mapping'].items():
            l,r=left[a],right[b]
            if r['kind']=='unknown':
                c['hidden_pairs']+=1
                continue
            c['visible_pairs']+=1
            state=l['state']
            c['visible_pairs_'+state]+=1
            if not set(l['names']) & set(r['names']):
                c['no_name_overlap_'+state]+=1
                bins[key]['no_name_overlap_'+state]+=1
                if len(examples[caller])<3:
                    examples[caller].append(dict(trial=trial,result=row['result'],state=state,
                        left=l,right=r,probability=row['cstar_probabilities'].get(a),
                        call_kind=row['call_kind']))
        if records%1000==0:
            safe=conditions()
            if safe['free_bytes'] < 18.5*2**30 or safe['swap_grew'] or safe['thermal_warning']:
                save(ROOT/'cstar_full_counts_01_STOP.json',dict(at=now(),resources=safe,completed_records=records))
                raise RuntimeError('読み取りの資源条件により停止')
digest=hashlib.sha256()
with path.open('rb') as stream:
    while block:=stream.read(2**20):
        digest.update(block)
save(OUT,dict(at=now(),source=str(path),source_sha256=digest.hexdigest(),
    passed=True,model_not_run=True,records=records,by_caller=dict(counts),
    by_100_trials=dict(bins),examples=dict(examples),
    meaning='candidatesはSMEの結合・順位・上位3の後に保存した対応候補数。hypothesesは記録に無く生成時の組数は不明。名前の交わりが無い対を集計し、Uの空の名前集合を異名の観察とは断定しない。'))
print(json.dumps(dict(at=now(),records=records,callers=list(counts),output=str(OUT)),ensure_ascii=False))
