"""既存の不一致を報告するため、保存状態の行数と欄だけ読む。原本は変更しない。"""
from pathlib import Path
import collections, gzip, hashlib, json

root = Path(__file__).resolve().parent
checks = root / 'instruction6_checks'
comparison = json.loads((checks / 'on100_retry2_comparison.json').read_text())
assert comparison['passed'] is False and comparison['mismatching_files'] == 1
bad = next(row for row in comparison['files'] if not row['equal'])
proof = {'original_comparison': comparison, 'state_record_metadata': {}}
for label in ('on100_without_probe_retry2', 'on100_with_probe_retry2'):
    path = checks / label / 'output' / bad['path']
    kinds = collections.Counter()
    metadata = []
    offset = 0
    containing = None
    with gzip.open(path, 'rb') as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            kind, trial = row.get('kind'), row.get('trial')
            kinds[str(kind)] += 1
            metadata.append({'line': number, 'kind': kind, 'trial': trial,
                             'bytes': len(line), 'sha256': hashlib.sha256(line).hexdigest()})
            if offset <= bad['first_mismatch_byte'] < offset + len(line):
                containing = dict(metadata[-1], record_start_byte=offset,
                                  top_level_fields=list(row))
            offset += len(line)
    proof['state_record_metadata'][label] = {
        'record_count': len(metadata), 'kind_counts': dict(kinds),
        'content_bytes': offset, 'first_mismatch_containing_record': containing,
        'last_records': metadata[-52:],
        'compressed_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'compressed_bytes': path.stat().st_size,
    }
proof['note'] = '原比較の不合格を維持。行・欄の削除、丸め、並べ替え、模型修正、再走行無し。'
destination = root / 'on100_retry2_mismatch_readonly_20261009.json'
with destination.open('x') as output:
    output.write(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({label: {k: v for k, v in value.items() if k != 'last_records'}
                  for label, value in proof['state_record_metadata'].items()}, ensure_ascii=False))
