"""元を残して選んだ探索の記録を結果枝に複製する。"""
from pathlib import Path
from hashlib import sha256
import json,shutil
ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
TARGET=WORK/'codex_worldv4_2026-10-01/results/mac/sme_light2_2026-10-04'
CHUNK=90*1024**2
folders={'proof_full_01','proof_small_01','component_01','tests_01','profile_200_01','collective_counts_01','analysis_01'}
paths=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and ((p.relative_to(ROOT).parts[0] in folders) or len(p.relative_to(ROOT).parts)==1)]
need=sum(p.stat().st_size for p in paths)
assert shutil.disk_usage(ROOT).free-need>=18*2**30,'公開用の複製後に18GiBを切る'
assert not TARGET.exists(),'公開先を上書きしない';TARGET.mkdir(parents=True)
records=[]
for p in sorted(paths):
    rel=p.relative_to(ROOT);target=TARGET/rel;target.parent.mkdir(parents=True,exist_ok=True)
    digest=sha256();length=0
    if p.stat().st_size<=CHUNK:
        shutil.copy2(p,target)
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024**2),b''):digest.update(block);length+=len(block)
        assert sha256(target.read_bytes()).hexdigest()==digest.hexdigest()
        parts=[]
    else:
        parts=[]
        with p.open('rb') as f:
            for index,block in enumerate(iter(lambda:f.read(CHUNK),b'')):
                q=target.with_name(target.name+f'.part{index:04d}');q.write_bytes(block)
                parts.append({'path':q.name,'bytes':len(block),'sha256':sha256(block).hexdigest()});digest.update(block);length+=len(block)
        target.with_name(target.name+'.parts.json').write_text(json.dumps({'original':target.name,'bytes':length,'sha256':digest.hexdigest(),'parts':parts},ensure_ascii=False,indent=2)+'\n')
        rebuilt=sha256()
        for part in parts:
            with (target.parent/part['path']).open('rb') as f:
                for block in iter(lambda:f.read(1024**2),b''):rebuilt.update(block)
        assert rebuilt.hexdigest()==digest.hexdigest()
    records.append({'file':str(rel),'bytes':length,'sha256':digest.hexdigest(),'parts':len(parts)})
shutil.copy2(WORK/'codex_sme_impl_2026-10-03/stage4_pack_test_01/packed/restore_bytes.py',TARGET/'restore_bytes.py')
(TARGET/'pack.json').write_text(json.dumps({'files':len(records),'bytes':need,'source':str(ROOT),'reconstructed_bytes_equal':True,'records':records},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':len(records),'bytes':need,'reconstructed_bytes_equal':True},ensure_ascii=False))
