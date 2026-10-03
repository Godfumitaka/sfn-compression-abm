"""PYTHONHASHSEEDを変えた種1を、元の一回目の全バイトと既存の試行表で比較する。"""
from collections import Counter
import csv
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
BASELINE = BASE / 'world1_rebuild/n3_w1_A_L50'
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
LEDGER = BASELINE / f'ledgers/cells/{CELL}/seed001.jsonl.gz'
TABLE = gzip.decompress((BASE / 'world1_rebuild/tables/trials.tsv.gz').read_bytes())
COLUMNS = TABLE.splitlines(keepends=True)[0]
assert len(TABLE.splitlines()) == 1741
reference = {}
with (BASE / 'world1_desktop_rowcheck/desktop_9510219_rows.tsv').open() as source:
    for row in csv.DictReader(source, delimiter='\t'):
        reference[int(row['line'])] = row['sha256']


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


results = []
for hashseed in (1, 2):
    run = JOB / f'hashseed_{hashseed}'
    out = run / 'n3_w1_A_L50'
    assert (run / 'completion.json').exists()
    actual = out / f'ledgers/cells/{CELL}/seed001.jsonl.gz'
    assert actual.with_name('seed001.done').exists()
    side = out / f'side/{CELL}/seed001.jsonl'
    bits = {}
    with side.open() as source:
        for line in source:
            row = json.loads(line)
            if row.get('kind') == 'v39':
                bits[row['trial']] = (row['bits_after'], row['defs'])
    counts = Counter()
    snapshots = Counter()
    hashes = [hashlib.sha256(), hashlib.sha256()]
    comparison = []
    trials = []
    first_difference = None
    changed_fields = Counter()
    value_different = 0
    with gzip.open(LEDGER, 'rb') as baseline, gzip.open(actual, 'rb') as source:
        for line, (a, b) in enumerate(zip_longest(baseline, source)):
            assert a is not None and b is not None, '行数の差'
            parsed = json.loads(b)
            sha = hashlib.sha256(b).hexdigest()
            changed = []
            if a != b:
                old = json.loads(a)
                changed = sorted(k for k in set(old) | set(parsed) if k not in old or k not in parsed or packed(old[k]) != packed(parsed[k]))
                changed_fields.update(changed)
                value_different += bool(changed)
                if first_difference is None:
                    first_difference = {'line_zero_based': line, 'file_line_one_based': line+1, 'prediction_order_baseline': old.get('prediction_order'), 'prediction_order_actual': parsed.get('prediction_order'), 'changed_fields': changed, 'same_line_as_desktop_681': line == 681}
            comparison.append({'line_zero_based': line, 'file_line_one_based': line+1, 'prediction_order': parsed.get('prediction_order'), 'baseline_sha256': hashlib.sha256(a).hexdigest(), 'actual_sha256': sha, 'baseline_match': a == b, 'desktop_sha256': reference[line], 'desktop_match': sha == reference[line], 'changed_fields': changed})
            if line == 0:
                header_match = a == b
                continue
            hashes[0].update(a)
            hashes[1].update(b)
            counts['body'] += 1
            counts['raw_different_body'] += a != b
            assert parsed['record_type'] == 'trial'
            t = len(trials)
            assert parsed['prediction_order'] == t
            snapshots[parsed['state_snapshot']['kind']] += 1
            outcome = 'a' if parsed['prediction_kind'] == 'Abstain' else ('c' if parsed['hit'] == 1 else 'w')
            bit_count, definitions = bits.get(t, ('', ''))
            values = (1, t, int(bool(parsed['f_fired'])), outcome, parsed.get('abstain_reason') or '', int(bool(parsed.get('held_out_is_door'))), parsed.get('shop_type', ''), parsed.get('shop_cue', ''), parsed.get('door_pred', ''), bit_count, definitions)
            trials.append('\t'.join(str(v) for v in values) + '\n')
    assert counts['body'] == 1740 and len(comparison) == 1741
    assert snapshots == {'full': 1, 'delta': 1739}
    actual_table = COLUMNS + ''.join(trials).encode()
    (run / 'trials.tsv.gz').write_bytes(gzip.compress(actual_table, mtime=0))
    old_lines, new_lines = TABLE.splitlines(keepends=True), actual_table.splitlines(keepends=True)
    trial_diffs = [i for i, (a, b) in enumerate(zip_longest(old_lines, new_lines)) if a != b]
    (run / 'row_comparison.jsonl.gz').write_bytes(gzip.compress(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in comparison).encode(), mtime=0))
    result = {'hashseed': hashseed, 'model_seed': 1, 'comparison_excluded_fields': [], 'rounding_or_tolerance_applied': False, 'flag_exact_match': json.loads((out/'flag.json').read_text()) == json.loads((BASELINE/'flag.json').read_text()), 'header_raw_bytes_match': header_match, 'baseline_body_sha256': hashes[0].hexdigest(), 'actual_body_sha256': hashes[1].hexdigest(), 'body_bytes_match': hashes[0].digest() == hashes[1].digest() and counts['raw_different_body'] == 0, 'body_rows': counts['body'], 'raw_different_body_rows': counts['raw_different_body'], 'value_different_rows_including_header': value_different, 'changed_field_row_counts': dict(changed_fields), 'first_difference': first_difference, 'table_columns': COLUMNS.decode().strip().split('\t'), 'trial_table_uncompressed_bytes_match': actual_table == TABLE, 'trial_table_different_rows_including_header': len(trial_diffs), 'first_trial_table_difference_row_one_based': trial_diffs[0]+1 if trial_diffs else None, 'baseline_trial_table_sha256': hashlib.sha256(TABLE).hexdigest(), 'actual_trial_table_sha256': hashlib.sha256(actual_table).hexdigest(), 'desktop_matching_rows_including_header': sum(r['desktop_match'] for r in comparison), 'desktop_different_rows_including_header': sum(not r['desktop_match'] for r in comparison), 'first_desktop_difference_zero_based': next((r['line_zero_based'] for r in comparison if not r['desktop_match']), None), 'snapshots': dict(snapshots), 'ledger_bytes': actual.stat().st_size, 'side_bytes': sum(p.stat().st_size for p in (out/'side'/CELL).glob('seed001.*'))}
    assert result['baseline_body_sha256'] == '0b0fe3eea24c7849d99869b10d72be3a5a9d99d528ffeea00891fc2b8a187eb4'
    (run / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    results.append(result)
    print(json.dumps({k:v for k,v in result.items() if k != 'table_columns'}, ensure_ascii=False), flush=True)
(JOB / 'comparison.json').write_text(json.dumps({'comparison_excluded_fields': [], 'results': results}, ensure_ascii=False, indent=2) + '\n')
