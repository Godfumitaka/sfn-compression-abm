"""記録診断の40種を集める。再選択・学習・模型は呼ばない。"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import resource
import time
from attnposition_diagnosis import CONDITIONS, write_csv


def csv_rows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def aggregate(base, job):
    start = time.monotonic()
    output = job / 'diagnostic_summary'
    if output.exists() and any(output.iterdir()):
        raise RuntimeError('既存の診断集計を重複しない')
    output.mkdir(exist_ok=True)
    assert json.loads((job / 'diagnosis_supervision/status.json').read_text())['status'] == 'complete_diagnosis_ready_for_aggregation'
    changed, blank, healed = [], [], []
    census, kinds, kind_sum, reasons = Counter(), Counter(), defaultdict(float), Counter()
    classes = {}
    for line in (base / 'seal_diagnostic_2026-10-05/extracted_cases.jsonl').open():
        d = json.loads(line)
        if d['day'] == 'exception' and d['baseline_class'] == 'selection_error':
            seal = d['selected_seal']
            classes[d['seed'], d['trial']] = 'U' if seal['state'] == 'U' else 'H[' + seal['seats'][0]['names'][0] + ']'
    assert Counter(classes.values()) == Counter({'H[sig_n]': 68, 'U': 52, 'H[sig_e]': 16})
    checks = []
    for w in (1, 2):
        for s in range(1, 21):
            folder = job / 'diagnosis' / f'n3_w{w}_A_L50'
            stem = f'seed{s:03d}'
            check = json.loads((folder / f'{stem}.diagnosis.check.json').read_text())
            assert check['passed'] and check['trials'] == 1740
            checks.append(check)
            changed.extend(csv_rows(folder / f'{stem}.changed.csv.gz'))
            blank.extend(csv_rows(folder / f'{stem}.blank.csv.gz'))
            for row in csv_rows(folder / f'{stem}.healed.csv'):
                row['baseline_seal_class'] = classes[int(row['seed']), int(row['trial'])]
                healed.append(row)
            for row in csv_rows(folder / f'{stem}.census.csv'):
                for measure in ('denominator_all_seats', 'denominator_non_door_seats', 'missing_ancestor'):
                    census[w, row['condition'], row['scope'], measure] += int(row[measure])
            for row in csv_rows(folder / f'{stem}.seat_kinds.csv'):
                key = w, row['condition'], row['seat_kind']
                kinds[key] += int(row['count'])
                kind_sum[key] += float(row['m_sum'])
            for row in csv_rows(folder / f'{stem}.zero_reasons.csv'):
                reasons[w, row['condition'], row['scope'], row['state'], row['reason']] += int(row['count'])
    # 空の種があっても、全種で存在する列を保持する。
    write_csv(output / 'changed_pairs.csv.gz', changed, list(dict.fromkeys(k for r in changed for k in r)))
    write_csv(output / 'blank_selected_R.csv.gz', blank)
    write_csv(output / 'healed_selection_errors.csv', healed)
    pair_summary = []
    for w in (1, 2):
        for c in CONDITIONS:
            for day in ('normal', 'exception'):
                all_rows = [r for r in changed if r['world'] == str(w) and r['condition'] == c and r['day'] == day]
                rows = [r for r in all_rows if r['record_status'] == 'complete']
                fewer = sum(r['d1_fewer_counted_seats'] == 'True' for r in rows)
                delta = sum(float(r['penalty_difference_d0_minus_d1']) for r in rows)
                other = sum(float(r['penalty_difference_other']) for r in rows)
                pair_summary.append({'world': w, 'condition': c, 'day': day, 'changed_trials': len(all_rows),
                                     'known_pairs': len(rows), 'unknown_pairs': len(all_rows) - len(rows),
                                     'd1_fewer_counted': fewer, 'd1_fewer_fraction': fewer / len(rows) if rows else None,
                                     'penalty_difference_sum': delta, 'nonseal_difference_sum': other,
                                     'nonseal_signed_fraction_of_sum': other / delta if delta else None,
                                     'penalty_difference_zero_pairs': sum(float(r['penalty_difference_d0_minus_d1']) == 0 for r in rows),
                                     'penalty_difference_negative_pairs': sum(float(r['penalty_difference_d0_minus_d1']) < 0 for r in rows)})
    write_csv(output / 'changed_pair_summary.csv', pair_summary)
    cr = []
    for w in (1, 2):
        for c in CONDITIONS:
            for scope in ('all', 'selected', 'correct_above_gate'):
                n = census[w, c, scope, 'denominator_all_seats']
                non_door = census[w, c, scope, 'denominator_non_door_seats']
                missing = census[w, c, scope, 'missing_ancestor']
                cr.append({'world': w, 'condition': c, 'scope': scope, 'all_candidate_seat_trials': n,
                           'non_door_candidate_seat_trials': non_door, 'missing_ancestor': missing,
                           'missing_ancestor_fraction_all': missing / n if n else None,
                           'missing_ancestor_fraction_non_door': missing / non_door if non_door else None})
    write_csv(output / 'missing_ancestor_denominators.csv', cr)
    kr = [{'world': w, 'condition': c, 'seat_kind': k, 'count': kinds[w, c, k], 'm_sum': kind_sum[w, c, k],
           'm_mean': kind_sum[w, c, k] / kinds[w, c, k] if kinds[w, c, k] else None}
          for w in (1, 2) for c in CONDITIONS for k in ('F_match', 'F_mismatch', 'H_present', 'H_absent', 'U')]
    write_csv(output / 'seat_kind_means.csv', kr)
    rr = [{'world': w, 'condition': c, 'scope': sc, 'state': st, 'reason': re, 'count': n}
          for (w, c, sc, st, re), n in sorted(reasons.items())]
    write_csv(output / 'counted_and_excluded.csv', rr)
    bc = Counter((int(r['world']), r['condition'], r['day'], r['baseline_outcome'], r['outcome'],
                  r['silence_cause'], r['abstain_reason'], bool(r['winning_R'])) for r in blank)
    br = [{'world': w, 'condition': c, 'day': day, 'baseline_outcome': before, 'outcome': after,
           'silence_cause': cause, 'abstain_reason': reason, 'winning_candidate_known': known, 'count': n}
          for (w, c, day, before, after, cause, reason, known), n in sorted(bc.items())]
    write_csv(output / 'blank_selected_R_counts.csv', br)
    hc = Counter((r['condition'], r['baseline_seal_class'], r['d1_is_highest_Q_correct']) for r in healed)
    hr = [{'condition': c, 'baseline_seal_class': cls, 'highest_Q_correct': hc[c, cls, 'True'],
           'other_correct': hc[c, cls, 'False'], 'total_healed': hc[c, cls, 'True'] + hc[c, cls, 'False']}
          for c in CONDITIONS for cls in ('H[sig_n]', 'U', 'H[sig_e]')]
    write_csv(output / 'healed_candidate_ranks.csv', hr)
    result = {'passed': True, 'trials': sum(c['trials'] for c in checks), 'seeds': 40,
              'conditions': CONDITIONS, 'changed_pairs': len(changed), 'blank_records': len(blank),
              'healed_records': len(healed), 'model_or_selection_or_learning_called': False,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'elapsed_seconds': time.monotonic() - start, 'results_judged': False}
    (output / 'diagnosis_summary.check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--job', type=Path, required=True)
    a = p.parse_args()
    aggregate(a.base, a.job)


if __name__ == '__main__':
    main()
