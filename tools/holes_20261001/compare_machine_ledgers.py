"""二本の既存台帳を読むだけで最初の相違と差の種類を記録する。"""
import argparse, collections, gzip, hashlib, json
from pathlib import Path


def differences(a,b,path='$'):
    if type(a) is not type(b):
        yield {'path':path,'left':a,'right':b,'type_difference':True}; return
    if isinstance(a,dict):
        for k in sorted(a.keys()|b.keys()):
            if k not in a or k not in b:
                yield {'path':f'{path}.{k}','left':a.get(k),'right':b.get(k),'missing':True}
            else:
                yield from differences(a[k],b[k],f'{path}.{k}')
    elif isinstance(a,list):
        if len(a)!=len(b): yield {'path':path+'.length','left':len(a),'right':len(b)}
        for i,(x,y) in enumerate(zip(a,b)):
            yield from differences(x,y,f'{path}[{i}]')
    elif a!=b:
        row={'path':path,'left':a,'right':b}
        if isinstance(a,float): row.update(left_hex=a.hex(),right_hex=b.hex(),absolute_difference=abs(a-b))
        yield row


def compare(left,right):
    counts=collections.Counter(); fields=collections.Counter(); first=None; first_bytes=None
    dl=hashlib.sha256(); dr=hashlib.sha256(); outcomes=collections.Counter()
    with gzip.open(left,'rb') as fl,gzip.open(right,'rb') as fr:
        hl=json.loads(next(fl));hr=json.loads(next(fr))
        assert hl['run_seed']==hr['run_seed'] and 1<=hl['run_seed']<=20
        import itertools
        for i,(ll,rr) in enumerate(itertools.zip_longest(fl,fr)):
            assert ll is not None and rr is not None,'行の数が違う'
            dl.update(ll);dr.update(rr);a=json.loads(ll);b=json.loads(rr);counts['trials']+=1
            if ll!=rr:
                counts['different_bytes']+=1
                if first_bytes is None:
                    offset=next((j for j,(x,y) in enumerate(zip(ll,rr)) if x!=y), min(len(ll),len(rr)))
                    first_bytes={'index_zero_based':i,'trial_display':i+1,'byte_offset':offset,
                                 'left_length':len(ll),'right_length':len(rr),
                                 'left_excerpt':ll[max(0,offset-70):offset+100].decode('utf-8',errors='replace'),
                                 'right_excerpt':rr[max(0,offset-70):offset+100].decode('utf-8',errors='replace'),
                                 'json_contents_equal':a==b}
            if a!=b:
                counts['different_json']+=1
                for k in a.keys()|b.keys():
                    if a.get(k)!=b.get(k):fields[k]+=1
                if first is None:
                    import itertools
                    first={'index_zero_based':i,'trial_display':i+1,'differences':list(itertools.islice(differences(a,b),80)),'left_row':a,'right_row':b}
            if a.get('agent_state_snapshot_hash')!=b.get('agent_state_snapshot_hash'):counts['different_state_hash']+=1
            if a.get('outcome_category')!=b.get('outcome_category'):counts['different_outcome']+=1
            outcomes[(a.get('outcome_category'),b.get('outcome_category'))]+=1
    return {'left':str(left),'right':str(right),'left_header':hl,'right_header':hr,
            'header_differences':list(differences(hl,hr)),'left_body_sha':dl.hexdigest(),'right_body_sha':dr.hexdigest(),
            'counts':dict(counts),'different_fields':dict(fields),'outcome_pairs':[[*k,v] for k,v in outcomes.items()],
            'first_bytes_difference':first_bytes,'first_difference':first}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('left',type=Path);p.add_argument('right',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    assert not args.output.exists()
    result=compare(args.left,args.right);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('first_difference','left_header','right_header','header_differences')},ensure_ascii=False))
    if result['first_difference']:print(json.dumps({k:v for k,v in result['first_difference'].items() if k not in ('left_row','right_row')},ensure_ascii=False))
