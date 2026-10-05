"""段C・Dの種ごとの表を結合する。種の原表を残して件数を合計する。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'), str(W)]
import attnsummary as S


def read_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        yield from csv.DictReader(stream)


def fold(rows, keys, values):
    grouped = defaultdict(Counter)
    for row in rows:
        key = tuple(row[k] for k in keys)
        for name in values:
            if row[name] != '':
                grouped[key][name] += int(row[name])
    return grouped


def decoded(counter, keys):
    # world/arm/beta/etaは測度側の分岐にも使うため型を戻す。
    result = defaultdict(Counter)
    for key, counts in counter.items():
        typed = tuple(int(value) if k in ('world', 'arm') else float(value) if k in ('beta', 'eta') else value
                      for k, value in zip(keys, key))
        result[typed].update(counts)
    return result


def concatenate_csv_stream(paths, destination):
    """値・欄・種の順序を維持し、大きな記録だけを一行ずつ結合する。"""
    manifest = []
    fields = writer = None
    with destination.open('w', encoding='utf-8', newline='') as target:
        for path in paths:
            with path.open(encoding='utf-8', newline='') as source:
                reader = csv.DictReader(source)
                if fields is None:
                    fields = reader.fieldnames
                    writer = csv.DictWriter(target, fieldnames=fields)
                    writer.writeheader()
                assert fields == reader.fieldnames
                writer.writerows(reader)
            manifest.append({'path': str(path), 'bytes': path.stat().st_size,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return manifest


def aggregate(output, stage, *, grid_name='original'):
    if stage not in ('C', 'D'):
        raise ValueError('段C又はD')
    variants, grid = S.grid_spec(grid_name)
    if stage == 'D' and grid_name != 'original':
        raise ValueError('追加の大きなηの格子では段Dを実行しない')
    folder = output/'aggregate'
    folder.mkdir(exist_ok=True)
    marker = output/f'all_{stage}.json'
    if marker.exists():
        raise RuntimeError('既存の集計を重複して作らない')
    seeds = [output/f'n3_w{world}_A_L50'/f'seed{seed:03d}' for world in (1, 2) for seed in range(1, 21)]
    checks = [json.loads((p/('check.json' if stage == 'C' else 'D_check.json')).read_text()) for p in seeds]
    assert all(c['passed'] and c['mismatch'] is None for c in checks)
    files = ['responses.csv', 'outcomes.csv', 'original_errors.csv', 'transitions.csv', 'weights_100_trials.csv',
             'first_seen.csv', 'update_reasons.csv', 'loss_100_trials.csv', 'signal_detection.csv'] if stage == 'C' else ['stageD_transitions.csv']
    all_rows = {}
    manifest = []
    for name in files:
        if grid_name == 'large-eta' and name == 'weights_100_trials.csv':
            # この表は数の計算に使わず、種別の原表を結合して保存するだけ。
            manifest.extend(concatenate_csv_stream([seed/name for seed in seeds], folder/('seed_'+name)))
            continue
        rows = []
        fields = None
        for seed in seeds:
            path = seed/name
            with path.open(encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream)
                if fields is None:
                    fields = reader.fieldnames
                assert fields == reader.fieldnames
                rows.extend(reader)
            manifest.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        all_rows[name] = rows
        S.write_csv(folder/('seed_'+name), rows, fields)
    if stage == 'C':
        assert all(c['variants'] == len(variants) and c.get('grid', 'original') == grid_name for c in checks)
        response_keys = ('world', 'arm', 'beta', 'eta', 'shop', 'day')
        response = decoded(fold(all_rows['responses.csv'], response_keys, (*S.CLASSES, 'hold', 'hold_b')), response_keys)
        responses = list(S.response_rows(response, response_keys))
        S.write_csv(folder/'responses.csv', responses, tuple(responses[0]))
        signal = list(S.signal_rows(response, response_keys))
        fields = ('world', 'arm', 'beta', 'eta', 'shop', 'hit', 'miss', 'false_alarm', 'correct_rejection',
                  'excluded_signal_silence', 'excluded_signal_other', 'excluded_noise_silence', 'excluded_noise_other',
                  'dprime', 'criterion', 'hit_rate', 'false_alarm_rate', 'adjusted_hit_rate', 'adjusted_false_alarm_rate',
                  'corrected', 'undefined_reason')
        S.write_csv(folder/'signal_detection.csv', signal, fields)
        for name, keys in [('outcomes.csv', ('world', 'arm', 'beta', 'eta', 'task', 'shop', 'day', 'availability')),
                           ('original_errors.csv', ('world', 'arm', 'beta', 'eta', 'shop', 'day', 'error_type'))]:
            counts = fold(all_rows[name], keys, S.OUTCOMES)
            rows = list(S.table_rows(counts, keys, S.OUTCOMES))
            S.write_csv(folder/name, rows, (*keys, 'total', *S.OUTCOMES, *(v+'_rate' for v in S.OUTCOMES)))
        for name, keys in [('update_reasons.csv', ('world', 'arm', 'beta', 'eta', 'task', 'reason'))]:
            counts = fold(all_rows[name], keys, ('count',))
            S.write_csv(folder/name, ({**dict(zip(keys, key)), 'count': value['count']} for key, value in sorted(counts.items())), (*keys, 'count'))
        keys = ('world', 'arm', 'beta', 'eta', 'bin_start', 'shop', 'day')
        losses = defaultdict(Counter)
        for row in all_rows['loss_100_trials.csv']:
            key = tuple(row[k] for k in keys)
            for value in ('defined_count', 'updated_count'):
                losses[key][value] += int(row[value])
            losses[key]['sum_L'] += float(row['sum_L'])
        S.write_csv(folder/'loss_100_trials.csv', ({**dict(zip(keys, key)), **cell, 'mean_L': cell['sum_L']/cell['defined_count']}
                    for key, cell in sorted(losses.items())), (*keys, 'defined_count', 'updated_count', 'sum_L', 'mean_L'))
        checks_total = sum(c['trial_records'] for c in checks)
        assert checks_total == 69600*len(variants)
        assert sum(int(r['total']) for r in all_rows['responses.csv']) == 6306*len(variants)
        assert sum(int(r['count']) for r in all_rows['update_reasons.csv']) == checks_total
        assert all(c['distinction_loss_to_correct'] == 0 and c['non_door_answer_mismatches'] == 0 for c in checks)
        marker_data = {'passed': True, 'seeds': 40, 'trial_records': checks_total, 'door_trial_records': 6306*len(variants),
                       'distinction_loss_to_correct': 0, 'non_door_answer_mismatches': 0, 'phaseD_started': False}
        transition_name, transition_keys = 'transitions.csv', ('world', 'beta', 'eta', 'source_arm', 'target_arm', 'task', 'shop', 'day', 'before', 'after')
    else:
        assert sum(c['trial_records'] for c in checks) == 6306*9
        marker_data = {'passed': True, 'seeds': 40, 'trial_records': 6306*9, 'model_updated': False,
                       'attention_updated': False, 'reset_normalized': False,
                       'weight_time': 'each_seed_final_after_last_trial'}
        transition_name, transition_keys = 'stageD_transitions.csv', ('world', 'beta', 'eta', 'pair', 'shop', 'day', 'before', 'after')
    transitions = fold(all_rows[transition_name], transition_keys, ('count',))
    S.write_csv(folder/transition_name, ({**dict(zip(transition_keys, key)), 'count': count['count']}
                for key, count in sorted(transitions.items())), (*transition_keys, 'count'))
    marker_data.update(stage=stage, manifest=manifest, checks=checks, phase3_started=False,
        task_instruction_assumption='本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う')
    if grid_name != 'original':
        marker_data.update(grid=grid_name, parameter_pairs=grid)
    marker.write_text(json.dumps(marker_data, ensure_ascii=False, indent=2)+'\n')
    return {k: v for k, v in marker_data.items() if k not in ('manifest', 'checks')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--aggregate-fixed-memory', action='store_true', required=True)
    ap.add_argument('--stage', choices=('C', 'D'), required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--attn-grid', choices=('original', 'large-eta'), default='original')
    args = ap.parse_args()
    print(json.dumps(aggregate(args.output, args.stage, grid_name=args.attn_grid), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
