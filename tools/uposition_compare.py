"""旗なしの全1740試行を、既存SME土台と全バイトで比較する。"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json


def digest(path, expanded=False):
    h = hashlib.sha256()
    opener = gzip.open if expanded and path.name.endswith('.gz') else open
    with opener(path, 'rb') as f:
        while block := f.read(1024*1024):
            h.update(block)
    return h.hexdigest()


def lines(path):
    with (gzip.open if path.name.endswith('.gz') else open)(path, 'rt') as f:
        return sum(1 for _ in f)


def compare(reference, current, output):
    reference, current, output = map(Path, (reference, current, output))
    files = ['tie_state.jsonl', 'saved_matcher.jsonl.gz']
    files += [str(p.relative_to(reference)) for folder in ('output/side', 'output/ledgers', 'output/evictions')
              for p in (reference/folder).rglob('*') if p.is_file() and not p.name.endswith('.done')]
    rows = []
    for rel in sorted(files):
        a, b = reference/rel, current/rel
        row = {'relative_path': rel, 'reference_path': str(a), 'current_path': str(b),
               'reference_sha256': digest(a), 'current_sha256': digest(b) if b.exists() else '',
               'reference_expanded_sha256': digest(a, True), 'current_expanded_sha256': digest(b, True) if b.exists() else ''}
        row['bytes_equal'] = row['reference_sha256'] == row['current_sha256']
        row['expanded_equal'] = row['reference_expanded_sha256'] == row['current_expanded_sha256']
        rows.append(row)
    extras = [str(p.relative_to(current)) for folder in ('output/side', 'output/ledgers', 'output/evictions')
              for p in (current/folder).rglob('*') if p.is_file() and not p.name.endswith('.done')
              and str(p.relative_to(current)) not in files]
    state_path = next((current/'output/side').rglob('seed001.sme.states.jsonl.gz'))
    tie_path = current/'tie_state.jsonl'
    counts = {'saved_state_lines': lines(state_path), 'rng_trial_lines': lines(tie_path)}
    result = {'passed': all(r['bytes_equal'] for r in rows) and not extras and counts == {
        'saved_state_lines': 1740*3, 'rng_trial_lines': 1740}, 'reference': str(reference), 'current': str(current),
              'files': rows, 'extra_files': extras, **counts,
              'metadata_note': '本体のcode_commit欄は土台の値へ共通化。実装の実コミットはexecution.json。壁時計の時刻と時間を含む.doneとmanifestは模型の本体・sideではなく比較対象外。'}
    output.mkdir(parents=True, exist_ok=True)
    (output/'gate1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    with (output/'gate1_files.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    if not result['passed']:
        print(json.dumps({'passed': False, 'mismatch': [r['relative_path'] for r in rows if not r['bytes_equal']], 'extra_files': extras, **counts}, ensure_ascii=False))
        raise SystemExit(3)
    print(json.dumps({'passed': True, 'compared_files': len(rows), **counts}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser();ap.add_argument('reference');ap.add_argument('current');ap.add_argument('output')
    compare(**vars(ap.parse_args()))


if __name__ == '__main__':
    main()
