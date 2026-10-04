"""公開用の部品から、元の記録を別の場所へ読み戻す。既存の記録を上書きしない。"""
from pathlib import Path
from hashlib import sha256
import argparse,json,shutil

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);a=ap.parse_args()
    source=Path(__file__).resolve().parent
    if a.output.exists():raise SystemExit('復元の場所は新しい場所にする')
    a.output.mkdir(parents=True)
    partnames=set()
    for index in source.rglob('*.parts.json'):
        record=json.loads(index.read_text());target=a.output/index.parent.relative_to(source)/record['original']
        target.parent.mkdir(parents=True,exist_ok=True);digest=sha256();length=0
        with target.open('wb') as out:
            for part in record['parts']:
                name=index.parent/part['path'];partnames.add(name);local=sha256();local_length=0
                with name.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024**2),b''):
                        out.write(block);digest.update(block);local.update(block);length+=len(block);local_length+=len(block)
                if local.hexdigest()!=part['sha256'] or local_length!=part['bytes']:raise ValueError('部品が違う: '+str(name))
        if digest.hexdigest()!=record['sha256'] or length!=record['bytes']:raise ValueError('連結が元と違う')
    for file in source.rglob('*'):
        if not file.is_file() or file in partnames or file.name.endswith('.parts.json') or file.name in ('restore_bytes.py','pack.json'):continue
        target=a.output/file.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    print('元と同じバイトの記録を読み戻した')

if __name__=='__main__':main()
