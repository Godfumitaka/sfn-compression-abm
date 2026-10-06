"""JSONを並べ替えたり欄を除いたりせず、保存した記録の全バイトを比べる。"""
from pathlib import Path
import gzip
import hashlib
import json
import sys

root = Path(__file__).resolve().parent
kind = sys.argv[1]
left, right = ('shop_base', 'shop_port') if kind == 'shop' else ('verb_old', 'verb_port')
a, b = (root/'gates'/side/'output' for side in (left, right))
if kind == 'shop':
    def names(folder):
        return {p.relative_to(folder) for p in folder.rglob('*') if p.is_file() and (str(p.relative_to(folder)).startswith(('ledgers/','side/','evictions/')) and p.suffix != '.done' or p.name == 'flag.json')}
    paths = names(a)
    assert paths == names(b), '記録ファイルの集合が違う'
else:
    paths = {Path('world.jsonl')}
rows=[]
for rel in sorted(paths):
    funcs = gzip.open if rel.suffix == '.gz' else open
    h1,h2=hashlib.sha256(),hashlib.sha256(); n=0; equal=True; mismatch=None
    with funcs(a/rel,'rb') as f, funcs(b/rel,'rb') as g:
        while True:
            x,y=f.read(1024*1024),g.read(1024*1024)
            h1.update(x);h2.update(y)
            if x != y:
                equal=False
                if mismatch is None:
                    mismatch=n+next((i for i,(u,v) in enumerate(zip(x,y)) if u!=v),min(len(x),len(y)))
            n+=len(x)
            if not x and not y:break
    rows.append({'path':str(rel),'content_bytes':n,'left_sha256':h1.hexdigest(),'right_sha256':h2.hexdigest(),
                 'equal':equal,'first_mismatch_byte':mismatch})
result={'gate':kind,'passed':all(r['equal'] for r in rows),'files':rows,
        'mismatching_files':sum(not r['equal'] for r in rows),'compared_content_bytes':sum(r['content_bytes'] for r in rows)}
(root/'gates'/f'{kind}_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)
raise SystemExit(0 if result['passed'] else 1)
