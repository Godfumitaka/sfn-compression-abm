"""種1の元の行バイトを、デスクトップの改行込みsha256と照合する。"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--previous-mac-comparison', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.reference.open(newline='') as source:
        reader = csv.DictReader(source, delimiter='\t')
        assert reader.fieldnames == ['line', 'sha256']
        reference = list(reader)
    assert [int(r['line']) for r in reference] == list(range(1741))
    previous = [json.loads(r) for r in gzip.open(args.previous_mac_comparison, 'rt')]
    assert len(previous) == len(reference) - 1
    previous_summary = json.loads((args.previous_mac_comparison.parent / 'comparison.json').read_text())
    with gzip.open(previous_summary['second'], 'rb') as second_ledger:
        second_header = second_ledger.readline()
    rows = []
    body_hash = hashlib.sha256()
    first_raw = None
    with gzip.open(args.ledger, 'rb') as ledger:
        for line, raw in enumerate(ledger):
            assert line < len(reference)
            sha = hashlib.sha256(raw).hexdigest()
            parsed = json.loads(raw)
            desktop_sha = reference[line]['sha256']
            row = {
                'line_zero_based': line,
                'file_line_one_based': line + 1,
                'prediction_order': parsed.get('prediction_order'),
                'record_type': parsed.get('record_type'),
                'mac_sha256': sha,
                'desktop_sha256': desktop_sha,
                'match': sha == desktop_sha,
            }
            # 既存の別の比較器の結果とも、全行で照合する。
            if line:
                prior = previous[line - 1]
                assert prior['file_line'] == line + 1
                assert prior['first_line_sha256'] == prior['second_line_sha256'] == sha
                assert prior['raw_bytes_match'] is True and prior['changed_fields'] == []
            else:
                # 既存の各行ファイルは本体だけなので、ヘッダは二回目の原文から確認する。
                assert second_header == raw
            rows.append(row)
            if line:
                body_hash.update(raw)
            if first_raw is None and not row['match']:
                first_raw = raw
    assert len(rows) == len(reference)
    different = [r for r in rows if not r['match']]
    summary = {
        'reference_commit': '951021945f0f8a310ad9f58e9811f2248655a80d',
        'reference_tsv_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        'comparison_excluded_fields': [],
        'line_hash_definition': 'gzip展開後の元の行バイト、末尾の改行を含む',
        'line_number_base': 0,
        'total_rows_including_header': len(rows),
        'matching_rows': len(rows) - len(different),
        'different_rows': len(different),
        'matching_body_rows': sum(r['match'] for r in rows[1:]),
        'different_body_rows': sum(not r['match'] for r in rows[1:]),
        'header_match': rows[0]['match'],
        'first_different_row': different[0] if different else None,
        'last_different_row': different[-1] if different else None,
        'mac_body_sha256': body_hash.hexdigest(),
        'previous_mac_check_all_row_hashes_match': True,
        'desktop_rows_contain_field_hashes_or_values': False,
        'changed_field_names': None,
        'model_value_difference': None,
        'serialization_only_difference': None,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'line_comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    all_raw = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows).encode()
    (args.output / 'all_row_comparison.jsonl.gz').write_bytes(gzip.compress(all_raw, mtime=0))
    if first_raw is not None:
        (args.output / 'first_different_mac_row.jsonl.gz').write_bytes(gzip.compress(first_raw, mtime=0))
        assert gzip.decompress((args.output / 'first_different_mac_row.jsonl.gz').read_bytes()) == first_raw
    print(json.dumps({'rows': len(rows), 'different': len(different), 'first': summary['first_different_row'], 'previous_mac_check_all_row_hashes_match': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
