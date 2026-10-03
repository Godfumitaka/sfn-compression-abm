"""届いたデスクトップの原文5行を、改行込みの元の行と全欄で比較する。"""
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
first = BASE / 'world1_rebuild/n3_w1_A_L50/ledgers/cells/f0.5000_th2.1000_vt0.3842_first_order/seed001.jsonl.gz'
reference = {}
with (BASE / 'world1_desktop_rowcheck/desktop_9510219_rows.tsv').open() as source:
    for r in csv.DictReader(source, delimiter='\t'):
        reference[int(r['line'])] = r['sha256']


def leaves(a, b, path):
    # JSONキー順だけを正準化し、数値の型と全ての配列の順を保つ。
    if json.dumps(a, sort_keys=True, separators=(',', ':')) == json.dumps(b, sort_keys=True, separators=(',', ':')):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append({'path': path + '.' + key, 'kind': 'missing_key', 'mac_present': key in a, 'desktop_present': key in b})
            else:
                out.extend(leaves(a[key], b[key], path + '.' + key))
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = []
        if len(a) != len(b):
            out.append({'path': path + '.length', 'kind': 'length', 'mac': len(a), 'desktop': len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(leaves(x, y, path + f'[{i}]'))
        return out
    row = {'path': path, 'kind': 'float_value' if isinstance(a, float) and isinstance(b, float) else 'value_or_type', 'mac': a, 'desktop': b}
    if row['kind'] == 'float_value':
        row.update(delta=b-a, ulp_steps_at_mac=abs(b-a)/math.ulp(a), mac_hex=a.hex(), desktop_hex=b.hex())
    return [row]


with gzip.open(first, 'rb') as source:
    mac = {i: raw for i, raw in enumerate(source) if 679 <= i <= 683}
desktop = (JOB / 'desktop_679_to683.jsonl').read_bytes().splitlines(keepends=True)
assert len(desktop) == 5
rows = []
for line, raw in zip(range(679, 684), desktop):
    assert hashlib.sha256(raw).hexdigest() == reference[line]
    a, b = json.loads(mac[line]), json.loads(raw)
    differences = leaves(a, b, '')
    changed_fields = sorted(set(d['path'].split('.')[1].split('[')[0] for d in differences))
    def order_and_lengths(x, y):
        if isinstance(x, dict) and isinstance(y, dict):
            return list(x) == list(y) and all(order_and_lengths(x[k], y[k]) for k in x)
        if isinstance(x, list) and isinstance(y, list):
            return len(x) == len(y) and all(order_and_lengths(u, v) for u, v in zip(x, y))
        return True
    row = {'line_zero_based': line, 'file_line_one_based': line+1, 'prediction_order_mac': a['prediction_order'], 'prediction_order_desktop': b['prediction_order'], 'raw_bytes_match': mac[line] == raw, 'mac_sha256': hashlib.sha256(mac[line]).hexdigest(), 'desktop_sha256': hashlib.sha256(raw).hexdigest(), 'changed_fields': changed_fields, 'object_key_orders_and_array_lengths_match': order_and_lengths(a, b), 'leaf_counts': dict(Counter(d['kind'] for d in differences)), 'leaf_differences': differences}
    rows.append(row)
result = {'reference_commit': 'f24867f0', 'comparison_excluded_fields': [], 'rounding_or_tolerance_applied': False, 'rows': rows}
(JOB / 'desktop_excerpt_comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
for r in rows:
    print(json.dumps({k:v for k,v in r.items() if k != 'leaf_differences'}, ensure_ascii=False))
    if r['line_zero_based'] == 681:
        print(json.dumps({'first_difference_leaves': r['leaf_differences'][:20]}, ensure_ascii=False))
