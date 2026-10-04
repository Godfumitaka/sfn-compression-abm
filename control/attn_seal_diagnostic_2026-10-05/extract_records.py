"""保存済みの台帳・候補・回答を読む追加診断。模型と注意の部品はimportしない。"""
import csv
import gzip
import hashlib
import json
import resource
import time
from collections import Counter
from pathlib import Path

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
ROOT = BASE/'material_rebuild_2026-10-04/n3_w2_A_L50'
B = BASE/'stageB_doors_2026-10-05'
C = BASE/'stageCD_doors_2026-10-05'
CELL = 'f0.5000_th2.1000_vt0.3842_first_order'
inputs = {}


def recorded(path):
    inputs[str(path)] = {'bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return path


def rows(path):
    recorded(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def apply_record(old, delta):
    # abm/loop.py:606の保存差分形式だけを展開する。模型の関数は呼ばない。
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


def answer_key(payload):
    edge = payload.get('predicted_edge')
    return None if edge is None else [edge['predicate'], edge['arguments']]


def outcome(payload, truth):
    key = answer_key(payload)
    return 'silence' if key is None else 'correct' if key == truth else 'wrong'


def seal(pre, name, seal_keys, expected):
    dd = pre['definitions'][name]
    seats = []
    for seat in sorted(dd['constituents'], key=lambda x: x['slot_index']):
        key = name, dd['registered_at'], seat['slot_index']
        if key not in seal_keys:
            continue
        hkey = str((name, seat['slot_index']))
        state = 'F' if seat['alive'] else 'H' if hkey in pre['slot_history'] else 'U'
        assert expected[key] == state, (key, state, expected.get(key))
        if state == 'F':
            names, history = [seat['relation']['predicate']], None
        elif state == 'H':
            history = pre['slot_history'][hkey]
            names = sorted(k for k, count in history.items() if count >= 1) if isinstance(history, dict) else sorted(history)
        else:
            # Uは古い述語も履歴も読まない。
            names, history = [], None
        seats.append({'slot': seat['slot_index'], 'relation_id': seat['relation']['relation_id'],
                      'state': state, 'names': names, 'history': history})
    return {'state': '+'.join(x['state'] for x in seats) if seats else 'none',
            'names': [x['names'] for x in seats], 'seats': seats,
            'registered_at': dd['registered_at']}


def main():
    start = time.monotonic()
    destination = JOB/'extracted_cases.jsonl'
    if destination.exists():
        raise RuntimeError('既存の抽出を上書きしない')
    all_cases, counts, pairs = [], Counter(), 0
    for seed in range(1, 21):
        stem = f'seed{seed:03d}'
        cases = {r['trial']: r for r in rows(C/'cases/n3_w2_A_L50'/f'{stem}.cases.jsonl.gz')
                 if r['door_task'] and r['baseline_outcome'] == 'wrong'
                 and (r['shop_cue'] == 'n' or r['actual_correct_candidates'] > 0)}
        targets = set(cases)
        frames = {r['trial']: r for r in rows(B/'frozen/n3_w2_A_L50'/f'{stem}.frozen.jsonl.gz') if r['trial'] in targets}
        original_scores = {r['t']: r for r in rows(ROOT/'side'/CELL/f'{stem}.select.jsonl.gz') if r['t'] in targets}
        attention = {arm: {r['trial']: r for r in rows(B/'replay/n3_w2_A_L50'/f'{stem}.arm{arm}.b5_e0.05.attn.jsonl.gz')
                           if r['trial'] in targets} for arm in (1, 2)}
        final = {arm: json.loads(recorded(B/'replay/n3_w2_A_L50'/f'{stem}.arm{arm}.b5_e0.05.check.json').read_text())['weights_final']
                 for arm in (1, 2)}
        events = list(rows(ROOT/'side'/CELL/f'{stem}.shop.jsonl'))
        seals = {(e['R'], e['reg'], e['slot']) for e in events if e['which'] == 'sig'}
        by_time = {}
        for event in events:
            if event['which'] == 'sig':
                by_time.setdefault(event['trial'], []).append(event)
        pre = None
        nrows = 0
        expected = {}
        for row in rows(ROOT/'ledgers/cells'/CELL/f'{stem}.jsonl.gz'):
            if row.get('record_type', 'trial') != 'trial':
                continue
            t = row['prediction_order']
            assert t == nrows
            nrows += 1
            if t in targets:
                case, frame = cases[t], frames[t]
                selected = frame['baseline']['R_used']
                assert selected == row['R_used'] and row['shop_cue'] == case['shop_cue']
                candidates = frame['candidates']
                selected_c = next(c for c in candidates if c['R'] == selected)
                qrows = {c['R']: c for c in original_scores[t]['cands']}
                correct = sorted((c for c in candidates if c['answer'] == case['truth']), key=lambda c: qrows[c['R']]['rank_n3'])
                assert len(correct) == case['actual_correct_candidates']
                selected_seal = seal(pre, selected, seals, expected)
                item = {'world': 2, 'seed': seed, 'trial': t, 'shop': case['shop_type'],
                        'day': 'exception' if case['shop_cue'] == 'e' else 'normal',
                        'baseline_class': 'selection_error' if correct else 'distinction_loss',
                        'availability': case['availability'], 'truth': case['truth'],
                        'selected_R': selected, 'selected_seal': selected_seal,
                        'selected_score_record': qrows[selected], 'selected_terms': selected_c['terms'],
                        'correct_candidates': [], 'final_weights': final,
                        'online': {arm: {'outcome': outcome(attention[arm][t]['answer_before_update'], case['truth']),
                                        'selected_R': attention[arm][t]['selected_before_update'],
                                        'candidates': attention[arm][t]['candidates']}
                                   for arm in (1, 2)}}
                for rank, candidate in enumerate(correct, 1):
                    item['correct_candidates'].append({'R': candidate['R'], 'rank_among_correct': rank,
                        'seal': seal(pre, candidate['R'], seals, expected),
                        'score_record': qrows[candidate['R']], 'terms': candidate['terms'],
                        'payload': candidate['payload']})
                counts[item['day']] += 1
                pairs += len(correct)
                all_cases.append(item)
            snapshot = row['state_snapshot']
            if snapshot['kind'] == 'full':
                pre = {key: snapshot['value'][key] for key in ('definitions', 'slot_history')}
            else:
                assert snapshot['kind'] == 'delta'
                delta = {key: snapshot['changes'][key] for key in ('definitions', 'slot_history') if key in snapshot['changes']}
                pre = apply_record(pre, delta)
            for event in by_time.get(t, []):
                key = event['R'], event['reg'], event['slot']
                if event['to'] == '定義ごと消えた':
                    expected.pop(key, None)
                else:
                    expected[key] = event['to']
        assert nrows == 1740
        print(f'種{seed}: 例外{sum(c["day"]=="exception" for c in all_cases if c["seed"]==seed)}、通常{sum(c["day"]=="normal" for c in all_cases if c["seed"]==seed)}', flush=True)
    assert counts == {'exception': 136, 'normal': 99}, counts
    assert sum(c['online'][1]['outcome'] == 'correct' for c in all_cases if c['day'] == 'exception') == 4
    assert sum(c['online'][2]['outcome'] == 'correct' for c in all_cases if c['day'] == 'exception') == 3
    with destination.open('x') as output:
        for item in all_cases:
            output.write(json.dumps(item, ensure_ascii=False)+'\n')
    result = {'world': 2, 'seeds': list(range(1, 21)), 'counts': dict(counts),
              'correct_candidate_pairs': pairs, 'beta': 5, 'eta': .05,
              'model_or_attention_imported_or_called': False, 'new_scores_computed': False,
              'seal_rule': '保存済みshop_seatのwhich=sigの(R,reg,slot)。sealmemのshopworld.IDS分類と同一。',
              'correct_representative_rule': '門上の正解候補のうち元N3のrank_n3が最小。全候補も残す。',
              'elapsed_seconds': time.monotonic()-start, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (JOB/'extraction_check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    (JOB/'input_manifest.json').write_text(json.dumps(inputs, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
