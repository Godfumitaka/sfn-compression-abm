"""大きい記録をGitHubの一ファイルの制限内で運ぶ。元のファイルは変更しない。

使い方：python3.12 tools/sme_artifact_pack.py <保存した場所> <新しい公開用の場所>
大きいファイルは圧縮済みのバイトを分割し、順に連結すると元と一字一句同じになる。
"""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import shutil

PART_BYTES = 90 * 1024**2


def pack_file(source, target):
    if source.stat().st_size <= PART_BYTES:
        shutil.copy2(source, target)
        return {'path': target.name, 'bytes': source.stat().st_size, 'split': False}
    digest = sha256()
    parts = []
    with source.open('rb') as stream:
        while block := stream.read(PART_BYTES):
            part = target.with_name(target.name + f'.part{len(parts) + 1:04d}')
            part.write_bytes(block)
            digest.update(block)
            parts.append({'path': part.name, 'bytes': len(block), 'sha256': sha256(block).hexdigest()})
    # 検証は、元を分割したときの控えでなく、書き出した部品を読み戻して行う。
    joined = sha256()
    length = 0
    for part in parts:
        with target.with_name(part['path']).open('rb') as stream:
            for block in iter(lambda: stream.read(1024**2), b''):
                joined.update(block)
                length += len(block)
    if joined.hexdigest() != digest.hexdigest() or length != source.stat().st_size:
        raise ValueError('輸送用の部品を連結したバイトが元と違う')
    record = {'original': target.name, 'bytes': length, 'sha256': digest.hexdigest(),
              'parts': parts, 'joined_bytes_equal': True}
    target.with_name(target.name + '.parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


RESTORE = '''"""公開用の部品から、元の記録を別の場所へ読み戻す。既存の記録を上書きしない。"""
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
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('target', type=Path)
    args = ap.parse_args()
    source, target = args.source.resolve(), args.target.resolve()
    if target.exists():
        raise SystemExit('公開用の場所は新しい場所にする')
    target.mkdir(parents=True)
    files = []
    for file in sorted(source.rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts:
            continue
        out = target / file.relative_to(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        record = pack_file(file, out)
        files.append({'relative_path': str(file.relative_to(source)), 'record': record})
    (target / 'restore_bytes.py').write_text(RESTORE)
    (target / 'pack.json').write_text(json.dumps({'source': str(source), 'part_bytes': PART_BYTES,
                                               'source_changed': False, 'files': files}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'split_files': sum('parts' in r['record'] for r in files)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
