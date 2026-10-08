import csv, random, sys, collections
rows=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')))
cfgs=sorted(set(r['config'] for r in rows)); print('configs',cfgs, 'seeds', sorted(set(int(r['seed']) for r in rows))[:3],'...', len(set(r['seed'] for r in rows)))
idx={}
for r in rows: idx[(r['config'],r['world'],r['scope'],r['day'],int(r['seed']))]=r
metrics=['selection_error','absent','distinction_loss','wrong','silent','correct']
pairs=[(c,'A_L50') for c in cfgs if c!='A_L50']+[('A_L50','A_zero')]
combos=sorted(set((r['world'],r['scope'],r['day']) for r in rows))
def ratio(num,den,w,s,d,m,seeds):
    nn=sum(float(idx[(num,w,s,d,k)][m]) for k in seeds); nt=sum(float(idx[(num,w,s,d,k)]['tasks']) for k in seeds)
    dn=sum(float(idx[(den,w,s,d,k)][m]) for k in seeds); dt=sum(float(idx[(den,w,s,d,k)]['tasks']) for k in seeds)
    if dn==0 or dt==0 or nt==0: return None
    return (nn/nt)/(dn/dt)
def judge(num,den,w,s,d,m,seeds,B=2000,rs=20261007):
    rng=random.Random(rs); r0=ratio(num,den,w,s,d,m,seeds)
    if r0 is None: return 'NA',None,None,None
    bs=[]
    for _ in range(B):
        smp=[rng.choice(seeds) for _ in seeds]; x=ratio(num,den,w,s,d,m,smp)
        if x is not None: bs.append(x)
    if len(bs)<B*0.9: return 'NA',r0,None,None
    bs.sort(); lo=bs[int(0.025*len(bs))]; hi=bs[int(0.975*len(bs))-1]
    j='>1' if lo>1 else ('<1' if hi<1 else 'またぐ')
    return j,r0,lo,hi
tab=collections.Counter(); widths=[]
ex=[]
for num,den in pairs:
  for (w,s,d) in combos:
    if any((c,w,s,d,k) not in idx for c in (num,den) for k in range(1,21)): continue
    for m in metrics:
      j20,r20,l20,h20=judge(num,den,w,s,d,m,list(range(1,21)))
      j10,r10,l10,h10=judge(num,den,w,s,d,m,list(range(1,11)))
      if j20=='NA' or j10=='NA': tab[('NA',)]+=1; continue
      tab[(j20,j10)]+=1
      import math
      if l20>0 and l10>0: widths.append(math.log(h10/l10)/math.log(h20/l20) if h20>l20 else None)
      if j20!=j10: ex.append((num,den,w,s,d,m,j20,round(r20,3),j10,round(r10,3),round(l10,3),round(h10,3)))
print('20本の判定 → 10本の判定 : 件数')
for k,v in sorted(tab.items()): print(k,v)
ws=[x for x in widths if x]; ws.sort(); print('CI幅（対数）の比 10本/20本 の中央値', round(ws[len(ws)//2],2), 'n',len(ws))
print('食い違いの例:'); [print(e) for e in ex[:40]]
