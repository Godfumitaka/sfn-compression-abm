import math,json,gzip
from pathlib import Path
root=Path(__file__).resolve().parent.parent

def plain(v):
 if not isinstance(v,dict):return v
 tag=v['tag']
 if tag=='dataclass':return {k:plain(x) for k,x in v['fields'].items()}
 if tag=='enum':return v['value']
 if tag=='mapping':return {plain(k):plain(x) for k,x in v['items']}
 if tag in ('tuple','list','set','frozenset'):return tuple(plain(x) for x in v['items'])
 raise ValueError(tag)

facts=[]
for folder in ('stage3_learning_02','stage3_learning_03'):
 for p in sorted((root/folder).glob('*/side/*/*.sme.states.jsonl.gz')):
  with gzip.open(p,'rt') as f:packets=[json.loads(s) for s in f]
  posts={x['trial']:plain(x['state']) for x in packets if x['kind']=='post'}
  side=p.with_name(p.name.split('.')[0]+'.jsonl')
  records=[json.loads(x) for x in side.read_text().splitlines()]
  births={x['trial']:x for x in records if x.get('kind')=='birth'}
  ne=nb=nr=0; skipped_birth=0; examples=[]
  for v in records:
   t=v.get('trial')
   if v.get('kind')=='v310be' and v.get('reg') is not None:
    chosen=next(c for c in v['cands'] if c[0]==v['chosen'])
    assert abs(v['K']-(chosen[1]+v['r']+v['lam']*v['dC_pred'])) < 0.0000011,(p,t,'K')
    assert v['dC_pred']==v['dC_real'],(p,t,'dC')
    ne+=1
    if v['chosen'] is not None and not any(x.get('kind')=='assim' for x in examples):examples.append({'kind':'assim','trial':t,'A_rounded':chosen[1],'r':v['r'],'lambda':v['lam'],'dC':v['dC_real'],'K':v['K'],'hist_inc':v.get('hist_inc')})
   if v.get('kind')=='v39' and t in births:
    birth=births[t];age=t-birth['base_written_at'];post=posts[t]
    for row in (v.get('m1') or {}).get('births_rec',[]):
     details=row.get('ordered_arguments')
     if details is None:raise ValueError((p,t,'初期の順つき記録が無い'))
     rec=post['v39_seats'].get((birth['R'],row['slot']))
     if rec is None or rec['state']=='U' or rec['gen']!=0:
      skipped_birth+=1;continue
     decay=[math.exp(-1/(0.3*(1740*3/0.3)**(i/15)))**age for i in range(16)]
     expected=tuple(tuple(w*a+b for w in decay) for a,b in zip(details['r_old'],details['r_current']))
     if rec['state']=='H':expected=((0.0,)*16,)+expected[1:]
     assert all(abs(a-b)<1e-10 for ac,bc in zip(expected,rec['init']) for a,b in zip(ac,bc)),(p,t,row['slot'],'誕生の初期')
     nb+=1
     if not any(x.get('kind')=='birth' for x in examples):examples.append({'kind':'birth','trial':t,'slot':row['slot'],'age':age,'old':details['r_old'],'current':details['r_current'],'first_tau':0.3,'first_column_expected':[c[0] for c in expected],'first_column_actual':[c[0] for c in rec['init']]})
   if v.get('kind')=='relearn_init' and not v.get('skipped'):
    rec=posts[t]['v39_seats'].get((v['R'],v['slot']))
    if rec is not None and rec['state']=='H' and rec['gen']==v['gen']:
     assert rec['init']==((0.0,)*16,(v['r_H'],)*16,(v['r_U'],)*16,(1.0,)*16),(p,t,'覚え直し初期')
     nr+=1
     if not any(x.get('kind')=='relearn' for x in examples):examples.append({'kind':'relearn','trial':t,'H':v['H'],'U':v['U'],'r_H':v['r_H'],'r_U':v['r_U'],'init_columns':[c[0] for c in rec['init']]})
  facts.append({'run':p.parents[2].name,'folder':folder,'E_checked':ne,'birth_seats_checked':nb,'birth_seats_already_U_or_removed':skipped_birth,'relearn_checked':nr,'examples':examples})
out=Path(__file__).resolve().parent/'learning_arithmetic.json';out.write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'runs':len(facts),'E':sum(x['E_checked'] for x in facts),'birth':sum(x['birth_seats_checked'] for x in facts),'relearn':sum(x['relearn_checked'] for x in facts)},ensure_ascii=False))
