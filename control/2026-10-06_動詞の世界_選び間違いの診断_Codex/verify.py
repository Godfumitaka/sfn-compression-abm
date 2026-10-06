"""元のcasesとCSVを別に読み、全件のキー・分類・入力の不変を確認する。"""
import csv
import gzip
import json
import resource
import time
from collections import Counter
from pathlib import Path
import read_records as rec

BASE = Path(__file__).resolve().parent


def main():
    start = time.monotonic()
    gate = json.loads((BASE / 'gate_result.json').read_text())
    primary = list(csv.DictReader((BASE / 'tables/primary_candidates.csv').open()))
    saved = {(r['run'], int(r['trial']), r['side']): r for r in primary}
    assert len(saved) == len(primary)
    checked = 0
    split = Counter()
    for run in json.loads((rec.OLD / 'plan.json').read_text())['runs']:
        assert run['seed'] in range(1, 6)
        for case in rec.rows(rec.OLD / run['label'] / 'analysis/cases.jsonl.gz'):
            chosen = case['candidates'][0]
            good = [c for c in case['candidates'] if c['correct'] and c['gate']]
            assert case['classification'] == ('selection_error' if good else 'distinction_loss')
            row = saved[(run['label'], case['trial'], 'selected')]
            assert row['R'] == chosen['R'] and row['classification'] == case['classification']
            assert float(row['N3']) == chosen['N3'] and int(row['n_FH']) == chosen['n']
            seats = chosen['name_seats']
            if not seats:
                category = 'a_no_name_seat'
            elif all(s['state'] == 'U' for s in seats):
                category = 'c_U'
            elif any((s['state'] == 'F' and s['predicate'] == case['verb']) or
                     (s['state'] == 'H' and s['history'].get(case['verb'], 0) > 0) for s in seats):
                category = 'd_contains_query'
            else:
                category = 'b_other_name'
            assert row['name_class'] == category
            split[category] += 1
            if good:
                correct = saved[(run['label'], case['trial'], 'correct')]
                assert correct['R'] == good[0]['R'] and float(correct['N3']) == good[0]['N3']
            else:
                assert (run['label'], case['trial'], 'correct') not in saved
            checked += 1
    assert checked == 1490
    shop_checked = 0
    for r in csv.DictReader((rec.SHOP_PUBLIC / 'exception_selection_errors_136.csv').open()):
        key = f'shop_s{int(r["seed"]):02d}', int(r['trial'])
        assert saved[(*key, 'selected')]['R'] == r['selected_R']
        assert saved[(*key, 'correct')]['R'] == r['correct_R']
        shop_checked += 1
    assert shop_checked == 136
    for r in primary:
        assert int(r['total_seats']) == sum(int(r[k]) for k in ('n_F', 'n_H', 'n_U'))
        assert int(r['n_FH']) == int(r['n_F']) + int(r['n_H'])
    for p in gate['inputs']:
        assert rec.fingerprint(rec.WORKSPACE / p['path']) == p, p['path']
    old_manifest = {r['path']: r['sha256'] for r in csv.DictReader((rec.ROOT / 'h_formula_2026-10-05/input_manifest.csv').open())}
    matched_prior = 0
    prefix = rec.ROOT.name + '/'
    for p in gate['inputs']:
        rel = p['path'].removeprefix(prefix)
        if rel in old_manifest:
            assert p['sha256'] == old_manifest[rel]
            matched_prior += 1
    result = {'state': 'passed', 'verb_cases_checked': checked, 'shop_cases_checked': shop_checked,
        'name_classes_direct_from_original_cases': dict(split), 'current_input_sha256_checks': len(gate['inputs']),
        'matched_prior_H_audit_sha256': matched_prior, 'mismatches': 0,
        'elapsed_seconds': time.monotonic() - start, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    rec.dump(BASE / 'verification.json', result)
    print(rec.compact(result))


if __name__ == '__main__':
    main()
