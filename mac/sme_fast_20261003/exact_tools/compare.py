"""見出し一行以外は元のバイトを比較し、違いを省略しない。"""
from pathlib import Path
from hashlib import sha256
import argparse
import gzip
import json
import re


def time_only(data):
    # 承認された実測秒の値だけを置き換える。その他の書式もそのまま比較する。
    return re.sub(rb'("sec_trial"\s*:\s*)-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', rb'\g<1>0', data)


def compare(left, right):
    records = []
    for pattern in ('ledgers/**/*.jsonl.gz', 'side/**/*'):
        paths = sorted(p.relative_to(left) for p in left.glob(pattern) if p.is_file())
        others = sorted(p.relative_to(right) for p in right.glob(pattern) if p.is_file())
        if paths != others:
            raise RuntimeError('ファイルの一覧が違う')
        for name in paths:
            a, b = (left / name).read_bytes(), (right / name).read_bytes()
            if str(name).startswith('ledgers/'):
                a, b = gzip.decompress(a).split(b'\n', 1)[1], gzip.decompress(b).split(b'\n', 1)[1]
            row = {'file': str(name), 'equal': a == b,
                   'left_sha256': sha256(a).hexdigest(), 'right_sha256': sha256(b).hexdigest()}
            if str(name).endswith(('.cflearn.jsonl', '.cfvalue.jsonl')):
                changes = []
                timings = []
                for index, (x, y) in enumerate(zip(a.splitlines(), b.splitlines())):
                    x, y = json.loads(x), json.loads(y)
                    if 'sec_trial' in x or 'sec_trial' in y:
                        timings.append({'line': index + 1, 'baseline_sec_trial': x.get('sec_trial'),
                                        'fast_sec_trial': y.get('sec_trial')})
                    if x != y:
                        changes.append({'line': index + 1, 'keys': [k for k in set(x) | set(y) if x.get(k) != y.get(k)]})
                row['different_fields'] = changes
                row['timing_values'] = timings
                row['raw_bytes_equal'] = a == b
                row['excluded_fields'] = ['sec_trial']
                a, b = time_only(a), time_only(b)
                row['equal'] = a == b
                row['normalized_left_sha256'] = sha256(a).hexdigest()
                row['normalized_right_sha256'] = sha256(b).hexdigest()
            records.append(row)
    a, b = (left.parent / 'tie_rng.jsonl').read_bytes(), (right.parent / 'tie_rng.jsonl').read_bytes()
    records.append({'file': 'tie_rng.jsonl', 'equal': a == b,
                    'left_sha256': sha256(a).hexdigest(), 'right_sha256': sha256(b).hexdigest()})
    return {'all_bytes_equal': all(x['equal'] for x in records), 'records': records}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('left', type=Path)
    ap.add_argument('right', type=Path)
    ap.add_argument('report', type=Path)
    a = ap.parse_args()
    result = compare(a.left, a.right)
    a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not result['all_bytes_equal']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
