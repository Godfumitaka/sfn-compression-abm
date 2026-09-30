"""公開用の全ファイルの指紋と、圧縮した通信・補助記録の原文一致を保存する。"""
from pathlib import Path
import gzip,hashlib,json,shutil
ROOT=Path(__file__).resolve().parent
TARGET=ROOT.parents[1]/'codex_v310ans_2026-09-30/results/mac/v311cu_1on1'
OUT=ROOT/'outputs'
shutil.copy2(__file__,TARGET/'verify_export.py')
def digest(path, compressed=False):
 h=hashlib.sha256()
 with (gzip.open(path,'rb') if compressed else path.open('rb')) as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
entries=[];compressed=0
for p in sorted(TARGET.rglob('*')):
 if not p.is_file() or p.name=='manifest.json':continue
 rel=p.relative_to(TARGET);r=dict(path=str(rel),bytes=p.stat().st_size,sha256=digest(p))
 if rel.parts[0] in ('L50_recvA','L50_recvB','L50_no_comm','lam020_recvA','lam020_recvB','lam020_no_comm'):
  origin=OUT/rel
 elif rel.parts[0]=='acceptance' and len(rel.parts)>2:
  origin=OUT/Path(*rel.parts[1:])
 else:origin=None
 if origin is not None:
  if p.name.endswith('.jsonl.gz') and ('side' in rel.parts or 'comm' in rel.parts):
   origin=origin.with_suffix('');s=digest(p,True);assert s==digest(origin);r['decoded_sha256']=s;compressed+=1
  else:assert digest(origin)==r['sha256']
 entries.append(r)
meta=json.loads((TARGET/'metadata.json').read_text());assert len(meta['ledgers'])==54
assert len(list((TARGET/'provenance_checks').glob('*.json')))==18
assert max(r['bytes'] for r in entries)<100*1024*1024
manifest=dict(files=entries,file_count=len(entries),compressed_side_and_comm_exact=compressed,
              main_ledger_count=36,acceptance_ledger_count=18,main_world_rows=62640,
              original_outputs_preserved=True,free_bytes=shutil.disk_usage(ROOT).free)
p=TARGET/'manifest.json';assert not p.exists();p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'ファイル':len(entries)+1,'圧縮原文一致':compressed,'合計MB':sum(r['bytes'] for r in entries)/1e6,
                  '最大MB':max(r['bytes'] for r in entries)/1e6,'空きGB':shutil.disk_usage(ROOT).free/1e9},ensure_ascii=False),flush=True)
