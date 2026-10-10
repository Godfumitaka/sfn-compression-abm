"""最初の不一致の一行だけを読む。比較・模型の再実行や除外の追加はしない。"""
import ast
import copy
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import resource
import time

HERE=Path(__file__).resolve().parent
B5=HERE.parents[1]/'instruction12/B5'
roots=[B5/('B5_on200_'+s) for s in ('before','after')]
paths=[root/'output/comm/run001.jsonl' for root in roots]
namespace=dict(copy=copy,json=json,gzip=gzip)
tree=ast.parse((B5/'reference_compare.py').read_text())
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('lines','rows','checked_done')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(B5/'reference_compare.py'),'exec'),namespace)
start=time.perf_counter()
raws=[];normalized=[];fingerprints=[]
for side,(root,path) in enumerate(zip(roots,paths)):
    data=path.read_bytes();fingerprints.append(hashlib.sha256(data).hexdigest())
    verification=json.loads((B5/(root.name+'_verification_01.json')).read_text())
    assert fingerprints[-1]==verification['all_case_files']['output/comm/run001.jsonl']['sha256']
    raw=data.splitlines(keepends=True)[3];raws.append(raw)
    row=json.loads(raw);spec=json.loads((root/'runtime.json').read_text())
    assert row['kind']=='summary'
    row['agents']=[namespace['checked_done'](v,root/'output',spec['commit']) for v in row['agents']]
    normalized.append(row)
    (HERE/f'first_mismatch_side{side}_line4_original.jsonl').write_bytes(raw)
differences=[]
def compare(a,b,path=''):
    if type(a)!=type(b):differences.append(dict(field=path,left=a,right=b));return
    if isinstance(a,dict):
        for key in dict.fromkeys([*a,*b]):
            p=path+'.'+key if path else key
            if key not in a or key not in b:differences.append(dict(field=p,left_present=key in a,right_present=key in b));continue
            compare(a[key],b[key],p)
    elif isinstance(a,list):
        if len(a)!=len(b):differences.append(dict(field=path+'.length',left=len(a),right=len(b)))
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,f'{path}.{i}')
    elif a!=b:differences.append(dict(field=path,left=a,right=b))
compare(*normalized)
proof=[]
for root in roots:
    source=Path(json.loads((root/'runtime.json').read_text())['cwd'])
    ranges={'tools/attnstage2_runtime.py':[(149,166),(198,201)],'tools/v3_run.py':[(646,651)],'tools/v311c.py':[(788,808),(1008,1028)]}
    records={}
    for name,intervals in ranges.items():
        p=source/name;txt=p.read_text().splitlines()
        records[name]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),excerpts=[dict(first_line=a,last_line=b,text='\n'.join(f'{i+1}: {txt[i]}' for i in range(a-1,b))) for a,b in intervals])
    proof.append(dict(root=str(source),files=records))
assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in zip(paths,fingerprints))
result=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),file='comm/run001.jsonl',line=4,first_difference= differences[0] if differences else None,all_remaining_field_differences=differences,source_proof=proof,full_files_sha256=fingerprints,
    original_comparison_stopped=True,comparison_rerun=False,model_rerun=False,new_exclusions_added=False,elapsed_seconds=time.perf_counter()-start,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
with (HERE/'first_mismatch_detail_01.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:result[k] for k in ('file','line','first_difference','all_remaining_field_differences','elapsed_seconds','max_rss_bytes')},ensure_ascii=False))
