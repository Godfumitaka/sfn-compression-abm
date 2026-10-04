"""抽出済みの記録だけから、シール席の区分表と件別CSVを作る。"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from verify_score_arithmetic import arithmetic_q

JOB = Path(__file__).resolve().parent


def text(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def label(seal):
    if seal is None:
        return '門上候補なし'
    if seal['state'] == 'none':
        return '席が無い'
    return '+'.join(seat['state'] + ('['+'|'.join(seat['names'])+']' if seat['names'] else '') for seat in seal['seats'])


def write(name, values):
    values = list(values)
    assert values
    with (JOB/name).open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def main():
    check = json.loads((JOB/'extraction_check.json').read_text())
    assert check['counts'] == {'exception': 136, 'normal': 99}
    verification = json.loads((JOB/'score_verification.json').read_text())
    assert verification['passed'], '保存Qとの全件一致前に点差を出さない'
    cases = [json.loads(line) for line in (JOB/'extracted_cases.jsonl').read_text().splitlines()]
    trials, pair_rows, changed, grouped, all_correct = [], [], [], Counter(), Counter()
    state_groups = Counter()
    for case in cases:
        best = case['correct_candidates'][0] if case['correct_candidates'] else None
        selected_label, best_label = label(case['selected_seal']), label(best['seal'] if best else None)
        base = {k: case[k] for k in ('world', 'seed', 'trial', 'shop', 'day', 'baseline_class', 'availability')}
        common = {**base, 'selected_R': case['selected_R'],
                  'selected_seal_state': case['selected_seal']['state'],
                  'selected_seal_names': text(case['selected_seal']['names']),
                  'selected_seal_seats': text(case['selected_seal']['seats']),
                  'selected_seal_class': selected_label,
                  'selected_Q0_recorded': case['selected_score_record']['N3'],
                  'correct_candidates_above_gate': len(case['correct_candidates']),
                  'arm1_online_outcome': case['online']['1']['outcome'],
                  'arm2_online_outcome': case['online']['2']['outcome']}
        selected_q0 = arithmetic_q(case['selected_terms'], {}, 1)
        assert float(selected_q0) == case['selected_score_record']['N3']
        selected_final = {arm: arithmetic_q(case['selected_terms'], case['final_weights'][str(arm)], arm) for arm in (1, 2)}
        for candidate in case['correct_candidates'] or [None]:
            q = candidate['score_record']['N3'] if candidate else None
            q0 = arithmetic_q(candidate['terms'], {}, 1) if candidate else None
            assert candidate is None or float(q0) == q
            final = {arm: arithmetic_q(candidate['terms'], case['final_weights'][str(arm)], arm) if candidate else None for arm in (1, 2)}
            row = {**common, 'correct_R': candidate['R'] if candidate else '',
                   'rank_among_correct': candidate['rank_among_correct'] if candidate else None,
                   'correct_seal_state': candidate['seal']['state'] if candidate else None,
                   'correct_seal_names': text(candidate['seal']['names']) if candidate else '',
                   'correct_seal_seats': text(candidate['seal']['seats']) if candidate else '',
                   'correct_seal_class': label(candidate['seal'] if candidate else None),
                   'correct_Q0_recorded': q,
                   'gap0_correct_minus_selected': None if q0 is None else float(q0-selected_q0),
                   'correct_Q1_final': None if final[1] is None else float(final[1]), 'selected_Q1_final': float(selected_final[1]),
                   'gap1_final': None if final[1] is None else float(final[1]-selected_final[1]),
                   'gap_change_arm1': None if final[1] is None else float((final[1]-selected_final[1])-(q0-selected_q0)),
                   'correct_Q2_final': None if final[2] is None else float(final[2]), 'selected_Q2_final': float(selected_final[2]),
                   'gap2_final': None if final[2] is None else float(final[2]-selected_final[2]),
                   'gap_change_arm2': None if final[2] is None else float((final[2]-selected_final[2])-(q0-selected_q0)),
                   'final_score_status': 'posthoc_arithmetic_from_saved_coefficients' if candidate else 'not_applicable_no_correct_above_gate'}
            pair_rows.append(row)
            if candidate is None or candidate['rank_among_correct'] == 1:
                trials.append({**row, 'all_correct_seals': text([{'R': c['R'], 'seal': c['seal']} for c in case['correct_candidates']])})
            if candidate:
                all_correct[(case['day'], selected_label, label(candidate['seal']))] += 1
        grouped[(case['day'], case['availability'], selected_label, best_label)] += 1
        state_groups[(case['day'], case['availability'], case['selected_seal']['state'], best['seal']['state'] if best else 'no_above_candidate')] += 1
        for arm in (1, 2):
            online = case['online'][str(arm)]
            if online['outcome'] == 'correct':
                used = next(c for c in case['correct_candidates'] if c['R'] == online['selected_R'])
                changed.append({**base, 'arm': arm, 'selected_R_arm0': case['selected_R'],
                    'selected_seal_class_arm0': selected_label,
                    'best_correct_R_arm0': best['R'], 'best_correct_seal_class': best_label,
                    'selected_correct_R_online': used['R'], 'selected_correct_seal_class_online': label(used['seal']),
                    'best_correct_is_actual_selection': used['R'] == best['R']})
    assert len(trials) == 235
    write('cases.csv', trials)
    write('all_correct_pairs.csv', pair_rows)
    write('online_wrong_to_correct.csv', changed)
    write('state_counts.csv', ({'day': k[0], 'availability': k[1], 'selected_state': k[2],
          'best_correct_state': k[3], 'trials': n} for k, n in sorted(state_groups.items())))
    write('class_counts.csv', ({'day': k[0], 'availability': k[1], 'selected_class': k[2],
          'best_correct_class': k[3], 'trials': n} for k, n in sorted(grouped.items())))
    write('all_correct_class_counts.csv', ({'day': k[0], 'selected_class': k[1],
          'correct_class': k[2], 'candidate_pairs': n} for k, n in sorted(all_correct.items())))
    gap_groups = defaultdict(list)
    for row in trials:
        if row['correct_candidates_above_gate']:
            gap_groups[(row['day'], row['selected_seal_class'], row['correct_seal_class'])].append(row)
    gap_summary = []
    for key, records in sorted(gap_groups.items()):
        cell = dict(zip(('day', 'selected_class', 'best_correct_class'), key))
        cell['trials'] = len(records)
        for field in ('gap0_correct_minus_selected', 'gap1_final', 'gap_change_arm1', 'gap2_final', 'gap_change_arm2'):
            values = [r[field] for r in records]
            cell[field+'_mean'] = sum(values)/len(values)
            cell[field+'_min'], cell[field+'_max'] = min(values), max(values)
        gap_summary.append(cell)
    write('gap_by_class.csv', gap_summary)
    result = {'trial_rows': len(trials), 'pair_rows_including_no_candidate': len(pair_rows),
              'candidate_pairs': check['correct_candidate_pairs'],
              'multi_seal_definitions_in_pairs': sum(len(c['seal']['seats']) > 1 for v in cases for c in v['correct_candidates']),
              'online_exception_repairs': dict(Counter(r['arm'] for r in changed if r['day'] == 'exception')),
              'normal_without_above_candidate': sum(not c['correct_candidates'] for c in cases if c['day'] == 'normal'),
              'state_counts': [{'key': k, 'count': n} for k, n in sorted(state_groups.items())],
              'class_counts': [{'key': k, 'count': n} for k, n in sorted(grouped.items())],
              'online_repairs': changed}
    result['final_score_source'] = '最終重みでの全候補のQは、保存済みの係数からの事後の算術計算'
    result['gap_summary'] = gap_summary
    (JOB/'tabulation_check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
