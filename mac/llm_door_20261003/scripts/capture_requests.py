"""本物のHTTPを禁止し、既存の段階の要求本体を全問分保存する。"""
from pathlib import Path
from contextlib import redirect_stdout
import gzip, hashlib, io, json, os, sys, urllib.request

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/llm_trial'))
import api
import fullhist_stages as stages

mode=sys.argv[1]
assert mode in ('before','after')
os.environ['ANTHROPIC_API_KEY']='offline-placeholder'
def forbidden(*args,**kwargs): raise AssertionError('オフライン検査中のHTTPは禁止')
urllib.request.urlopen=forbidden
api._book=lambda *args,**kwargs: 0.0
records=[]
def capture(url,body,headers,timeout=600):
    records.append({'url':url,'body_utf8':json.dumps(body).encode().decode()})
    if url.endswith('/count_tokens'): return {'input_tokens':5}
    return {'model':body['model'],'id':'offline','stop_reason':'end_turn',
            'content':[{'type':'text','text':json.dumps({'answer':'puga','confidence':0.5,'respond':True})}],
            'usage':{'input_tokens':0,'output_tokens':0,'output_tokens_details':{'thinking_tokens':0}}}
api._post=capture
summary=[]
for stage in ('S基準','S全部ドア'):
    records=[]
    out=ROOT/('gate_'+mode)/stage
    assert not out.exists(),out
    sys.argv=['fullhist_stages.py',str(out),'2',stage,'1']
    with redirect_stdout(io.StringIO()): stages.main()
    data=('\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n').encode()
    path=ROOT/('gate_'+mode)/(stage+'.requests.jsonl.gz')
    path.write_bytes(gzip.compress(data,mtime=0))
    assert len(records)==113,len(records)
    assert sum(r['url'].endswith('/messages') for r in records)==56
    match=None
    if mode=='after':
        old=gzip.decompress((ROOT/'gate_before'/(stage+'.requests.jsonl.gz')).read_bytes())
        assert data==old,stage
        match=True
    summary.append({'stage':stage,'requests':len(records),'messages':56,'count_tokens':57,
                    'all_request_bodies_sha256':hashlib.sha256(data).hexdigest(),'matches_before':match})
(ROOT/('gate_'+mode+'.json')).write_text(json.dumps({'API_calls':0,'checks':summary},ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'API_calls':0,'checks':summary},ensure_ascii=False))
