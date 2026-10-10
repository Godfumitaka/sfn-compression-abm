"""受付内で原成分を可逆圧縮して別公開証拠へ複製する。原資料を消さない。"""
from pathlib import Path
import datetime,gzip,hashlib,json,resource,shutil,time

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
DEST=BASE/'report/control/2026-10-07_介入_新しい版の移植_Codex/指示24_全原成分診断と既存記録口fで停止_20261010_2209'
assert not DEST.exists()
DEST.mkdir(parents=True)
began=time.perf_counter()

def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

inventory={}
compressed=[]
originals=[p for p in HERE.rglob('*')if p.is_file() and '__pycache__'not in p.parts and 'output'not in p.relative_to(HERE).parts]
for source in sorted(originals):
    rel=source.relative_to(HERE)
    target=DEST/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    sha=fingerprint(source)
    inventory[str(rel)]=dict(original_bytes=source.stat().st_size,original_sha256=sha)
    if source.suffix in ('.bin','.raw') and source.stat().st_size>65536:
        target=target.with_name(target.name+'.gz')
        with source.open('rb')as inp,target.open('xb')as out:
            with gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0)as packed:
                shutil.copyfileobj(inp,packed,1024*1024)
        h=hashlib.sha256()
        with gzip.open(target,'rb')as inp:
            for block in iter(lambda:inp.read(1024*1024),b''):h.update(block)
        assert h.hexdigest()==sha and fingerprint(source)==sha
        inventory[str(rel)].update(public_file=str(target.relative_to(DEST)),gzip_sha256=fingerprint(target),reversible_verified=True)
        compressed.append(str(rel))
    else:
        shutil.copyfile(source,target)
        assert fingerprint(target)==sha and fingerprint(source)==sha
        inventory[str(rel)]['public_file']=str(rel)
outputs={}
for case in sorted(HERE.glob('*_tau04_200_*')):
    if case.is_dir():
        outputs[case.name]={str(p.relative_to(case/'output')):dict(bytes=p.stat().st_size,sha256=fingerprint(p))
            for p in sorted((case/'output').rglob('*'))if p.is_file()}
for n in (22,23,24):
    p=BASE/f'instruction{n}_status.json'
    shutil.copyfile(p,DEST/p.name)
(DEST/'original_inventory_01.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
(DEST/'retained_model_output_inventory_01.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2)+'\n')
summary=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),passed=True,public_directory=str(DEST),
    original_files=len(originals),compressed_files=len(compressed),all_gzip_reversible=True,
    all_originals_preserved=True,model_output_case_count=len(outputs),model_outputs_retained_locally=True,
    seconds=time.perf_counter()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(DEST/'publication_verification_01.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
index={str(p.relative_to(DEST)):fingerprint(p)for p in sorted(DEST.rglob('*'))if p.is_file()}
(DEST/'SHA256SUMS').write_text(''.join(f'{sha}  {name}\n'for name,sha in index.items()))
(HERE/'publication_verification_01.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
