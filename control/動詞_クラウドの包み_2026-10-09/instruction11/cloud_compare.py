"""指示9。同じ機械の完了した二本だけを、retry2と同じ内容全バイトで比べる。"""
from pathlib import Path
import argparse,gzip,hashlib,json,sys
from cloud_run import read,save,complete

def compare(left_case,right_case,destination,limit=100):
    vx,vy=read(left_case/'runtime.json'),read(right_case/'runtime.json')
    sx,sy=read(left_case/'start.json'),read(right_case/'start.json')
    assert sx['machine_sha256']==sy['machine_sha256']
    assert vx['source_commit']==vy['source_commit'] and vx['model_commit']==vy['model_commit'] and vx['observer_sha256']==vy['observer_sha256']
    complete(left_case,limit);complete(right_case,limit)
    if limit==100:
        assert vx['flags']==[f for f in vy['flags'] if f!='--probe-world']
    else:
        assert limit==200
        expected=list(vx['flags'])
        for flag in ('--stage2-speed','--stage2-cache-prune'):
            i=expected.index(flag);assert expected[i+1]=='off';expected[i+1]='on'
        assert expected==vy['flags']
    a,b=left_case/'output',right_case/'output'
    def names(folder):
        return {p.relative_to(folder) for p in folder.rglob('*') if p.is_file()
                and p.relative_to(folder).parts[0] in ('ledgers','side','evictions','attention')
                and p.suffix!='.done' and (limit==200 or not p.name.endswith('.probe.jsonl'))}
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
            'comparison':('内容の全バイト。200は固定試験のprobe.jsonlも含む。100の試験なし／ありではprobeだけ除外。全試行の学習記録と保存状態を含み、試験後も省略しない。stage2の秒を含む診断・gzip容器・時間・manifest・flagは原本を別保存。欄の削除・丸め・再配列なし。')}
    if limit==200:
        probes=[r for r in rows if r['path'].endswith('.probe.jsonl')]
        assert probes and '--probe-world' in vx['flags'] and '--probe-world' in vy['flags'], '200の固定試験の回答がない'
    assert result['file_count']>0
    result.update(completed_trials=limit,source_commit=vx['source_commit'],model_commit=vx['model_commit'],observer_sha256=vx['observer_sha256'],
                  left_case=str(left_case),right_case=str(right_case),machine_sha256=sx['machine_sha256'],
                  finished_epoch=max(read(left_case/'result.json')['finished_epoch'],read(right_case/'result.json')['finished_epoch']))
    save(destination,result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))
    return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('left',type=Path);p.add_argument('right',type=Path);p.add_argument('destination',type=Path);p.add_argument('--limit',type=int,default=100)
    a=p.parse_args();raise SystemExit(compare(a.left.resolve(),a.right.resolve(),a.destination.resolve(),a.limit))
