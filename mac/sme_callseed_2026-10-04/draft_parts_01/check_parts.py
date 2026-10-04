"""模型の経路と独立な例で、上限と一意な置換の部品を点検する。"""
from pathlib import Path
from dataclasses import replace
import importlib.util,json,random,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'source/tools'),str(ROOT/'source'),str(ROOT/'draft_light_01')]
import sme2017 as sme
import canonical_reuse as reuse
import strict_bound as upper
spec=importlib.util.spec_from_file_location('fixtures',ROOT/'source/tools/test_sme2017_component.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def rename_pair(a,b):
    names=sorted(set(w for g in (a,b) for n in g.nodes for w in n.names));names={w:f'word{len(names)-i}' for i,w in enumerate(names)}
    out=[];maps=[]
    for side,g in enumerate((a,b)):
        ids={n.key:f'{side}_id{len(g.nodes)-i}' for i,n in enumerate(g.nodes)};maps.append(ids)
        out.append(sme.Graph(tuple(replace(n,key=ids[n.key],names=frozenset(names[w] for w in n.names),args=None if n.args is None else tuple(ids[z] for z in n.args)) for n in reversed(g.nodes))))
    return out,maps
checks=[];reused=0;ties=0;ambiguous=0
for i in range(48):
    rng=random.Random(i)
    a,b=f.fixture('L','A'),f.fixture('R','A' if i%2==0 else 'B')
    gs=[]
    for g in (a,b):
        rows=[]
        for n in g.nodes:
            if n.kind=='relation':
                r=rng.random()
                if r<.16:n=replace(n,state='U',names=frozenset())
                elif r<.30:n=replace(n,state='H',names=n.names|frozenset({'extra'+str(i%3)}))
            rows.append(n)
        gs.append(sme.Graph(tuple(rows)))
    a,b=gs
    matcher=sme.Matcher();result=matcher.match(a,b,tie_seed=i)
    dd=matcher.self_score(a,tie_seed=i);xx=matcher.self_score(b,tie_seed=i)
    support,score,n3=upper.bound(a,b,matcher.settings,dd,xx)
    actual=0 if result.best is None else result.best.score
    assert actual<=score,(i,actual,score)
    for c in result.candidates:
        fh=sum(a.by_id[k].state!='U' and a.by_id[k].kind=='relation' for k,_ in c.relation_mapping)
        assert fh<=support,(i,fh,support)
    changed,maps=rename_pair(a,b);aa,bb=changed;pa=reuse.positions(a,b);pb=reuse.positions(aa,bb)
    if pa is None or pb is None:ambiguous+=1
    else:
        assert pa.code==pb.code
        if not result.choices:
            restored=reuse.relabel(result,pa,pb,aa,bb);sme.validate(aa,bb,restored)
            fresh=sme.Matcher().match(aa,bb,tie_seed=i)
            if not fresh.choices:
                assert restored.best==fresh.best or (restored.best.score==fresh.best.score and restored.best.relation_mapping==fresh.best.relation_mapping and restored.best.entity_mapping==fresh.best.entity_mapping and restored.best.breakdown==fresh.best.breakdown and restored.best.inferences==fresh.best.inferences)
                reused+=1
        else:ties+=1
    checks.append({'case':i,'score':actual,'score_upper':score,'support_upper':support,'ties':bool(result.choices),'unique_positions':pa is not None})
result={'passed':True,'bounds':len(checks),'relabel_comparisons':reused,'not_reused_ties':ties,'not_reused_ambiguous':ambiguous,'connected_to_model':False,'checks':checks}
(ROOT/'draft_light_01/parts_result_01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
