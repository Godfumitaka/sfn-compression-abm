"""既存記録だけを展開する関門。模型・照合・分類の関数は呼ばない。"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import resource
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
WORKSPACE = ROOT.parent
OLD = ROOT / 'stage3_night'
SHOP = WORKSPACE / 'codex_attn_2026-10-03/material_rebuild_2026-10-04/n3_w2_A_L50'
SHOP_CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
SHOP_PUBLIC = ROOT / 'report-results/control/attn_seal_diagnostic_2026-10-05'


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return {'path': str(path.relative_to(WORKSPACE)), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def apply_record(old, delta):
    # 台帳の保存形式だけを展開。abm/loop.py の _apply と同じ形式。
    if delta is None:
        return old
    if isinstance(delta, dict) and set(delta) == {'set'}:
        return delta['set']
    if isinstance(delta, dict) and set(delta) == {'ld'}:
        result = list(old)
        for i in sorted(delta['ld']['d'], reverse=True):
            result.pop(i)
        for i, value in delta['ld']['i']:
            result.insert(i, value)
        return result
    result = dict(old) if isinstance(old, dict) else {}
    for key, value in delta.items():
        if value == '__deleted__':
            result.pop(key, None)
        else:
            result[key] = apply_record(result.get(key), value)
    return result


def advance(pre, snapshot):
    # 必要な記憶の二欄だけを復号する。前の行の更新後＝現在行の予測前。
    keys = ('definitions', 'slot_history')
    if snapshot['kind'] == 'full':
        return {k: snapshot['value'][k] for k in keys}
    assert snapshot['kind'] == 'delta'
    return apply_record(pre, {k: snapshot['changes'][k] for k in keys if k in snapshot['changes']})


def seat(d, row, pre):
    key = str((d['name'], row['slot_index']))
    hist = pre['slot_history'].get(key)
    counts = dict(hist) if isinstance(hist, dict) else {p: 1 for p in hist or ()}
    return ('F' if row['alive'] else 'H' if key in pre['slot_history'] else 'U'), counts


def size(d, pre):
    counts = Counter(seat(d, row, pre)[0] for row in d['constituents'])
    return {'total_seats': len(d['constituents']), 'n_F': counts['F'], 'n_H': counts['H'],
            'n_U': counts['U'], 'n_FH': counts['F'] + counts['H']}


def opaque(seed, t, role):
    # 名前の席の出生時の役割を既存記録のIDから読む。世界生成は呼ばない。
    return hashlib.blake2b(f'{seed}\x1f{t}\x1f{role}'.encode(), digest_size=8).hexdigest()


def verb_run(run):
    start = time.monotonic()
    label, seed = run['label'], run['seed']
    assert seed in range(1, 6)
    folder = OLD / label
    ledger_list = list((folder / 'run/ledgers/cells').glob(f'*/seed{seed:03d}.jsonl.gz'))
    assert len(ledger_list) == 1
    ledger = ledger_list[0]
    side = folder / 'run/side' / ledger.parent.name
    cp, sp, bp = folder / 'analysis/cases.jsonl.gz', side / f'seed{seed:03d}.select.jsonl.gz', side / f'seed{seed:03d}.jsonl'
    inputs = [fingerprint(p) for p in (ledger, cp, sp, bp)]
    cases = {c['trial']: c for c in rows(cp)}
    selected_records = {r['t']: r for r in rows(sp) if r['t'] in cases}
    birth_events = {(r['R'], r['trial']): r for r in rows(bp) if r.get('kind') == 'birth'}
    name_ids = {opaque(seed, t, 'relation:shop:sig') for t in range(5000)}
    pre, verbs, births = None, {}, {}
    checks, classes, missing = Counter(), Counter(), []
    out = BASE / 'parts' / f'{label}.candidates.jsonl.gz'
    with gzip.open(out, 'wt') as output:
        for row in rows(ledger):
            if row.get('record_type') != 'trial':
                continue
            t = row['prediction_order']
            assert t == len(verbs)
            verbs[t] = row['verb_name']
            reg = row.get('registration_event')
            if reg and not reg['was_extension']:
                b = reg['base_written_at']
                assert b in verbs and b < t
                side_birth = birth_events[(reg['R'], t)]
                assert side_birth['base_written_at'] == b
                births[(reg['R'], t)] = {
                    'birth_base_trial': b, 'birth_base_verb': verbs[b], 'birth_target_trial': t,
                    'birth_target_verb': verbs[t], 'birth_target_held_predicate': row['held_out_content']['predicate'],
                    'birth_name_predicates': [r['predicate'] for r in reg['constituents'] if r['predicate'].startswith('V') and r['predicate'][1:].isdigit()],
                    'birth_registration_constituents': reg['constituents'], 'birth_name_source': reg['name_source']}
            is_case = bool(row['held_out_is_past'] and row['verb_class'] == 'irregular' and
                           (row.get('predicted_edge') or {}).get('predicate') == 'REG')
            assert is_case == (t in cases), (label, t, '対象試行とcasesが不一致')
            if t in cases:
                c = cases[t]
                assert c['verb'] == row['verb_name']
                good = [x for x in c['candidates'] if x['correct'] and x['gate']]
                cls = 'selection_error' if good else 'distinction_loss'
                assert cls == c['classification']
                assert [x['R'] for x in good] == c['correct_candidates']
                classes[cls] += 1
                saved = {x['R']: x for x in selected_records[t]['cands']}
                sel = c['candidates'][0]
                assert sel['R'] == row['R_used'] and sel['answer'] == 'REG'
                assert sel['arguments'] == row['predicted_edge']['arguments']
                assert saved[sel['R']]['selected'] and saved[sel['R']]['rank_n3'] == 1
                targets = [('selected', 0, sel)] + [('correct', k, g) for k, g in enumerate(good, 1)]
                for role, rank, candidate in targets:
                    d = pre['definitions'][candidate['R']]
                    sr = saved[candidate['R']]
                    sz = size(d, pre)
                    assert sz['n_FH'] == candidate['n'] == sr['n']
                    assert candidate['born'] == sr['reg'] == d['registered_at']
                    assert candidate['support'] == sr['sup'] and candidate['gate'] == sr['gate']
                    assert candidate['N3'] == sr['N3'] == float(Fraction(2 * (sr['name'] + sr['arg'] + sr['link']), sr['S_dd'] + sr['S_xx']))
                    name_seats = []
                    for rr in d['constituents']:
                        if rr['relation']['relation_id'] in name_ids:
                            st, hist = seat(d, rr, pre)
                            name_seats.append({'slot': rr['slot_index'], 'state': st,
                                'predicate': rr['relation']['predicate'] if rr['alive'] else None, 'history': hist})
                    recorded_names = [{k: x[k] for k in ('slot', 'state', 'predicate', 'history')} for x in candidate['name_seats']]
                    assert recorded_names == name_seats, (label, t, candidate['R'], '名前の席が不一致')
                    birth = births.get((d['name'], d['registered_at']))
                    if birth is None:
                        missing.append({'run': label, 't': t, 'R': d['name'], 'field': 'birth_material_verbs'})
                    item = {'world': 'verb', 'run': label, 'arm': run['arm'], 'U': run['U'], 'seed': seed,
                        'trial': t, 'verb': c['verb'], 'classification': cls, 'side': role, 'correct_rank': rank,
                        'R': candidate['R'], 'born': candidate['born'], **sz, 'N3': candidate['N3'],
                        'support': candidate['support'], 'gate': candidate['gate'], 'name_seats': candidate['name_seats'],
                        'legacy_no_definition': c['selected_name_states'] == ['no_definition'], **(birth or {})}
                    output.write(compact(item) + '\n')
                    checks['candidate_fields_verified'] += 1
                checks['classification_verified'] += 1
            pre = advance(pre, row['state_snapshot'])
    assert len(verbs) == 5000 and checks['classification_verified'] == len(cases)
    result = {'run': label, 'arm': run['arm'], 'U': run['U'], 'seed': seed, 'rows': len(verbs),
              'checks': dict(checks), 'classification': dict(classes), 'missing': missing, 'inputs': inputs,
              'elapsed_seconds': time.monotonic() - start, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    dump(BASE / 'parts' / f'{label}.result.json', result)
    return result


def shop_run(seed, cases):
    start = time.monotonic()
    assert seed in range(1, 21)
    ledger = SHOP / 'ledgers/cells' / SHOP_CELL / f'seed{seed:03d}.jsonl.gz'
    side = SHOP / 'side' / SHOP_CELL / f'seed{seed:03d}.shop.jsonl'
    seal_keys = {(r['R'], r['reg'], r['slot']) for r in rows(side) if r['which'] == 'sig'}
    pre, nr, checked = None, 0, 0
    out = BASE / 'parts' / f'shop_s{seed:02d}.candidates.jsonl.gz'
    with gzip.open(out, 'wt') as output:
        for row in rows(ledger):
            if row.get('record_type') != 'trial':
                continue
            t = row['prediction_order']
            assert t == nr
            nr += 1
            if t in cases:
                c = cases[t]
                assert c['day'] == 'exception' and c['baseline_class'] == 'selection_error'
                assert row['R_used'] == c['selected_R'] and row['shop_cue'] == 'e'
                targets = [('selected', 0, c['selected_R'], c['selected_score_record'], c['selected_seal'])]
                targets += [('correct', k['rank_among_correct'], k['R'], k['score_record'], k['seal']) for k in c['correct_candidates']]
                for role, rank, name, sr, ss in targets:
                    d = pre['definitions'][name]
                    sz = size(d, pre)
                    assert sz['n_FH'] == sr['n'] and d['registered_at'] == sr['reg'] == ss['registered_at']
                    calculated = []
                    for rr in sorted(d['constituents'], key=lambda x: x['slot_index']):
                        if (name, d['registered_at'], rr['slot_index']) in seal_keys:
                            st, hist = seat(d, rr, pre)
                            names = [rr['relation']['predicate']] if st == 'F' else sorted(p for p, n in hist.items() if n >= 1) if st == 'H' else []
                            calculated.append({'slot': rr['slot_index'], 'relation_id': rr['relation']['relation_id'],
                                               'state': st, 'names': names, 'history': hist if st == 'H' else None})
                    assert calculated == ss['seats'], (seed, t, name, 'シールの記録が不一致')
                    item = {'world': 'shop', 'run': f'shop_s{seed:02d}', 'arm': 'A', 'U': 'global', 'seed': seed,
                        'trial': t, 'verb': 'sig_e', 'classification': 'selection_error', 'side': role,
                        'correct_rank': rank, 'R': name, 'born': sr['reg'], **sz, 'N3': sr['N3'],
                        'support': sr['sup'], 'gate': sr['gate'], 'name_seats': ss['seats']}
                    output.write(compact(item) + '\n')
                    checked += 1
            pre = advance(pre, row['state_snapshot'])
    assert nr == 1740
    result = {'run': f'shop_s{seed:02d}', 'seed': seed, 'cases': len(cases), 'candidate_fields_verified': checked,
              'inputs': [fingerprint(p) for p in (ledger, side)], 'missing': [],
              'elapsed_seconds': time.monotonic() - start, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    dump(BASE / 'parts' / f'shop_s{seed:02d}.result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', action='store_true')
    args = parser.parse_args()
    (BASE / 'parts').mkdir(exist_ok=True)
    plan = json.loads((OLD / 'plan.json').read_text())['runs']
    assert len(plan) == 30 and {(r['arm'], r['U'], r['seed']) for r in plan} == {
        (a, u, s) for a in ('A', 'C', 'D') for u in ('global', 'abstain') for s in range(1, 6)}
    results = []
    for run in plan[:1] if args.sample else plan:
        target = BASE / 'parts' / f'{run["label"]}.result.json'
        r = json.loads(target.read_text()) if target.exists() else verb_run(run)
        assert not r['missing'], r['missing'][:3]
        results.append(r)
        print(f'{run["label"]}: 関門 {r["classification"]}, {r["elapsed_seconds"]:.1f}秒, RSS {r["peak_rss_bytes"]}', flush=True)
    if args.sample:
        return
    aggregate = Counter()
    for r in results:
        for cls, n in r['classification'].items():
            aggregate[(r['arm'], r['U'], cls)] += n
    expected = list(csv.DictReader((OLD / 'aggregate/classification.csv').open()))
    for r in expected:
        for cls in ('selection_error', 'distinction_loss'):
            assert aggregate[(r['arm'], r['U'], cls)] == int(r[cls]), (r, cls)
    assert sum(aggregate.values()) == 1490
    public = [c for c in rows(SHOP_PUBLIC / 'extracted_cases.jsonl.gz') if c['day'] == 'exception']
    assert len(public) == 136 and all(c['seed'] in range(1, 21) for c in public)
    expected_shop = {(int(c['seed']), int(c['trial'])): c for c in csv.DictReader((SHOP_PUBLIC / 'exception_selection_errors_136.csv').open())}
    assert set(expected_shop) == {(c['seed'], c['trial']) for c in public}
    for c in public:
        r = expected_shop[(c['seed'], c['trial'])]
        assert r['selected_R'] == c['selected_R'] and r['correct_R'] == c['correct_candidates'][0]['R']
    for seed in sorted({c['seed'] for c in public}):
        target = BASE / 'parts' / f'shop_s{seed:02d}.result.json'
        cases = {c['trial']: c for c in public if c['seed'] == seed}
        r = json.loads(target.read_text()) if target.exists() else shop_run(seed, cases)
        assert not r['missing']
        results.append(r)
        print(f'shop_s{seed:02d}: {len(cases)}件, {r["elapsed_seconds"]:.1f}秒, RSS {r["peak_rss_bytes"]}', flush=True)
    manifests = [fingerprint(OLD / 'aggregate/classification.csv'), fingerprint(OLD / 'plan.json')]
    manifests += [fingerprint(SHOP_PUBLIC / n) for n in ('extracted_cases.jsonl.gz', 'exception_selection_errors_136.csv')]
    manifests += [p for r in results for p in r['inputs']]
    dump(BASE / 'gate_result.json', {'state': 'passed', 'verb_cases': 1490, 'shop_cases': 136,
        'classification_mismatches': 0, 'candidate_field_mismatches': 0, 'missing_fields': [],
        'model_reruns': 0, 'model_matching_classification_calls': 0, 'results': results, 'inputs': manifests})


if __name__ == '__main__':
    main()
