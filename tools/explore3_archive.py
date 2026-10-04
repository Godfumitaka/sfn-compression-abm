"""分類後のsideだけを可逆に圧縮し、元バイトのsha256を確認する。台帳はそのまま残す。"""
from pathlib import Path
import sys,gzip,hashlib,json,shutil


def archive(root):
    root=Path(root);rows=[]
    for p in sorted((root/'side').glob('*/*')):
        if p.suffix not in ('.jsonl','.csv'):continue
        dst=p.with_name(p.name+'.gz');tmp=p.with_name(p.name+'.gz.tmp')
        assert not dst.exists(),dst
        with p.open('rb') as src,tmp.open('wb') as output,gzip.GzipFile(fileobj=output,mode='wb',mtime=0,filename=p.name) as gz:
            shutil.copyfileobj(src,gz,length=1024*1024)
        def digest(stream):
            h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
            return h.hexdigest()
        with p.open('rb') as stream:original=digest(stream)
        with gzip.open(tmp,'rb') as stream:restored=digest(stream)
        assert original==restored,p
        rows.append({'file':str(p.relative_to(root)),'sha256':original,'bytes':p.stat().st_size,'compressed_bytes':tmp.stat().st_size})
        tmp.replace(dst);p.unlink()
    (root/'side_compression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return rows

if __name__=='__main__':archive(sys.argv[1])
