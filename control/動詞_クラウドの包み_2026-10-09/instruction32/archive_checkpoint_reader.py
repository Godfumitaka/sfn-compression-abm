"""指示32。別置きgzipから元の字節を読み、固定比較器の条件を保つ。"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys

sys.dont_write_bytecode = True
FIXED_SHA = 'f9dfd958bb14e6964df8aa503757939cd21009c2f3362f752de8d759f0642ced'


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def compare(left_case, right_case, completed, destination, archive_index, fixed_path=None):
    fixed_path = Path(fixed_path or Path(__file__).resolve().parent.parent / 'instruction27/checkpoint_digest.py')
    assert file_sha(fixed_path) == FIXED_SHA, '元の固定比較器は変更しない'
    sys.path.insert(0, str(fixed_path.parent))
    spec = importlib.util.spec_from_file_location('instruction32_fixed_reader', fixed_path)
    fixed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixed)
    index = json.loads(Path(archive_index).read_text())
    assert index['passed'] and index['comparator_sha256'] == FIXED_SHA
    assert index['files_excluded'] == index['probe_rows_excluded'] == 0
    left_spec = fixed.read(Path(left_case) / 'spec.json')
    records_root = Path(left_spec['output']) / 'comparison_checkpoints' / f'completed_{completed:04d}' / 'records'
    rows = [r for r in index['records'] if r['completed_trials'] == completed and Path(r['path']).is_relative_to(records_root)]
    archives = {r['relative_path']: r for r in rows}
    proof = fixed.read(records_root.parent / 'confirmed.json')
    assert len(archives) == len(rows) and set(archives) == {r['path'] for r in proof['records']}
    assert not any(p.is_file() for p in records_root.rglob('*')), '未処理の原写しと退避済みを混ぜない'
    original_names = fixed.names

    def names(folder):
        if Path(folder).resolve() == records_root.resolve():
            return {Path(rel) for rel in archives}
        return original_names(folder)

    def compare_file(rel, old_copy, new_original, old_proof, new_proof):
        r = archives[str(rel)]
        assert Path(old_copy) == records_root / rel
        z = Path(r['compressed_path'])
        assert r['verification_passed'] and file_sha(z) == r['compressed_file_sha256']
        old = lambda: fixed.chunks(z, compressed=True)
        new = lambda: fixed.chunks(new_original, compressed=Path(rel).suffix == '.gz', limit=new_proof['bytes'])
        a, b = fixed.digest(old()), fixed.digest(new())
        assert a == r['raw'] == r['decompressed_verified']
        assert all(a[k] == old_proof[k] for k in ('sha256', 'bytes'))
        assert all(b[k] == new_proof[k] for k in ('sha256', 'bytes', 'lines'))
        result = fixed.compare_streams(fixed.normalized(old(), rel), fixed.normalized(new(), rel))
        result.update(path=str(rel), old_raw=a, new_raw=b, line_count_equal=a['lines'] == b['lines'],
            second_stage_time_only=Path(rel).parts[0] == 'stage2')
        result['equal'] = result['equal'] and result['line_count_equal']
        return result

    # ファイルの読み元だけを別置きgzipへ結ぶ。旗/機械/確定印/状態/RNG/cache/履歴は固定入口で検査する。
    fixed.names = names
    fixed.compare_file = compare_file
    return fixed.compare(left_case, right_case, completed, destination)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('left_case'); p.add_argument('right_case'); p.add_argument('completed', type=int)
    p.add_argument('destination'); p.add_argument('archive_index')
    a = p.parse_args()
    raise SystemExit(compare(a.left_case, a.right_case, a.completed, a.destination, a.archive_index))
