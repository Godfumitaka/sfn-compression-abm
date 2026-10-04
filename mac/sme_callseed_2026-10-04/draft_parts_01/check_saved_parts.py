"""完了した13小走行の保存された入力・結果で、未接続の部品だけを確認する。"""
from pathlib import Path
from dataclasses import fields
from collections import OrderedDict
import gzip,json,sys,time
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'source/tools'),str(ROOT/'source'),str(ROOT/'draft_light_01')]
import sme2017 as sme
import canonical_reuse as reuse
import strict_bound as upper
TYPES={n:getattr(sme,n) for n in ('Settings','Node','Graph','Hypothesis','Candidate','Result')}
def decode(x):
    if not isinstance(x,dict):return x
    if x['tag'] in ('tuple','list','set','frozenset'):
        return {'tuple':tuple,'list':list,'set':set,'frozenset':frozenset}[x['tag']](decode(y) for y in x['items'])
    assert x['tag']=='dataclass' and x['module']=='sme2017' and x['name'] in TYPES
    cls=TYPES[x['name']]
    assert set(x['fields'])=={f.name for f in fields(cls)}
    return cls(**{k:decode(v) for k,v in x['fields'].items()})
def records(p):
    with gzip.open(p,'rt') as stream:
        for line in stream:yield json.loads(line)
def logical(c):
    if c is None:return None
    return {k:getattr(c,k) for k in ('score','initial_score','relation_mapping','entity_mapping','match_kinds','breakdown','inferences')}
plan=json.loads((ROOT/'small_extra_plan_01.json').read_text());unique=list(dict.fromkeys(r['folder'] for r in plan))
cache=OrderedDict();checks=hits=ties=ambiguous=literal_same=0;details=[];started=time.perf_counter()
for folder in unique:
    p=Path(folder)/'saved_matcher.jsonl.gz';graphs={}
    for row in records(p):
        if row['section']=='graphs':g=decode(row['value']);graphs[g.fingerprint()]=g
    counts={'case':Path(folder).name,'checks':0,'hits':0,'ties':0,'ambiguous':0}
    for row in records(p):
        if row['section']!='cache':continue
        result=decode(row['value'])
        if result.left_fingerprint not in graphs or result.right_fingerprint not in graphs:continue
        left,right=graphs[result.left_fingerprint],graphs[result.right_fingerprint]
        support,score,_=upper.bound(left,right,result.settings,1.,1.)
        for candidate in result.candidates:
            actual=sum(left.by_id[a].kind=='relation' and left.by_id[a].state!='U' for a,b in candidate.relation_mapping)
            assert candidate.score<=score,('点の上限を超えた',folder,candidate.score,score)
            assert actual<=support,('支持の上限を超えた',folder,actual,support)
        checks+=1;counts['checks']+=1
        if result.choices:ties+=1;counts['ties']+=1;continue
        pos=reuse.positions(left,right)
        if pos is None:ambiguous+=1;counts['ambiguous']+=1;continue
        key=(result.version,result.settings,pos.code)
        if key in cache:
            old_result,old_pos=cache.pop(key)
            restored=reuse.relabel(old_result,old_pos,pos,left,right);sme.validate(left,right,restored)
            assert logical(restored.best)==logical(result.best),('再利用した第一位が違う',folder,logical(restored.best),logical(result.best))
            hits+=1;counts['hits']+=1
            literal_same+=int(old_result.left_fingerprint==result.left_fingerprint and old_result.right_fingerprint==result.right_fingerprint)
        cache[key]=(result,pos)
        if len(cache)>512:cache.popitem(last=False)
    details.append(counts)
summary={'passed':True,'connected_to_model':False,'small_cases':len(plan),'distinct_completed_outputs':len(unique),'cached_results_checked':checks,'all_candidate_scores_and_support_below_upper':True,'canonical_relabel_comparisons':hits,'of_relabels_with_same_literal_input':literal_same,'excluded_actual_ties':ties,'excluded_nonunique_positions':ambiguous,'reuse_cache_limit':512,'elapsed_seconds':time.perf_counter()-started,'cases':details}
out=ROOT/'draft_light_01/saved_parts_result_01.json';assert not out.exists();out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
