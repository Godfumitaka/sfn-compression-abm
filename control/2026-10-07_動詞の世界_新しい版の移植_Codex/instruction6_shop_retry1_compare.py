"""既存の種1と、台帳・全side・順つき保存状態を内容の全バイトで比べる。"""
from pathlib import Path
import gzip,hashlib,json,sys
root=Path(__file__).resolve().parent
case=root
a,b=root/'shop_baseline/output',root/'shop_candidate_retry1/output'
def names(folder):
    return {p.relative_to(folder) for p in folder.rglob('*') if p.is_file()
            and p.relative_to(folder).parts[0] in ('ledgers','side','evictions','attention')
            and p.suffix!='.done'}
left,right=names(a),names(b)
rows=[]
for rel in sorted(left|right):
    row={'path':str(rel),'left_exists':rel in left,'right_exists':rel in right}
    if rel not in left or rel not in right:
        row.update(equal=False,mismatching_bytes=None)
    else:
        opener=gzip.open if rel.suffix=='.gz' else open
        hs=[hashlib.sha256(),hashlib.sha256()];size=[0,0];n=0;first=None;example=None;bad=0
        with opener(a/rel,'rb') as f,opener(b/rel,'rb') as g:
            while True:
                x,y=f.read(1024*1024),g.read(1024*1024)
                for i,data in enumerate((x,y)):hs[i].update(data);size[i]+=len(data)
                if x!=y:
                    bad+=sum(u!=v for u,v in zip(x,y))+abs(len(x)-len(y))
                    if first is None:
                        p=next((i for i,(u,v) in enumerate(zip(x,y)) if u!=v),min(len(x),len(y)))
                        first=n+p
                        example={'left':x[max(0,p-80):p+160].decode('utf-8','replace'),
                                 'right':y[max(0,p-80):p+160].decode('utf-8','replace')}
                n+=max(len(x),len(y))
                if not x and not y:break
        row.update(equal=first is None,content_bytes=size,left_sha256=hs[0].hexdigest(),right_sha256=hs[1].hexdigest(),
                   mismatching_bytes=bad,first_mismatch_byte=first,example=example)
    rows.append(row)
result={'passed':left==right and all(r['equal'] for r in rows),'file_count':len(rows),
        'mismatching_files':sum(not r['equal'] for r in rows),'files':rows,
        'comparison':'内容の全バイト。gzip容器と非模型の時間・manifest・flagは別の原本として保存。欄の削除・丸め・再配列なし。'}
(case/'shop_retry1_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)
sys.exit(0 if result['passed'] else 1)
