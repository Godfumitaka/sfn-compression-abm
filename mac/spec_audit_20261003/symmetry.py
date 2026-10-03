import csv,gzip,json,statistics,math
from pathlib import Path
from collections import Counter
R=Path(__file__).parent; RES=R.parent/'codex_worldv4_2026-10-01/results'
O=R/'analysis';O.mkdir(exist_ok=True)
SUM=[]; SEED=[]; META=[]
def pct(xs,p):
    xs=sorted(xs); k=(len(xs)-1)*p; a=math.floor(k);b=math.ceil(k);return xs[a]+(xs[b]-xs[a])*(k-a)
def compare(arm,kind,filter_fn,group_col,groups):
    base=RES/arm
    with gzip.open(base/'trials.tsv.gz','rt') as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
    assert len(rows)==34800 and {int(x['seed']) for x in rows}==set(range(1,21))
    assert all(0<=int(x['trial'])<1740 for x in rows)
    codes=sorted({json.loads(x).get('code_commit') for x in (base/'sha256.jsonl').read_text().splitlines()})
    flags=json.loads((base/'flag.json').read_text()); META.append({'arm':arm,'code':codes,'flags':flags})
    sel=[x for x in rows if filter_fn(x)]
    tot={g:Counter(x['outcome'] for x in sel if x[group_col]==g) for g in groups}
    for outcome in ['w','a','c']:
        diffs=[]
        for seed in range(1,21):
            cc={g:Counter(x['outcome'] for x in sel if x[group_col]==g and int(x['seed'])==seed) for g in groups}
            ns=[sum(cc[g].values()) for g in groups]; rates=[cc[g][outcome]/n if n else None for g,n in zip(groups,ns)]
            diff=100*(rates[0]-rates[1]) if None not in rates else None
            SEED.append({'arm':arm,'kind':kind,'outcome':outcome,'seed':seed,'group0':groups[0],'group1':groups[1],'n0':ns[0],'count0':cc[groups[0]][outcome],'n1':ns[1],'count1':cc[groups[1]][outcome],'difference_pp':diff})
            if diff is not None:diffs.append(diff)
        ns=[sum(tot[g].values()) for g in groups]
        SUM.append({'arm':arm,'kind':kind,'outcome':outcome,'group0':groups[0],'group1':groups[1],'n0':ns[0],'count0':tot[groups[0]][outcome],'n1':ns[1],'count1':tot[groups[1]][outcome],'pooled_diff_pp':100*(tot[groups[0]][outcome]/ns[0]-tot[groups[1]][outcome]/ns[1]),'paired_mean_pp':statistics.mean(diffs),'paired_sd_pp':statistics.stdev(diffs),'p025_pp':pct(diffs,.025),'p25_pp':pct(diffs,.25),'median_pp':pct(diffs,.5),'p75_pp':pct(diffs,.75),'p975_pp':pct(diffs,.975),'min_pp':min(diffs),'max_pp':max(diffs),'positive_seeds':sum(x>0 for x in diffs),'negative_seeds':sum(x<0 for x in diffs),'zero_seeds':sum(x==0 for x in diffs)})
for rule in ['A','C']:
 for lam in ['L50','L90']:
  arm=f'ataru-0608/f_grid/fg_f050_{rule}_{lam}'
  for kind,fn in [('全課題',lambda x:True),('ドア全体',lambda x:x['door']=='1'),('ドア通常',lambda x:x['door']=='1' and x['shop_cue']=='n'),('ドア例外',lambda x:x['door']=='1' and x['shop_cue']=='e')]:compare(arm,kind,fn,'shop_type',['甲','乙'])
  compare(f'ataru-0608/n3/now_w1_{rule}_{lam}','世界1ドア',lambda x:x['door']=='1','shop_cue',['e','n'])
for lam in ['L50','L90']:
 for dp in ['none','0.3','0.5']:
  compare(f'ataru-0608/c_grid/cg_C_{lam}_e0.5_d{dp}','例外割合0.5ドア',lambda x:x['door']=='1','shop_cue',['e','n'])
for name,rows in [('symmetry_summary',SUM),('symmetry_by_seed',SEED)]:
 with (O/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(O/'symmetry_inputs.json').write_text(json.dumps(META,ensure_ascii=False,indent=2)+'\n')
print('集計',len(SUM),'行、種別',len(SEED),'行')
for x in SUM:
 if x['kind'] in ['ドア全体','世界1ドア','例外割合0.5ドア'] and x['outcome']!='c': print(x)
