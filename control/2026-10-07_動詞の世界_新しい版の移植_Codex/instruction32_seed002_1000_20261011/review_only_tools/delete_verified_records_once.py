"""直接承認の範囲で、検証済みgzipを残してrecords写しだけを一度消す。"""
from pathlib import Path
from datetime import datetime
import hashlib, json, shutil, stat

I = Path(__file__).resolve().parent
N = Path('$WORKSPACE/newport_2026-10-07')


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


approval = json.loads((I / 'direct_approval_received.json').read_text())
published = json.loads((I / 'direct_approval_published.json').read_text())
done = json.loads((I / 'fingerprint_compress_completed.json').read_text())
result = json.loads((I / 'compression_runtime/result.json').read_text())
assert approval['delete_only_confirmed_records_after_verified_archive'] and approval['gzip_fallback_authorized']
assert published['normal_push_succeeded'] and result['exit_code'] == 0 and done['passed']
assert not (I / 'cleanup_plan.json').exists() and not (I / 'cleanup_completed.json').exists(), '同じ削除を重ねない'
protected = json.loads((I / 'protected_static_unchanged.json').read_text())['sha256']
assert all(sha(Path(p)) == h for p, h in protected.items()), '状態/RNG/cache/spec/確定印は不変'
rows = done['records']
assert len(rows) == done['file_count'] == 13
assert len({r['path'] for r in rows}) == len(rows)
for r in rows:
    assert r['seed'] == 2 and r['completed_trials'] == 1000
    root = N / 'instruction23_production' / f'19_seed{r["seed"]:03d}_score_e_off' / 'output/comparison_checkpoints/completed_1000/records'
    p, z = Path(r['path']), Path(r['compressed_path'])
    rel = Path(r['relative_path'])
    assert not rel.is_absolute() and '..' not in rel.parts
    assert p == root / rel and p.resolve() == (root / rel).absolute() and not p.is_symlink()
    assert z.resolve().is_relative_to((I / 'compressed_records').resolve()) and not z.is_symlink()
    st = p.stat()
    assert stat.S_ISREG(st.st_mode)
    assert (st.st_ino, st.st_mtime_ns, st.st_size) == (r['inode'], r['mtime_ns'], r['bytes'])
    # 解凍内容は先の受付で全字節を確認済み。現在のgzip容器も同じ指紋か確かめる。
    assert r['verification_passed'] and r['raw'] == r['decompressed_verified']
    assert z.stat().st_size == r['compressed_bytes'] and sha(z) == r['compressed_file_sha256']
    proof = json.loads((root.parent / 'confirmed.json').read_text())
    assert sha(root.parent / 'confirmed.json') == r['confirmed_sha256']
    assert proof['confirmed'] and proof['completed_trials'] == 1000
    record = next(x for x in proof['records'] if x['path'] == str(rel))
    assert all(record[k] == r['raw'][k] for k in ('sha256', 'bytes'))
plan = dict(at=datetime.now().astimezone().isoformat(), records=rows,
    direct_approval_commit=published['commit'], all_gzip_fingerprints_verified_before_deletion=True,
    before_free_bytes=shutil.disk_usage(I).free, file_count=len(rows),
    only_original_records_copies=True, model_starts=0, model_or_observer_changes=0)
save(I / 'cleanup_plan.json', plan)
deleted = []
for r in rows:
    p = Path(r['path'])
    st = p.stat()
    assert (st.st_ino, st.st_mtime_ns, st.st_size) == (r['inode'], r['mtime_ns'], r['bytes'])
    p.unlink()
    deleted.append(dict(path=str(p), bytes=r['bytes'], raw=r['raw'], compressed_path=r['compressed_path'],
        compressed_file_sha256=r['compressed_file_sha256']))
    save(I / 'cleanup_progress.json', dict(at=datetime.now().astimezone().isoformat(),
        deleted_files=len(deleted), deleted=deleted, model_starts=0))
after_protected = {p: sha(Path(p)) for p in protected}
assert after_protected == protected
assert all(not Path(r['path']).exists() and Path(r['compressed_path']).is_file() for r in rows)
after_free = shutil.disk_usage(I).free
save(I / 'archive_index.json', dict(at=datetime.now().astimezone().isoformat(), records=rows,
    file_count=len(rows), passed=True, original_records_deleted=True, raw_contents_retained_in_gzip=True,
    comparator_sha256='f9dfd958bb14e6964df8aa503757939cd21009c2f3362f752de8d759f0642ced',
    files_excluded=0, probe_rows_excluded=0))
save(I / 'cleanup_completed.json', dict(at=datetime.now().astimezone().isoformat(), passed=True,
    deleted_files=len(deleted), deleted_original_bytes=sum(r['bytes'] for r in rows),
    retained_gzip_bytes=done['compressed_bytes'], net_file_bytes_reduced=done['original_bytes']-done['compressed_bytes'],
    before_free_bytes=plan['before_free_bytes'], after_free_bytes=after_free,
    free_change_bytes=after_free-plan['before_free_bytes'], protected_static_sha256=after_protected,
    protected_changed_files=0, deleted=deleted, model_starts=0, model_or_observer_changes=0,
    external_archive_used=False, gzip_fallback=True, only_original_records_copies=True,
    actual_free_is_not_only_our_deletion_effect=True))
print('CLEANUP_VERIFIED', len(deleted), sum(r['bytes'] for r in rows), after_free)
