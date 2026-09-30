import csv,glob,json,sys
from collections import Counter
res=json.load(open('answerseat/345.json'))
arms=dict(λ0='lam000',L25='L25',L50='L50',L75='L75',L90='L90',**{'λ0.15':'lam015','λ0.2':'lam020','λ0.3':'lam030','λ0.5':'lam050','λ0.2_U棄権':'lam020_Uabs','λ0.3_U棄権':'lam030_Uabs'})
def dist(xs):
    xs=sorted(xs)
    if not xs: return '—'
    q=lambda p: xs[min(len(xs)-1,int(p*(len(xs)-1)+0.5))]
    return f"{q(.5)}〔{q(.25)}–{q(.75)}〕{xs[-1]}"
L3=["| 腕 | 全課題 | 伏せた ID が見えている引数に無い | うち答えた | うち外れ | 外れ（全体） | 外れのうち、伏せた ID が無い |","|---|---:|---:|---:|---:|---:|---:|"]
L5=["| 腕 | 42 課題のうち答えた | 当たり | 外れ | 外れ（全体） |","|---|---:|---:|---:|---:|"]
L4=["| 腕 | 答え | F（全答え） | H（全答え） | U（全答え） | 外れ | F（外れ） | H（外れ） | U（外れ） |","|---|---:|---|---|---|---:|---|---|---|"]
for name,d in arms.items():
    root=f'v310BEurta_{d}'
    none={(int(s),t) for s,ts in res[name]['ぶら下がり無しの試行'].items() for t in ts}
    un={(x['seed'],x['trial']) for x in res[name]['未経験_細かい']}
    c=Counter(); c5=Counter()
    for p in glob.glob(f'{root}/side/*/seed*.extrap.csv'):
        for r in csv.DictReader(open(p,encoding='utf-8')):
            k=(int(r['seed']),int(r['trial'])); c['全']+=1; m=r['task']=='外れ'; c['外れ']+=m
            if k in none: c['無']+=1; c['無答']+=r['answered']=='1'; c['無外']+=m
            if k in un: c5['答']+=r['answered']=='1'; c5['当']+=r['task']=='当たり'; c5['外']+=m
    L3.append(f"| {name} | {c['全']:,} | {c['無']:,} | {c['無答']:,} | {c['無外']:,} | {c['外れ']:,} | {c['無外']:,} |")
    L5.append(f"| {name} | {c5['答']} | {c5['当']} | {c5['外']} | {c['外れ']:,} |")
    A=[r for p in glob.glob(f'{root}/side/*/seed*.answers.csv') for r in csv.DictReader(open(p))]
    M=[r for r in A if r['hit']=='0']
    g=lambda rs,k: dist([int(r[k]) for r in rs])
    L4.append(f"| {name} | {len(A):,} | {g(A,'def_F')} | {g(A,'def_H')} | {g(A,'def_U')} | {len(M):,} | {g(M,'def_F')} | {g(M,'def_H')} | {g(M,'def_U')} |")
open('answerseat/表/外れの分母.md','w').write("# 外れの分母での数\n\n## 3\n\n"+"\n".join(L3)+"\n\n## 4-1 答えた課題・外れの課題の、選ばれた定義の席（答えの記録の def_F・def_H・def_U。中央値〔四分位〕最大）\n\n"+"\n".join(L4)+"\n\n## 5\n\n"+"\n".join(L5)+"\n")
print(open('answerseat/表/外れの分母.md').read())
