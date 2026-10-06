"""関門を通った保存済みの候補行を数える。模型のコードはimportしない。"""
from __future__ import annotations
import csv
import gzip
import json
import resource
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
import read_records as records

BASE = Path(__file__).resolve().parent
OUT = BASE / 'tables'
CLASSES = ('a_no_name_seat', 'b_other_name', 'c_U', 'd_contains_query')


def csv_out(path, values):
    values = list(values)
    keys = list(dict.fromkeys(k for v in values for k in v))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        for row in values:
            w.writerow({k: records.compact(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def names(s):
    if s['state'] == 'F':
        return [s['predicate']] if 'predicate' in s else s['names']
    if s['state'] == 'H':
        h = s['history'] or {}
        return sorted(k for k, n in h.items() if n > 0) if isinstance(h, dict) else sorted(h)
    return []


def kind(ns):
    if any(p.startswith('V') and p[1:].isdigit() and 33 <= int(p[1:]) <= 40 for p in ns):
        return 'contains_irregular_verb'
    if ns and all(p.startswith('V') and p[1:].isdigit() and 1 <= int(p[1:]) <= 32 for p in ns):
        return 'regular_verbs_only'
    return 'empty' if not ns else 'other_names'


def annotate(row):
    row = dict(row)
    seats, target = row['name_seats'], row['verb']
    if not seats:
        cls = CLASSES[0]
    elif any(target in names(s) for s in seats):
        cls = CLASSES[3]
    elif all(s['state'] == 'U' for s in seats):
        cls = CLASSES[2]
    else:
        cls = CLASSES[1]
    row.update(name_class=cls, name_seat_count=len(seats),
               name_state_pattern='+'.join(s['state'] for s in seats) or 'none',
               name_fixed_predicates=[p for s in seats if s['state'] == 'F' for p in names(s)],
               name_history_kinds=[kind(names(s)) for s in seats if s['state'] == 'H'],
               name_history_positive_names=[names(s) for s in seats if s['state'] == 'H'],
               name_U_seats=sum(s['state'] == 'U' for s in seats),
               name_mapped_to_query_seats=sum(s.get('maps_to_this_verb', False) for s in seats))
    if row['world'] == 'verb' and cls == CLASSES[0]:
        if row['birth_name_predicates']:
            mechanism = 'name_seat_present_at_birth_later_absent'
        elif row['birth_base_verb'] != row['birth_target_verb']:
            mechanism = 'different_verbs_at_birth_name_not_in_common'
        elif row['birth_base_verb'] == row['birth_target_verb']:
            mechanism = 'same_verb_at_birth_no_name_seat'
        else:
            mechanism = 'unidentified'
        row['absent_name_origin'] = mechanism
    else:
        row['absent_name_origin'] = 'not_applicable'
    return row


def q(values, p):
    values = sorted(values)
    x = (len(values) - 1) * p
    lo = int(x)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (x - lo)


def groups(row):
    # 同じ数値を再集約する各粒度。ALLは集約欄で、元の行は全て残す。
    dims = ('arm', 'U', 'seed', 'verb')
    levels = [('world', ()), ('arm_U', ('arm', 'U')), ('arm_U_seed', ('arm', 'U', 'seed')),
              ('arm_U_verb', ('arm', 'U', 'verb')), ('arm_U_seed_verb', dims)]
    for level, keep in levels:
        yield (row['world'], row['classification'], level,
               *(row[k] if k in keep else 'ALL' for k in dims))


def group_dict(key):
    return dict(zip(('world', 'classification', 'group_level', 'arm', 'U', 'seed', 'verb'), key))


def main():
    start = time.monotonic()
    gate = json.loads((BASE / 'gate_result.json').read_text())
    assert gate['state'] == 'passed' and not gate['missing_fields']
    assert gate['classification_mismatches'] == gate['candidate_field_mismatches'] == 0
    OUT.mkdir(exist_ok=True)
    all_rows = []
    for run in gate['results']:
        all_rows.extend(annotate(r) for r in records.rows(BASE / 'parts' / f'{run["run"]}.candidates.jsonl.gz'))
    primary = [r for r in all_rows if r['side'] == 'selected' or r['correct_rank'] == 1]
    selected = {(r['world'], r['run'], r['trial']): r for r in primary if r['side'] == 'selected'}
    correct = {(r['world'], r['run'], r['trial']): r for r in primary if r['side'] == 'correct'}
    assert sum(r['world'] == 'verb' for r in selected.values()) == 1490
    assert sum(r['world'] == 'shop' for r in selected.values()) == 136
    pairs = []
    for key, s in selected.items():
        if s['classification'] != 'selection_error':
            assert key not in correct
            continue
        c = correct[key]
        p = {k: s[k] for k in ('world', 'run', 'arm', 'U', 'seed', 'trial', 'verb', 'classification')}
        for prefix, row in [('selected', s), ('correct', c)]:
            for k in ('R', 'born', 'total_seats', 'n_F', 'n_H', 'n_U', 'n_FH', 'N3', 'name_class', 'name_state_pattern'):
                p[prefix + '_' + k] = row[k]
        for metric in ('total_seats', 'n_FH', 'N3'):
            diff = s[metric] - c[metric]
            p[metric + '_selected_minus_correct'] = diff
            p[metric + '_difference_sign'] = (diff > 0) - (diff < 0)
        pairs.append(p)
    size_groups, pair_groups, name_groups, other_groups, origin_groups = (defaultdict(list) for _ in range(5))
    for row in primary:
        for key in groups(row):
            size_groups[(*key, row['side'])].append(row)
            name_groups[(*key, row['side'], row['name_class'])].append(row)
            if row['name_class'] == CLASSES[1]:
                detail = records.compact({'F': row['name_fixed_predicates'], 'H_kinds': row['name_history_kinds'],
                                          'H_names': row['name_history_positive_names']})
                other_groups[(*key, row['side'], row['name_state_pattern'], detail)].append(row)
            if row['world'] == 'verb' and row['name_class'] == CLASSES[0]:
                origin_groups[(*key, row['side'], row['absent_name_origin'])].append(row)
    for row in pairs:
        for key in groups(row):
            pair_groups[key].append(row)
    size_summary = []
    for key, values in sorted(size_groups.items(), key=lambda kv: str(kv[0])):
        row = {**group_dict(key[:-1]), 'side': key[-1], 'cases': len(values)}
        for metric in ('total_seats', 'n_FH'):
            x = [r[metric] for r in values]
            row.update({metric + '_q1': q(x, .25), metric + '_median': q(x, .5), metric + '_q3': q(x, .75)})
        for metric in ('N3', 'n_F', 'n_H', 'n_U'):
            row[metric + '_mean'] = statistics.mean(r[metric] for r in values)
        size_summary.append(row)
    pair_summary = []
    for key, values in sorted(pair_groups.items(), key=lambda kv: str(kv[0])):
        row = {**group_dict(key), 'cases': len(values)}
        for metric in ('total_seats', 'n_FH', 'N3'):
            signs = Counter(r[metric + '_difference_sign'] for r in values)
            for sign, label in [(1, 'selected_larger'), (0, 'equal'), (-1, 'selected_smaller')]:
                row[metric + '_' + label] = signs[sign]
                row[metric + '_' + label + '_fraction'] = signs[sign] / len(values)
        pair_summary.append(row)
    csv_out(OUT / 'all_candidates.csv', all_rows)
    csv_out(OUT / 'primary_candidates.csv', primary)
    csv_out(OUT / 'size_pairs.csv', pairs)
    csv_out(OUT / 'size_summary.csv', size_summary)
    csv_out(OUT / 'size_pair_summary.csv', pair_summary)
    csv_out(OUT / 'name_class_counts.csv', ({**group_dict(k[:-2]), 'side': k[-2], 'name_class': k[-1], 'cases': len(v)}
        for k, v in sorted(name_groups.items(), key=lambda kv: str(kv[0]))))
    csv_out(OUT / 'other_name_details.csv', ({**group_dict(k[:-3]), 'side': k[-3], 'name_state_pattern': k[-2],
        'detail': k[-1], 'cases': len(v)} for k, v in sorted(other_groups.items(), key=lambda kv: str(kv[0]))))
    csv_out(OUT / 'absent_name_origins.csv', ({**group_dict(k[:-2]), 'side': k[-2], 'origin': k[-1], 'cases': len(v),
        'definitions': len({(r['run'], r['R'], r['born']) for r in v})}
        for k, v in sorted(origin_groups.items(), key=lambda kv: str(kv[0]))))
    unique_origins = {}
    for r in primary:
        if r['world'] == 'verb' and r['name_class'] == CLASSES[0]:
            key = (r['run'], r['R'], r['born'], r['side'])
            entry = unique_origins.setdefault(key, {k: r[k] for k in ('run', 'arm', 'U', 'seed', 'R', 'born',
                'side', 'absent_name_origin', 'birth_base_trial', 'birth_base_verb', 'birth_target_trial', 'birth_target_verb',
                'birth_name_predicates')})
            entry['cases'] = entry.get('cases', 0) + 1
    csv_out(OUT / 'absent_name_definition_details.csv', unique_origins.values())
    csv_out(OUT / 'input_manifest.csv', gate['inputs'])
    csv_out(OUT / 'resources.csv', ({k: r.get(k) for k in ('run', 'seed', 'elapsed_seconds', 'peak_rss_bytes')}
                                 for r in gate['results']))
    with gzip.open(OUT / 'candidate_records.jsonl.gz', 'wt') as f:
        for row in all_rows:
            f.write(records.compact(row) + '\n')
    result = {'state': 'complete', 'model_reruns': 0, 'candidate_rows': len(all_rows), 'primary_rows': len(primary),
        'verb_cases': sum(r['world'] == 'verb' for r in selected.values()),
        'shop_cases': sum(r['world'] == 'shop' for r in selected.values()),
        'max_name_seats_per_definition': max(r['name_seat_count'] for r in all_rows),
        'legacy_no_definition': sum(r['world'] == 'verb' and r['legacy_no_definition'] for r in selected.values()),
        'elapsed_seconds': time.monotonic() - start, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'pooled_sizes': [r for r in size_summary if r['group_level'] == 'world'],
        'pooled_pair_signs': [r for r in pair_summary if r['group_level'] == 'world'],
        'pooled_name_classes': [{**group_dict(k[:-2]), 'side': k[-2], 'name_class': k[-1], 'cases': len(v)}
                               for k, v in name_groups.items() if k[2] == 'world'],
        'pooled_absent_name_origins': [{**group_dict(k[:-2]), 'side': k[-2], 'origin': k[-1], 'cases': len(v),
                                       'definitions': len({(r['run'], r['R'], r['born']) for r in v})}
                                     for k, v in origin_groups.items() if k[2] == 'world']}
    records.dump(BASE / 'result.json', result)
    print(records.compact(result), flush=True)


if __name__ == '__main__':
    main()
