"""追記の範囲の見積もり用小例。模型の修正は行わない。"""
import csv
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from measure_matcher import graph, prototype, elapsed, sme
import v39
import v310be
from abm.domains import Relation, EdgePrediction, AgentOutput
from abm.accounting import score_prediction


def exact_maps(base, target):
    """この五物の小例だけを全列挙して、名前・順付き引数の整合を確認。"""
    be = [e.entity_id for e in base.entities]
    te = [e.entity_id for e in target.entities]
    target_rows = Counter((r.predicate,r.arguments) for r in target.relations)
    result=[]
    for order in itertools.permutations(te):
        mapping=dict(zip(be,order))
        mapped=Counter((r.predicate,tuple(mapping[a] for a in r.arguments)) for r in base.relations)
        if mapped==target_rows: result.append(mapping)
    return result


def fixture(prefix, variant):
    # 四葉の並行経路。既存名 carry を使う一階の検査用アンカーが内部 a を結ぶ。
    names={x:prefix+x for x in ('u','a','b','v','o')}
    a,b=names['a'],names['b']
    rows=[('p','fold',[names['u'],a]),('r','fold',[names['u'],b]),
          ('cueA','break',[a if variant=='A' else b,names['v']]),
          ('cueB','break_b',[b if variant=='A' else a,names['v']]),
          ('anchor','carry',[names['o'],a]),
          ('other1','lift',[names['v'],names['o']]),
          ('other2','press',[names['o'],names['u']])]
    partial=graph(prefix,list(names.values()),[(prefix+i,p,args) for i,p,args in rows])
    held=Relation(prefix+'hole','hold' if variant=='A' else 'hold_b',(a,names['v']))
    return partial,held


def common_layout(prefix):
    es=[];rs=[];leaves=[]
    for block in range(2):
        u,a,b,v=[f'{prefix}{x}{block}' for x in ('u','a','b','v')]
        es.extend([u,a,b,v])
        for j,args in enumerate([(u,a),(a,v),(u,b),(b,v)]):
            rid=f'{prefix}leaf{block*4+j}';leaves.append(rid)
            rs.append((rid,f'p{block*4+j}',args))
    level=0;layer=leaves
    while len(layer)>1:
        nxt=[]
        for j in range(0,len(layer),2):
            rid=f'{prefix}parent{level}_{j//2}';nxt.append(rid)
            rs.append((rid,f'parent{level}',layer[j:j+2]))
        layer=nxt;level+=1
    return graph(prefix,es,rs)


def main():
    patterns={k:fixture('def'+k,k)[0] for k in ('A','B')}
    scenes={k:fixture('scene'+k,k) for k in ('A','B')}
    matrix={}
    for d in patterns:
        for t,(scene,held) in scenes.items():
            matrix[d+'->'+t]=exact_maps(patterns[d],scene)
    assert len(matrix['A->A'])==len(matrix['B->B'])==1
    assert not matrix['A->B'] and not matrix['B->A']
    assert Counter(r.predicate for r in scenes['A'][0].relations)==Counter(r.predicate for r in scenes['B'][0].relations)
    result={'scope':'高階の役割情報を入力に入れない、一階だけの照合単体検査案。本番世界の生成ではない。',
            'definitions':{k:v.to_dict() for k,v in patterns.items()},
            'scenes':{k:{'visible':g.to_dict(),'expected_held':h.to_dict()} for k,(g,h) in scenes.items()},
            'exact_mapping_matrix':matrix,'same_visible_predicate_counts':True,
            'role_anchor':'carry(o,a) と共有する内部物 a の経路で、break/break_b のどちらが手がかりかを識別する。'}
    (ROOT/'v4_role_fixture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    b,t=common_layout('base'),common_layout('target')
    cases=[('common_layout_full',b,t),('v4_fixture_A',patterns['A'],scenes['A'][0]),('v4_fixture_B',patterns['B'],scenes['B'][0])]
    rows=[]
    for name,left,right in cases:
        old,oldp=elapsed(lambda:sme.map_graphs(left,right),100)
        new,newp=elapsed(lambda:prototype(left,right),100)
        rows.append({'case':name,'base_relations':len(left.relations),'base_entities':len(left.entities),'repeats':100,
                     'current_median_ms':old,'current_p90_ms':oldp,'prototype_median_ms':new,'prototype_p90_ms':newp})
    with (ROOT/'scoped_timings.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

    # 採点の引数順の不一致を、実関数の名前と位置の判定部分で測る。
    # 蓄積先だけをこの小例の写しに替え、通常の状態を作らない。
    calls=[]
    original=v39.rec_add
    v39.rec_add=lambda rec,t,inc: (calls.append(inc) or rec)
    v310be.CTX['L_score']={'fold':7}
    v310be.CTX['R_B_trial']=0
    v310be.STATS.update(score_role_scored=0,score_role_scored_pos_differs=0)
    received=Relation('hole','fold',('a','b'))
    ans={'R':'R','items':[{'slot':0,'gen':1,'st':'F','pos':['b','a'],'cid':'hole','higher':False,
                          'ans':{'F':'fold','H':'fold','U':'fold'}}]}
    try:
        _,scored=v310be.score_answers_role({('R',0):SimpleNamespace(gen=1,state='F')},ans,received,1)
    finally:
        v39.rec_add=original
    output=AgentOutput(prediction=EdgePrediction(Relation('pred','fold',('b','a'))),trace={})
    score=score_prediction(output,received,10)
    order={'oracle_ordered_hit':score.hit,'role_scored':scored,'increment':calls,
           'expected_after_authorized_order_fix':'同じ役割の開示として採点し、順の逆転を誤答として F/H/U の書換費用を7ビットにする。',
           'note':'7 はこの小例の名前の符号長。通常の価格又は新しい係数の指定ではない。'}
    (ROOT/'ordered_arguments_example.json').write_text(json.dumps(order,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'exact_counts':{k:len(v) for k,v in matrix.items()},'order':order,'timings':rows},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
