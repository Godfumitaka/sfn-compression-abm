"""元の関数と返り値の型・文字列を比較。期待値を新しい関数で作らない。"""
from pathlib import Path
import importlib.util,json,random,sys,time,itertools
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));from verify_corpus import old,new,key
cases=[]
for n in (0,1,2,4,6):
    labels=[('same',)]*n
    cases.append((labels,[(i,(i+1)%n,'edge') for i in range(n)] if n else []))
for n in (3,4,5,6):
    cases.append(([('center',)]+[('leaf',)]*n,[(0,i+1,'leaf') for i in range(n)]))
# 文字列のエスケープ、多重辺、辺の色が文字列以外、複合した初期の色。
cases.extend([([('"\\\n\u0000😀',),('日本語',)],[(0,1,'"\\\n\u0000😀')]),
              ([('x',)]*3,[(0,1,'p'),(0,1,'p'),(1,2,'p')]),
              ([{'x':[True,None,1.25]},['x',-10]],[(0,1,7)]),
              ([('x',)]*3,[(0,1,None),(1,2,None)]),
              ([('x',)]*3,[(0,1,[1]),(1,2,[1])]),
              ([('x',)]*3,[(0,1,{'x':1}),(1,2,{'x':1})]),
              (list(range(15)),[(0,i,'p') for i in range(1,15)])])
r=random.Random(103104);checks=0;t=time.perf_counter()
for labels,edges in cases:
    a,b=old._canonical(labels,edges),new._canonical(labels,edges)
    assert type(a) is type(b) is str and a==b,(labels,edges,a,b);checks+=1
    if len(labels)>1:
        for _ in range(3):
            order=list(range(len(labels)));r.shuffle(order);at={i:j for j,i in enumerate(order)}
            ls=[labels[i] for i in order];es=[(at[a],at[b],p) for a,b,p in edges];r.shuffle(es)
            x,y=old._canonical(ls,es),new._canonical(ls,es);assert type(x) is type(y) is str and x==y;checks+=1
# 小さな有向図を全列挙。空、自己参照、対称な図を含む（模型へ渡さない）。
for bits in range(2**9):
    labels=[('x',)]*3;edges=[(i,j,'p') for i in range(3) for j in range(3) if bits&(1<<(3*i+j))]
    a,b=old._canonical(labels,edges),new._canonical(labels,edges);assert type(a) is type(b) is str and a==b,(bits,a,b);checks+=1
# 多桁の色、同じ引数への参照、Unicodeの辺を含む。これは部品用の乱数である。
for _ in range(120):
    n=r.randrange(1,18);labels=[(r.randrange(4),'色'+str(r.randrange(3))) for i in range(n)]
    edges=[(r.randrange(n),r.randrange(n),r.choice(('arg0','arg1','allows','"\\\n\u0000😀'))) for _ in range(r.randrange(0,3*n))]
    a,b=old._canonical(labels,edges),new._canonical(labels,edges);assert type(a) is type(b) is str and a==b;checks+=1
# 元が受け入れる一回きりの辺の反復子も、返り値を変えない。
labels=[('a',),('b',)];es=[(0,1,'p')]
a,b=old._canonical(labels,iter(es)),new._canonical(labels,iter(es));assert type(a) is type(b) is str and a==b;checks+=1
result={'passed':True,'checks':checks,'seconds':time.perf_counter()-t,'scope':'対称の図・全512小図・多桁の色・Unicode・非文字列の辺・反復子。元の返り値と型を比較'}
(ROOT/'design_01/pure_component_03.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
