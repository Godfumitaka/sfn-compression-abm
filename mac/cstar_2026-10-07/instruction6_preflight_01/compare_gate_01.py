"""台帳本体・全side（保存状態を含む）のバイト比較。.doneは存在のみ。"""
from pathlib import Path
import gzip, hashlib, itertools, json, re

def clean_time(line):
    return re.sub(rb', "sec_trial": [-+0-9.eE]+', b'', line)

def inventory(root):
    root=Path(root)
    ledger=list((root/'ledgers').rglob('*'))
    unknown=[str(p.relative_to(root)) for p in ledger if p.is_file() and not (p.name.endswith('.jsonl.gz') or p.suffix=='.done')]
    assert not unknown, '未指定の台帳のファイル：'+str(unknown)
    files={p.relative_to(root) for p in ledger if p.is_file() and p.name.endswith('.jsonl.gz')}
    files.update(p.relative_to(root) for p in (root/'side').rglob('*') if p.is_file())
    markers={p.relative_to(root) for p in ledger if p.is_file() and p.suffix=='.done'}
    assert files and markers, '模型の記録または完了印が無い'
    return files,markers

def read_record(root,rel):
    p=Path(root)/rel
    if rel.parts[0]=='ledgers':
        with gzip.open(p,'rb') as f:
            next(f)
            return b''.join(clean_time(line) for line in f)
    return p.read_bytes()

def difference(a,b,path):
    """比較条件を緩めず、最初の異なる場所を説明する。"""
    compressed=path.name.endswith('.gz')
    if compressed:
        a,b=gzip.decompress(a),gzip.decompress(b)
        if a==b: return {'compressed_bytes_only':True}
    offset=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
    out={'byte_offset':offset,'left_bytes':len(a),'right_bytes':len(b)}
    for line,(x,y) in enumerate(itertools.zip_longest(a.splitlines(),b.splitlines()),1):
        if x==y: continue
        out['line']=line
        try:
            left,right=json.loads(x),json.loads(y)
            def walk(l,r,key=''):
                if type(l)!=type(r): return key,l,r
                if isinstance(l,dict):
                    for k in sorted(set(l)|set(r)):
                        if k not in l or k not in r: return key+'/'+str(k),l.get(k,'<欠落>'),r.get(k,'<欠落>')
                        if l[k]!=r[k]: return walk(l[k],r[k],key+'/'+str(k))
                elif isinstance(l,list):
                    for i,(lv,rv) in enumerate(itertools.zip_longest(l,r,fillvalue='<欠落>')):
                        if lv!=rv:return walk(lv,rv,key+'/'+str(i))
                return key,l,r
            field,lv,rv=walk(left,right)
            out.update(field=field,left=repr(lv)[:600],right=repr(rv)[:600])
            if isinstance(left,dict):
                out['trial']=left.get('trial',left.get('t',left.get('step')))
        except (ValueError,TypeError):
            out.update(left_line=repr(x)[:600],right_line=repr(y)[:600])
        break
    return out

def compare(left,right,output,*,stop_first=False):
    left,right,output=Path(left),Path(right),Path(output)
    lf,lm=inventory(left);rf,rm=inventory(right)
    assert lf==rf, '記録のファイル集合が異なる：'+str(sorted(map(str,lf^rf)))
    assert lm==rm, '完了印の存在が異なる：'+str(sorted(map(str,lm^rm)))
    result={'passed':False,'left':str(left),'right':str(right),
            'exclusions':['台帳の見出し一行','実測sec_trial'],
            'completion_markers_present_both':sorted(map(str,lm)),
            'completion_marker_contents_compared':False,'files':[]}
    for rel in sorted(lf):
        a,b=read_record(left,rel),read_record(right,rel)
        row={'path':str(rel),'bytes_left':len(a),'bytes_right':len(b),
             'left_sha256':hashlib.sha256(a).hexdigest(),'right_sha256':hashlib.sha256(b).hexdigest(),'equal':a==b}
        result['files'].append(row)
        if a!=b:
            row['first_difference']=difference(a,b,rel)
            if stop_first:
                output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                raise RuntimeError('全バイト不一致：'+str(rel)+' '+json.dumps(row['first_difference'],ensure_ascii=False))
    result['passed']=all(row['equal'] for row in result['files'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if not result['passed']:
        bad=[row['path'] for row in result['files'] if not row['equal']]
        raise RuntimeError('全バイト不一致のファイル一覧：'+str(bad))
    return result
