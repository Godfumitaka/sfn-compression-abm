"""保存済みの台帳・対応・状態を、模型を読み込まずに点検する。

使い方：python3.12 tools/sme_replay_audit.py <走行の出力> <新しい集計.json>
答えの正誤は台帳の予測後の判定だけを集計する。対応の整合は独立に検査する。
"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import json


def rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def alignment_errors(row):
    """採用された対応の全部の順つき引数を、保存した表だけで照合する。"""
    left = {n['key']: n for n in row['left_nodes']}
    right = {n['key']: n for n in row['right_nodes']}
    em, rm = row['new_entity_mapping'], row['new_relation_mapping']
    errors = []
    if len(set(em.values())) != len(em) or len(set(rm.values())) != len(rm):
        errors.append(['one_to_one'])
    if set(em) & set(rm) or set(em.values()) & set(rm.values()):
        errors.append(['entity_relation_overlap'])
    for a, b in em.items():
        if a not in left or b not in right or left[a]['kind'] != 'entity' or right[b]['kind'] != 'entity':
            errors.append(['entity_kind', a, b])
    for a, b in rm.items():
        if a not in left or b not in right:
            errors.append(['missing_node', a, b])
            continue
        x, y = left[a], right[b]
        if x['kind'] not in ('relation', 'unknown') or y['kind'] not in ('relation', 'unknown'):
            errors.append(['relation_kind', a, b])
            continue
        if x['args'] is None or y['args'] is None:
            continue
        if len(x['args']) != len(y['args']):
            errors.append(['arity', a, b])
            continue
        for i, (u, v) in enumerate(zip(x['args'], y['args'])):
            mapped = em.get(u) if u in em else rm.get(u)
            if mapped != v:
                errors.append(['ordered_argument', a, b, i, u, v, mapped])
    for side in (left, right):
        for n in side.values():
            if n['kind'] == 'unknown' and (n['names'] or n['args'] is not None):
                errors.append(['unknown_hidden_content', n['key']])
    return errors


def audit(root):
    manifests = list(rows(root / 'manifest.jsonl'))
    if len(manifests) != 1 or manifests[0].get('error'):
        raise ValueError('完了した一本だけを点検する')
    manifest = manifests[0]
    ledgers = list(root.glob('ledgers/cells/*/*.gz'))
    if len(ledgers) != 1:
        raise ValueError('台帳は一本だけ')
    counts = Counter()
    reasons = Counter()
    shops = {}
    trials = {}
    f_values = Counter()
    header = None
    for row in rows(ledgers[0]):
        if row.get('record_type') == 'run_header':
            header = row
            continue
        number = len(trials)
        if row['prediction_kind'] == 'Abstain':
            outcome = 'abstain'
            reasons[row['abstain_reason']] += 1
        elif row['prediction_kind'] == 'EdgePrediction':
            outcome = 'correct' if row['hit'] else 'wrong'
        else:
            raise ValueError(('分類できない出力', number, row['prediction_kind']))
        counts[outcome] += 1
        actual_f = row.get('f_realized')
        if not isinstance(actual_f, (int, float)) or not 0 <= actual_f <= 1:
            raise ValueError(('実際のfの欠落又は範囲', number, actual_f))
        f_values[str(row.get('f_realized'))] += 1
        kind = row.get('shop_type')
        cue = row.get('shop_cue')
        group = shops.setdefault(f'{kind}/{cue}/all', Counter())
        group[outcome] += 1
        if row.get('held_out_is_door'):
            shops.setdefault(f'{kind}/{cue}/door', Counter())[outcome] += 1
        trials[number] = {'hit': bool(row['hit']), 'abstain': outcome == 'abstain'}
    expected = manifest['trial_count']
    if len(trials) != expected or header['trial_count'] != expected:
        raise ValueError('試行数と全課題の分母が違う')
    if header.get('arm_f_profile', '').startswith('uniform:') and set(f_values) != {str(header['f_setting'])}:
        raise ValueError(('実際のfの記録が設定と違う', f_values))

    versions = Counter()
    callers = Counter()
    alignment_count = 0
    n3_rows = 0
    for path in root.glob('side/*/*.sme.jsonl.gz'):
        for row in rows(path):
            versions[row['version']] += 1
            if row['kind'] == 'sme_result':
                errors = alignment_errors(row)
                if errors:
                    raise ValueError(('対応の独立の検査', alignment_count, row['result'], row['caller'], errors))
                alignment_count += 1
                callers[row['caller']] += 1
            elif row['kind'] == 'sme_n3':
                denominator = row['S_dd'] + row['S_xx']
                if not denominator > 0 or abs(row['N3'] - 2 * row['S_dx'] / denominator) > 1e-14:
                    raise ValueError(('記録されたN3の計算', row))
                n3_rows += 1
    if set(versions) != {'sme2017-ordered-component-1'}:
        raise ValueError(('照合の版が混在', versions))
    state_kinds = Counter()
    seat_states = Counter()
    post_u_trials = []
    for path in root.glob('side/*/*.sme.states.jsonl.gz'):
        for row in rows(path):
            state_kinds[row['kind']] += 1
            if row['kind'] != 'post':
                continue
            fs = row['state']['fields']
            live_names = {p[0] for p in fs['definitions']['items']}
            current = [value['fields']['state'] for key, value in fs['v39_seats']['items']
                       if key['items'][0] in live_names]
            seat_states.update(current)
            if 'U' in current:
                post_u_trials.append(row['trial'])
    if dict(state_kinds) != {'pre': expected, 'prediction': expected, 'post': expected}:
        raise ValueError(('保存した三段の試行数', state_kinds))
    flag = json.loads((root / 'flag.json').read_text())
    if flag['v39_price'] == 0:
        if manifest['v39']['conv_FH'] or manifest['v39']['conv_HU'] or post_u_trials:
            raise ValueError(('λ=0の関門', manifest['v39']['conv_FH'], manifest['v39']['conv_HU'], post_u_trials[:1]))
    candidates = Counter()
    for path in root.glob('side/*/*.sme.candidates.jsonl.gz'):
        for row in rows(path):
            candidates['trials'] += 1
            candidates['candidates'] += len(row['candidates'])
            if row['original_hit'] != trials[row['trial']]['hit']:
                raise ValueError(('解析した正誤が元と違う', row['trial']))
            chosen = [c for c in row['candidates'] if c['selected']]
            if row['chosen_R'] is not None:
                if len(chosen) != 1:
                    raise ValueError(('選ばれた候補の記録', row['trial']))
                c = chosen[0]
                prediction = c['prediction'] or {'abstain_reason': c['abstain_reason']}
                if prediction != row['prediction']:
                    raise ValueError(('解析の答えが元と違う', row['trial']))
                candidates['selected_predictions_equal'] += 1
    return {'source': str(root), 'seed': manifest['seed'], 'trials': expected,
            'outcomes': dict(counts), 'abstain_reasons': dict(reasons), 'f_values': dict(f_values),
            'shop_counts': {k: dict(v) for k, v in shops.items()},
            'alignment_count': alignment_count, 'alignment_violations': 0,
            'versions': dict(versions), 'callers': dict(callers), 'N3_rows': n3_rows,
            'state_kinds': dict(state_kinds), 'post_seat_states': dict(seat_states),
            'post_u_trials': len(post_u_trials), 'first_u_trial': next(iter(post_u_trials), None),
            'conv_FH': manifest['v39']['conv_FH'], 'conv_HU': manifest['v39']['conv_HU'],
            'candidate_analysis': dict(candidates), 'replay': manifest['smereplay'],
            'elapsed_seconds': manifest['elapsed_sec'], 'peak_rss_mb': manifest['peak_rss_mb']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit('点検の集計は新しい出力先にする')
    result = audit(args.run)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
