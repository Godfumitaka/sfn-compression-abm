"""完了済みの解析だけを追加の保存形式にする。原本は残す。"""
from pathlib import Path
import gzip, hashlib, json, subprocess, time

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'diagnostic_full'
DEST=ROOT/'diagnostic_export'
DEST.mkdir(exist_ok=True)
done=set()
while len(done)<220:
    for summary in sorted(SRC.glob('*/seed*.summary.json')):
        key=(summary.parent.name,summary.name)
        if key in done:continue
        meta=json.loads(summary.read_text())
        source=Path(meta['decision_file'])
        output=DEST/source.parent.name/source.name.replace('.gz','.zst')
        output.parent.mkdir(exist_ok=True)
        if output.exists():raise FileExistsError(output)
        digest=hashlib.sha256();nbytes=0
        proc=subprocess.Popen(['/opt/homebrew/bin/zstd','-q','-10','--long=27','-T1','-o',str(output)],stdin=subprocess.PIPE)
        with gzip.open(source,'rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                digest.update(chunk);nbytes+=len(chunk);proc.stdin.write(chunk)
        proc.stdin.close()
        assert proc.wait()==0
        check=hashlib.sha256()
        proc=subprocess.Popen(['/opt/homebrew/bin/zstd','-q','-d','-c',str(output)],stdout=subprocess.PIPE)
        for chunk in iter(lambda:proc.stdout.read(1024*1024),b''):check.update(chunk)
        assert proc.wait()==0 and check.digest()==digest.digest()
        dest_meta=output.with_name(summary.name)
        assert not dest_meta.exists()
        dest_meta.write_text(json.dumps(dict(meta,export_file=str(output),text_bytes=nbytes,
            text_sha256=digest.hexdigest(),export_sha256=hashlib.file_digest(output.open('rb'),'sha256').hexdigest()),
            ensure_ascii=False,indent=2)+'\n')
        done.add(key)
        print(json.dumps({'compressed':output.name,'arm':source.parent.name,'files':len(done),
            'gzip_bytes':source.stat().st_size,'zstd_bytes':output.stat().st_size,'text_bytes':nbytes},ensure_ascii=False),flush=True)
    if 'Traceback' in (ROOT/'diagnostic_full.log').read_text():
        raise RuntimeError('本体の解析が停止したため、完了分を残して圧縮も停止')
    if len(done)<220:time.sleep(10)
print('全220ファイルの文字列が原本と一致',flush=True)
