"""指示15の固定試験行だけを除く承認済み比較。原出力と原比較は書き換えない。"""
from pathlib import Path
from random import Random
from collections import Counter
from datetime import datetime
import argparse,gzip,hashlib,json

def sha(value):return hashlib.sha256(value).hexdigest()
def encoded_rng(value):
    if isinstance(value,tuple):return {'tag':'tuple','items':[encoded_rng(x) for x in value]}
    return value
def rng_key(value):
    return sha(json.dumps(value,sort_keys=True,separators=(',',':')).encode())
def state_compare(left,right,probe_file,seed):
    probes=[json.loads(x) for x in probe_file.read_text().splitlines()]
    assert len(probes)==48 and {x['t'] for x in probes}=={100}
    expected={}
    for qi,row in enumerate(probes):
        key=rng_key(encoded_rng(Random(int.from_bytes(hashlib.sha256(f"probe\x1f{seed}\x1f{row['t']}\x1f{qi}".encode()).digest()[:8],'big')).getstate()))
        assert key not in expected
        expected[key]={'probe_t':row['t'],'question_index':qi}
    seen=Counter();excluded=[];counts=Counter();hashes=[hashlib.sha256(),hashlib.sha256()]
    raw_hashes=[hashlib.sha256(),hashlib.sha256()];sizes=[0,0];raw_sizes=[0,0];bad=0;first=None
    with gzip.open(left,'rb') as f,gzip.open(right,'rb') as g:
        it=iter(enumerate(g,1));kept=0
        for number,line in it:
            row=json.loads(line);raw_hashes[1].update(line);raw_sizes[1]+=len(line)
            match=expected.get(rng_key(row['rng'])) if row['kind']=='pre' else None
            if match is not None:
                n,line2=next(it);prediction=json.loads(line2)
                assert prediction['kind']=='prediction' and prediction['trial']==row['trial']
                raw_hashes[1].update(line2);raw_sizes[1]+=len(line2)
                seen[match['question_index']]+=1
                excluded.append(dict(match,trial=row['trial'],pre_line=number,prediction_line=n,pre_sha256=sha(line),prediction_sha256=sha(line2)))
                continue
            baseline=next(f,None);kept+=1
            if baseline is not None:
                base=json.loads(baseline)
                assert not (base['kind']=='pre' and rng_key(base['rng']) in expected),'試験なし側に試験鍵が混入'
                hashes[0].update(baseline);sizes[0]+=len(baseline);raw_hashes[0].update(baseline);raw_sizes[0]+=len(baseline)
            hashes[1].update(line);sizes[1]+=len(line)
            if baseline!=line:
                bad+=1
                if first is None:first={'kept_line':kept,'original_right_line':number,'kind':row['kind'],'trial':row['trial']}
        for line in f:
            raw_hashes[0].update(line);raw_sizes[0]+=len(line);hashes[0].update(line);sizes[0]+=len(line);bad+=1
    assert seen==Counter({qi:1 for qi in range(48)})
    return dict(equal=bad==0 and hashes[0].hexdigest()==hashes[1].hexdigest(),content_bytes=sizes,left_sha256=hashes[0].hexdigest(),right_sha256=hashes[1].hexdigest(),
                mismatching_rows=bad,example=first,excluded_records={'left':0,'right':len(excluded)*2},excluded_pairs=excluded,
                excluded_pair_trial_counts=dict(Counter(str(x['trial']) for x in excluded)),original_content_bytes=raw_sizes,
                original_sha256=[x.hexdigest() for x in raw_hashes])
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('left_output',type=Path);p.add_argument('right_output',type=Path)
    p.add_argument('original_comparison',type=Path);p.add_argument('destination',type=Path)
    p.add_argument('--seed',type=int,choices=[1],default=1)
    a=p.parse_args();assert not a.destination.exists()
    data=a.original_comparison.read_bytes();original=json.loads(data)
    assert original['file_count']==11 and len(original['files'])==11
    assert original['passed'] is False and original['mismatching_files']==1
    results=[]
    for item in original['files']:
        x,y=a.left_output/item['path'],a.right_output/item['path']
        assert x.is_file() and y.is_file()
        if item['path'].endswith('.sme.states.jsonl.gz'):
            before=[sha(x.read_bytes()),sha(y.read_bytes())]
            result=state_compare(x,y,y.with_name('seed001.probe.jsonl'),a.seed)
            assert result['original_sha256']==[item['left_sha256'],item['right_sha256']]
            assert result['original_content_bytes']==item['content_bytes']
            assert before==[sha(x.read_bytes()),sha(y.read_bytes())]
            result.update(path=item['path'],left_exists=True,right_exists=True,mismatching_bytes=0 if result['equal'] else None)
        else:
            op=gzip.open if x.suffix=='.gz' else open
            hs=[hashlib.sha256(),hashlib.sha256()];sizes=[0,0];bad=0
            with op(x,'rb') as f,op(y,'rb') as g:
                while True:
                    l,r=f.read(1024*1024),g.read(1024*1024)
                    for i,v in enumerate((l,r)):hs[i].update(v);sizes[i]+=len(v)
                    bad+=sum(u!=v for u,v in zip(l,r))+abs(len(l)-len(r))
                    if not l and not r:break
            assert [v.hexdigest() for v in hs]==[item['left_sha256'],item['right_sha256']]
            result=dict(path=item['path'],left_exists=True,right_exists=True,equal=bad==0,content_bytes=sizes,left_sha256=hs[0].hexdigest(),right_sha256=hs[1].hexdigest(),mismatching_bytes=bad)
        results.append(result)
    assert a.original_comparison.read_bytes()==data
    result=dict(at=datetime.now().astimezone().isoformat(),instruction=15,approval='D-07βω',model_started=0,
                original_gate_passed=False,original_comparison_sha256=sha(data),passed=all(x['equal'] for x in results),
                file_count=11,mismatching_files=sum(not x['equal'] for x in results),files=results,
                completed_trials=100,configured_trial_count=5000,horizon=5000,full_5000_completed=False,
                method='指示14の固定呼び出し鍵と初期rng一致pre＋直後の同trial predictionだけ除外。原行順・全バイトを維持。speed200では使用しない。')
    with a.destination.open('x') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())

