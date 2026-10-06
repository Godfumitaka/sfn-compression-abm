"""通過した小試しの記録から、誤答の分類・誕生のシール・費用を並べる。"""
from collections import Counter
from pathlib import Path
import argparse
import csv
import gzip
import json


def read(path):
    with (gzip.open if path.name.endswith('.gz') else open)(path, 'rt') as f:
        for line in f:
            yield json.loads(line)


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def study(cases_file, output):
    cases = json.loads(Path(cases_file).read_text());output = Path(output)
    trial_rows, birth_rows, summary = [], [], []
    for case in cases:
        root = Path(case['path']);seed = case['seed']
        if seed not in (1, 2, 3):
            raise ValueError('種1〜3以外を読まない')
        stem = f'seed{seed:03d}'
        ledger = next((root/'output/ledgers').rglob(stem+'.jsonl.gz'))
        cands = next((root/'analysis/side').rglob(stem+'.sme.candidates.jsonl.gz'))
        side = next((root/'output/side').rglob(stem+'.jsonl'))
        core = read(ledger);next(core)
        side_rows = {r['trial']: r for r in read(side) if r['kind'] == 'v39'}
        counts = Counter()
        for t, (record, candidates) in enumerate(zip(core, read(cands), strict=True)):
            assert t == candidates['trial']
            assert bool(record['hit']) == candidates['original_hit']
            pred = record['predicted_edge']
            outcome = 'correct' if record['hit'] else 'abstain' if pred is None else 'wrong'
            day = 'exception' if record['shop_cue'] == 'sig_e' else 'normal'
            category = (('selection_mistake' if candidates['any_correct'] else 'distinction_loss')
                        if outcome == 'wrong' else '')
            row = {'score': case['score'], 'u_position': case['u_position'], 'seed': seed, 'trial': t,
                   'day': day, 'is_door': record['held_out_is_door'], 'outcome': outcome,
                   'error_category': category, 'any_correct_definition': candidates['any_correct'],
                   'R_used': record['R_used']}
            trial_rows.append(row)
            if row['is_door']:
                counts[day+'_'+outcome] += 1
                if category:
                    counts[day+'_'+category] += 1
            reg = record.get('registration_event')
            if reg and not reg['was_extension']:
                seals = [r for r in reg['constituents'] if r['predicate'] in ('sig_n', 'sig_e')]
                if not seals:
                    counts['birth_without_seal'] += 1
                for seal in seals:
                    st = 'F'
                    for ev in side_rows[t]['conv']:
                        if ev[1] == reg['R'] and ev[2] == seal['slot_index']:
                            if ev[0] == 'FH':st = 'H'
                            elif ev[0] == 'HU':st = 'U'
                    # 最後のHUで定義全体が退役した場合でも、その席のUを数える。
                    birth_rows.append({'score': case['score'], 'u_position': case['u_position'], 'seed': seed,
                                       'trial': t, 'R': reg['R'], 'slot': seal['slot_index'],
                                       'material_name': seal['predicate'], 'state': st})
                    counts['birth_'+st] += 1
        assert t+1 == 1740
        for day in ('exception', 'normal'):
            assert counts[day+'_wrong'] == counts[day+'_selection_mistake']+counts[day+'_distinction_loss']
        row = {'score': case['score'], 'u_position': case['u_position'], 'seed': seed, 'world': 2,
               'lambda': 0.01873710622997919}
        for day in ('exception', 'normal'):
            for item in ('correct', 'wrong', 'abstain', 'selection_mistake', 'distinction_loss'):
                row[day+'_'+item] = counts[day+'_'+item]
        for st in ('F', 'H', 'U'):row['birth_'+st] = counts['birth_'+st]
        row['birth_without_seal'] = counts['birth_without_seal']
        row['final_total_bits'] = side_rows[1739]['bits_after']
        row['final_definition_count'] = side_rows[1739]['defs']
        summary.append(row)
    write(output/'trials.csv', trial_rows)
    write(output/'birth_seals.csv', birth_rows)
    write(output/'comparison.csv', summary)
    print(json.dumps({'cases': len(cases), 'trial_rows': len(trial_rows), 'birth_rows': len(birth_rows)}, ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser();ap.add_argument('cases_file');ap.add_argument('output')
    study(**vars(ap.parse_args()))
