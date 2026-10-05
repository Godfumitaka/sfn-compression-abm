"""全件CSVを別に読み、最多・置換・件数の保存則と二分母を確認する。"""
from __future__ import annotations
import csv
import json
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path
import audit

OUT = audit.OUT/'stage2'
KEYS = ('arm', 'U', 'seed', 'phase', 'bin', 'verb', 'verb_class')
FIELDS = ('queries', 'answered', 'abstain', 'correct', 'REG', 'other', 'counterfactual_answered_scope', 'counterfactual_correct', 'counterfactual_REG')


def integer(row, field):
    return int(row.get(field) or 0)


def main():
    began = time.monotonic()
    result = json.loads((OUT/'result.json').read_text())
    assert result['state'] == 'complete'
    counts, cf, bd, unassigned = (defaultdict(Counter) for _ in range(4))
    totals = Counter()
    repair_examples = []
    zero_history_examples = []
    first_csv = audit.OUT/'stage2_partial_first/past_questions.csv'
    with (OUT/'past_questions.csv').open() as f, first_csv.open() as old_file:
        initial = iter(csv.DictReader(old_file))
        for r in csv.DictReader(f):
            old = next(initial)
            differences = [k for k in r if r[k] != old[k]]
            if differences:
                assert differences == ['category']
                assert old['category'] == 'その他' and r['category'] == '席が未特定の黙り'
                assert r['phase'] == 'training' and r['abstain_reason'] == 'no_projectable_relation'
                repair_examples.append({k: r[k] for k in ('run', 'phase', 't', 'verb', 'R', 'abstain_reason')})
            assert 1 <= int(r['seed']) <= 5
            assert int(r['bin']) == (int(r['t'])//500 if r['phase'] == 'training' else (int(r['t'])-1)//500)
            key = tuple(r[k] for k in KEYS)
            answered = bool(r['answer'])
            correct = answered and bool(r['truth']) and r['answer'] == r['truth'] and r['arguments_correct'] == 'True'
            assert (r['actual_correct'] == 'True') == correct
            is_reg = r['verb_class'] == 'irregular' and r['answer'] == 'REG'
            c = counts[key]
            c.update(queries=1, answered=int(answered), abstain=int(not answered), correct=int(correct), REG=int(is_reg),
                     other=int(answered and not correct and not is_reg), counterfactual_answered_scope=int(r['counterfactual_scope'] == 'answered_H'))
            hypothetical = r['counterfactual_answer']
            hypothetical_correct = answered and bool(r['truth']) and hypothetical == r['truth'] and r['arguments_correct'] == 'True'
            if answered:
                assert (r['counterfactual_correct'] == 'True') == hypothetical_correct
            else:
                assert r['counterfactual_correct'] == ''
            c['counterfactual_correct'] += int(hypothetical_correct)
            c['counterfactual_REG'] += int(answered and r['verb_class'] == 'irregular' and hypothetical == 'REG')
            changed = r['answer'] != hypothetical
            assert (r['counterfactual_change'] == 'True') == changed
            if r['seat_state'] == 'H' and answered:
                hist = json.loads(r['history'])
                names = json.loads(r['history_pool'])
                top = max(hist[p] for p in names)
                maxima = sorted(p for p in names if hist[p] == top)
                assert maxima == json.loads(r['history_maxima'])
                most = maxima[0] if len(maxima) == 1 else ''
                assert most == r['majority_answer'] == hypothetical
                assert r['category'] == ('H-一致' if most == r['answer'] else 'H-引っ張り')
                weights = json.loads(r['weights'])
                phcounts = json.loads(r['p_hat_candidate_counts'])
                total = int(r['p_hat_total'])
                n = sum(hist[p] for p in names)
                # 当該H履歴名の全体頻度が正の件を、保存された回数から独立に検算する。
                assert all(phcounts[p] > 0 for p in names)
                expected_weights = {p: ((hist[p]/n)*(phcounts[p]/total) if n > 0 else phcounts[p]/total) for p in names}
                assert weights == expected_weights
                winners = [p for p, w in weights.items() if w == max(weights.values())]
                assert winners == [r['answer']]
                totals['H_rechecked'] += 1
                totals['H_zero_history_total'] += int(n == 0)
                if n == 0 and len(zero_history_examples) < 3:
                    zero_history_examples.append({k: r[k] for k in ('run', 'phase', 't', 'verb', 'history', 'weights')})
                totals['H_unique_majority_pull'] += int(changed and len(maxima) == 1)
                totals['H_maximum_tie_to_answer'] += int(changed and len(maxima) > 1)
            elif r['category'] != 'H-黙り':
                assert not changed
            if is_reg:
                assert r['classification'] in ('selection_error', 'distinction_loss', 'not_recorded_probe')
                bd[(*key, r['category'], r['subtype'], r['classification'])]['REG'] += 1
            if r['category'] == '席が未特定の黙り':
                assert not answered and not r['slot'] and not r['seat_state'] and not r['history']
                unassigned[(r['arm'], r['U'], r['seed'], r['phase'], r['bin'], r['abstain_reason'])]['count'] += 1
            z = cf[(*key, r['category'], r['subtype'])]
            z.update(queries=1, changed=int(changed), overREG_to_correct=int(is_reg and hypothetical_correct),
                     correct_to_wrong=int(correct and bool(hypothetical) and not hypothetical_correct),
                     correct_to_silence=int(correct and not hypothetical), regular_changed=int(r['verb_class'] == 'regular' and changed),
                     silence_to_seat_answer_lower_bound=int(not answered and bool(hypothetical)))
            totals[r['phase']+':queries'] += 1
            totals[r['phase']+':answered'] += int(answered)
            totals[r['phase']+':unidentified_silence'] += int(r['category'] == '席が未特定の黙り')
        assert next(initial, None) is None
    assert len(repair_examples) == 5
    for c in counts.values():
        assert c['queries'] == c['answered'] + c['abstain'] == c['correct'] + c['REG'] + c['other'] + c['abstain']
    original = {tuple(r[k] for k in KEYS): r for r in csv.DictReader((OUT/'rates_per_verb.csv').open())}
    assert original.keys() == counts.keys()
    for k, c in counts.items():
        assert all(integer(original[k], p) == c[p] for p in FIELDS), k
    for file, data, extra in (('counterfactual.csv', cf, ('category', 'subtype')),
                              ('overregularization_breakdown.csv', bd, ('category', 'subtype', 'classification')),
                              ('unidentified_silence.csv', unassigned, None)):
        fields = (*KEYS, *extra) if extra else ('arm', 'U', 'seed', 'phase', 'bin', 'abstain_reason')
        saved = {tuple(r[k] for k in fields): r for r in csv.DictReader((OUT/file).open())}
        assert data.keys() == saved.keys(), file
        for k, c in data.items():
            assert all(integer(saved[k], p) == v for p, v in c.items()), (file, k)
    # 問いが0回だった不規則語×時点も残し、率を0で埋めず欠測にする。
    for a in ('A', 'C', 'D'):
        for u in ('global', 'abstain'):
            for s in range(1, 6):
                for phase in ('training', 'probe'):
                    for b in range(10):
                        for v in range(33, 41):
                            counts.setdefault((a, u, str(s), phase, str(b), f'V{v:02d}', 'irregular'), Counter())
    def with_rates(k, c, fields):
        den = c['correct'] + c['REG']
        cfden = c['counterfactual_correct'] + c['counterfactual_REG']
        applicable = k[-1] == 'irregular'
        return {**dict(zip(fields, k)), **{p: c[p] for p in FIELDS}, 'marcus_applicable': applicable,
                'marcus_denominator': den if applicable else None,
                'marcus_rate': c['REG']/den if applicable and den else None,
                'REG_all_queries_rate': c['REG']/c['queries'] if applicable and c['queries'] else None,
                'counterfactual_answered_marcus_denominator': cfden if applicable else None,
                'counterfactual_answered_marcus_rate': c['counterfactual_REG']/cfden if applicable and cfden else None,
                'counterfactual_answered_REG_all_queries_rate': c['counterfactual_REG']/c['queries'] if applicable and c['queries'] else None}
    audit.csv_out(OUT/'rates_per_verb.csv', [with_rates(k, c, KEYS) for k, c in sorted(counts.items())])
    pooled = defaultdict(Counter)
    for k, c in counts.items():
        pooled[(k[0], k[1], k[3], k[4], k[5], k[6])].update(c)
    audit.csv_out(OUT/'rates_pooled_seeds.csv', [with_rates(k, c, ('arm', 'U', 'phase', 'bin', 'verb', 'verb_class')) for k, c in sorted(pooled.items())])
    assert totals['training:queries'] == 13650 and totals['probe:queries'] == 72000 and totals['H_rechecked'] == 49178
    assert totals['training:unidentified_silence'] == 740 and totals['probe:unidentified_silence'] == 8260
    verification = {'state': 'verified', 'counts': dict(totals), 'all_question_rows': 85650,
                    'initial_to_corrected_category_only_differences': len(repair_examples), 'repair_examples': repair_examples,
                    'zero_history_total_uses_existing_p_hat_fallback_examples': zero_history_examples,
                    'rate_rows_including_zero_query_irregular_cells': len(counts), 'mismatches': 0,
                    'elapsed_seconds': time.monotonic()-began, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    audit.dump(OUT/'verification.json', verification)
    manifests = list(csv.DictReader((OUT/'input_manifest.csv').open()))
    manifests.append(audit.fingerprint(Path(__file__)))
    manifests.append(audit.fingerprint(first_csv))
    audit.csv_out(OUT/'input_manifest.csv', manifests)
    print(json.dumps(verification, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
