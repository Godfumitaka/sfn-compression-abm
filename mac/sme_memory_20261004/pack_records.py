"""元を残し、公開用の複製だけを90MiB以下の部品にする。"""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import shutil

CHUNK = 90 * 1024**2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit('公開用の場所も上書きしない')
    args.destination.mkdir(parents=True)
    records = []
    for source in sorted(args.source.rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts:
            continue
        target = args.destination / source.relative_to(args.source)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, length = sha256(), 0
        if source.stat().st_size <= CHUNK:
            shutil.copy2(source, target)
            with source.open('rb') as stream:
                for block in iter(lambda: stream.read(1024**2), b''):
                    digest.update(block)
                    length += len(block)
            records.append({'file': str(source.relative_to(args.source)), 'bytes': length,
                            'sha256': digest.hexdigest(), 'parts': 0})
            continue
        parts = []
        with source.open('rb') as stream:
            index = 0
            for block in iter(lambda: stream.read(CHUNK), b''):
                part = target.with_name(target.name + f'.part{index:04d}')
                part.write_bytes(block)
                parts.append({'path': part.name, 'bytes': len(block), 'sha256': sha256(block).hexdigest()})
                digest.update(block)
                length += len(block)
                index += 1
        record = {'original': target.name, 'bytes': length, 'sha256': digest.hexdigest(), 'parts': parts}
        target.with_name(target.name + '.parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        records.append({'file': str(source.relative_to(args.source)), 'bytes': length,
                        'sha256': digest.hexdigest(), 'parts': len(parts)})
    restore = Path(__file__).resolve().parent.parent / 'codex_sme_impl_2026-10-03/stage4_pack_test_01/packed/restore_bytes.py'
    shutil.copy2(restore, args.destination / 'restore_bytes.py')
    (args.destination / 'pack.json').write_text(json.dumps({'source': str(args.source.resolve()),
        'chunk_bytes': CHUNK, 'records': records}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'files': len(records), 'bytes': sum(row['bytes'] for row in records),
                      'parts': sum(row['parts'] for row in records)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
