"""指示32。確定recordsの指紋と別置きgzipを作り、原写しを消さない。"""
from pathlib import Path
from datetime import datetime
import gzip, hashlib, json, sys

sys.dont_write_bytecode = True
I = Path(__file__).resolve().parent
N = Path('$WORKSPACE/newport_2026-10-07')
sys.path.insert(0, str(N / 'instruction27'))
import checkpoint_digest as fixed


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


assert file_sha(N / 'instruction27/checkpoint_digest.py') == 'f9dfd958bb14e6964df8aa503757939cd21009c2f3362f752de8d759f0642ced'
inventory = json.loads((I / 'records_inventory.json').read_text())
F = I / 'fingerprints'
Z = I / 'compressed_records'
assert not F.exists() and not Z.exists(), '同じ指紋・圧縮を二重起動しない'
F.mkdir()
Z.mkdir()
rows = []
for index, row in enumerate(inventory['files']):
    p = Path(row['path'])
    st = p.stat()
    assert st.st_ino == row['inode'] and st.st_mtime_ns == row['mtime_ns'] and st.st_size == row['bytes']
    raw = fixed.digest(fixed.chunks(p, compressed=False, limit=row['bytes']))
    assert raw['sha256'] == row['sha256'] and raw['bytes'] == row['bytes']
    normalized = fixed.digest(fixed.normalized(fixed.chunks(p, compressed=False, limit=row['bytes']), row['relative_path']))
    evidence = dict(**row, raw=raw, comparison_normalized=normalized,
                    second_stage_time_only=Path(row['relative_path']).parts[0] == 'stage2',
                    files_excluded=0, probe_rows_excluded=0)
    # 指紋はgzipを作る前に確定する。模型の行・順・値は変更しない。
    write(F / f'record_{index:03d}.json', evidence)
    dest = Z / f'seed{row["seed"]:03d}' / f'completed_{row["completed_trials"]:04d}' / (row['relative_path'] + '.gz')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('xb') as out:
        with gzip.GzipFile(filename='', fileobj=out, mode='wb', compresslevel=1, mtime=0) as compressed:
            for block in fixed.chunks(p, compressed=False, limit=row['bytes']):
                compressed.write(block)
    verified = fixed.digest(fixed.chunks(dest, compressed=True))
    assert verified == raw, '圧縮後の解凍内容が違う場合は止め、原写しを消さない'
    after = p.stat()
    assert (after.st_ino, after.st_mtime_ns, after.st_size) == (st.st_ino, st.st_mtime_ns, st.st_size)
    evidence.update(compressed_path=str(dest), compressed_file_sha256=file_sha(dest),
                    compressed_bytes=dest.stat().st_size, decompressed_verified=verified,
                    verification_passed=True, source_record_kept=True, deleted_files=0)
    write(F / f'record_{index:03d}.json', evidence)
    rows.append(evidence)
    write(I / 'fingerprint_compress_progress.json', dict(at=datetime.now().astimezone().isoformat(),
        completed_files=len(rows), total_files=len(inventory['files']), source_records_kept=True,
        deleted_files=0, model_starts=0))
    print('VERIFIED', index, row['seed'], row['completed_trials'], row['relative_path'], flush=True)
write(I / 'fingerprint_compress_completed.json', dict(at=datetime.now().astimezone().isoformat(),
    records=rows, file_count=len(rows), original_bytes=sum(r['bytes'] for r in rows),
    compressed_bytes=sum(r['compressed_bytes'] for r in rows), passed=True,
    source_records_kept=True, deleted_files=0, model_starts=0,
    compressed_archive_only=True, external_archive_path_verified=False,
    comparator_unchanged=True, future_comparisons_not_run=True))
