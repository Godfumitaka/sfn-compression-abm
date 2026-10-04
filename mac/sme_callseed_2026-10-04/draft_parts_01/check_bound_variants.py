"""未知・関数・繰返し引数のある小さなDAGで、上限を独立に点検。未接続。"""
from pathlib import Path
from dataclasses import replace
import json,random,sys,time
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'source/tools'),str(ROOT/'source'),str(ROOT/'draft_light_01')]
import sme2017 as sme
import strict_bound as upper
checks=[];started=time.perf_counter()
def make(side,seed):
    rng=random.Random(seed);rows=[sme.Node(side+str(i),'entity') for i in range(4)]
    for j in range(5):
        kind=rng.choice(['relation','relation','function','attribute']);state=rng.choice(['F','F','H','U'])
        names=frozenset() if state=='U' else frozenset({rng.choice(['p','q','s'])})
        if state=='H' and rng.random()<.4:names|=frozenset({rng.choice(['p','q','s'])})
        # DAG。親の引数に同じ子を二回置く場合を含む。
        args=tuple(rng.choice(rows).key for _ in range(rng.choice([1,2])))
        rows.append(sme.Node(side+str(j+4),kind,names,args,state,rng.random()<.12))
    if rng.random()<.3:
        old=rows[4];rows[4]=sme.Node(old.key,'unknown',args=None)
    return sme.Graph(tuple(rows))
for case in range(80):
    left,right=make('L',case),make('R',case if case%2 else case+11)
    matcher=sme.Matcher();result=matcher.match(left,right,tie_seed=case)
    dd=matcher.self_score(left,tie_seed=case);xx=matcher.self_score(right,tie_seed=case)
    support,score,n3=upper.bound(left,right,matcher.settings,dd,xx)
    for c in result.candidates:
        assert c.score<=score,(case,c.score,score)
        actual=sum(left.by_id[a].kind=='relation' and left.by_id[a].state!='U' for a,b in c.relation_mapping)
        assert actual<=support,(case,actual,support)
    checks.append({'case':case,'actual':result.best.score if result.best else 0.,'upper':score,'support_upper':support,'choices':bool(result.choices)})
out={'passed':True,'connected_to_model':False,'cases':len(checks),'covered':['unknown','F','H','U','function','attribute','ubiquitous','repeated_arguments','shared_DAG_children'],'elapsed_seconds':time.perf_counter()-started,'checks':checks}
p=ROOT/'draft_light_01/bound_variants_result_01.json';assert not p.exists();p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='checks'},ensure_ascii=False))
