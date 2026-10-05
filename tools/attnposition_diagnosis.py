"""保存済みの候補・位置費用・回答だけを読む事後診断。模型は呼ばない。

selected_before_update（選びの一位）とR_used（発話の門を通った
採用定義）を分ける。研究者の正解・日は集計と候補区分だけに使う。
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import resource
import time

CONDITIONS = ('global_e01', 'position_e01', 'global_fixed1',
              'global_e05', 'position_e05', 'position_fixed1')
REASONS = ('missing_ancestor', 'definition_key_collision', 'scene_key_collision',
           'no_visible_position', 'queried_hidden_position', 'cycle')
SEAL_KEY = '[[[[[2,["relation","relation"]],0]]],[1,["entity"]]]'


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        yield from (json.loads(line) for line in f)


def public_parts(path):
    """巨大な既知ID一覧を展開せず、既に分離した公開候補の席だけ読む。"""
    decoder = json.JSONDecoder()
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            assert line.startswith('{"trial": ')
            trial, _ = decoder.raw_decode(line, len('{"trial": '))
            start = line.index('"candidates": ') + len('"candidates": ')
            candidates, _ = decoder.raw_decode(line, start)
            yield {'trial': trial, 'candidates': candidates}


def write_csv(path, rows, columns=None):
    rows = iter(rows)
    first = next(rows, None)
    columns = columns or list(first or {})
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'wt', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        if first is not None:
            writer.writerow(first)
        writer.writerows(rows)


def q_of(candidate):
    return Fraction(candidate['q_numerator'], candidate['q_denominator'])


def n3_order(candidate):
    return (-q_of(candidate), -candidate['n'], -candidate['registered_at'], candidate['R'])


def answer_key(payload):
    edge = payload['predicted_edge']
    return None if edge is None else (edge['predicate'], tuple(edge['arguments']))


def outcome(payload, truth):
    value = answer_key(payload)
    return 'abstain' if value is None else 'correct' if value == truth else 'wrong'


def silence_cause(payload):
    if payload['predicted_edge'] is not None:
        return 'answered'
    reason = payload['abstain_reason']
    return {'below_tau': 'below_speech_gate', 'below_threshold': 'below_structure_gate',
            'no_definition': 'no_candidate_definition', 'no_prototype': 'no_prototype',
            'no_gap_candidate': 'no_answer_at_visible_gap',
            'no_projectable_relation': 'no_projectable_or_fillable_answer',
            'ambiguous_projection': 'ambiguous_projection_U_or_H_tie_unknown'}.get(reason, 'unknown')


def seat_kind(seat, detail):
    if detail['reason'] is not None:
        return None
    state, name = seat['state'], detail['visible_name']
    if state == 'U':
        return 'U'
    if state == 'F':
        return 'F_match' if seat['predicate'] == name else 'F_mismatch'
    assert state == 'H'
    return 'H_present' if seat['history'].get(name, 0) > 0 else 'H_absent'


def describe(candidate, attention, mode):
    """記録したmの同じ加算順で費用を足す。照合・選び・学びは呼ばない。"""
    states = Counter(d['state'] for d in candidate['details'])
    used = [d for d in candidate['details'] if d['reason'] is None]
    reasons = Counter(d['reason'] for d in candidate['details'] if d['reason'] is not None)
    penalty = seal = other = 0.
    for key, m in sorted(candidate['m'][mode].items()):
        term = attention.get(key, 0.) * m
        penalty += term
        if key == SEAL_KEY:
            seal += term
        else:
            other += term
    q = q_of(candidate)
    log_q = math.log(q) if q > 0 else None
    return {'R': candidate['R'], 'seats_total': len(candidate['details']),
            'alive_F': states['F'], 'F': states['F'], 'H': states['H'], 'U': states['U'],
            'gate_FH_n': candidate['n'], 'm_counted': len(used),
            'm_numeric_zero': sum(d['m_' + mode] == 0 for d in used),
            'U_counted': sum(d['state'] == 'U' for d in used),
            'U_numeric_zero': sum(d['state'] == 'U' and d['m_' + mode] == 0 for d in used),
            **{'excluded_' + r: reasons[r] for r in REASONS},
            'penalty': penalty, 'penalty_seal': seal, 'penalty_other': other,
            'ln_Q': log_q, 'z': None if log_q is None else log_q - penalty,
            'speech_payload_R': candidate['payload']['R_used'],
            'silence_cause': silence_cause(candidate['payload']),
            'abstain_reason': candidate['payload']['abstain_reason']}


def diagnose(base, old_job, world, seed, output):
    assert world in (1, 2) and seed in range(1, 21)
    name = f'n3_w{world}_A_L50'
    featurepath = old_job / 'features' / name / f'seed{seed:03d}.features.jsonl.gz'
    runpath = old_job / 'runs' / name / f'seed{seed:03d}.attention.jsonl.gz'
    casepath = base / 'stageCD_doors_2026-10-05/cases' / name / f'seed{seed:03d}.cases.jsonl.gz'
    publicpath = old_job / 'input' / name / f'seed{seed:03d}.public.jsonl.gz'
    checkpath = old_job / 'runs' / name / f'seed{seed:03d}.replay.check.json'
    assert json.loads(checkpath.read_text())['passed']
    folder = output / name
    folder.mkdir(parents=True, exist_ok=True)
    check = folder / f'seed{seed:03d}.diagnosis.check.json'
    if check.exists():
        raise RuntimeError('既存の記録診断を重複しない')
    start = time.monotonic()
    changed, blank, healed = [], [], []
    census, zero_reasons, kind_n, kind_sum = Counter(), Counter(), Counter(), defaultdict(float)
    total = doors = 0
    for feature, frame, case, public in itertools.zip_longest(
            records(featurepath), records(runpath), records(casepath), public_parts(publicpath)):
        assert None not in (feature, frame, case, public)
        assert feature['trial'] == frame['trial'] == case['trial'] == public['trial'] == total
        total += 1
        if not feature['door_task']:
            continue
        doors += 1
        trial = feature['trial']
        truth = (case['truth'][0], tuple(case['truth'][1]))
        before = outcome(case['baseline'], truth)
        day = 'exception' if case['shop_cue'] == 'e' else 'normal'
        candidates = {c['R']: c for c in feature['candidates']}
        seats = {c['R']: {d['slot']: d for d in c['seats']} for c in public['candidates']}
        ranked = sorted((c for c in candidates.values() if q_of(c) > 0), key=n3_order)
        d0 = ranked[0] if ranked else None
        # 元の点の記録を並べるだけ。元の回答を再計算せず保存payloadと照合する。
        assert d0 is None or d0['payload'] == case['baseline']
        good = [c for c in ranked if answer_key(c['payload']) == truth]
        assert len(good) == case['actual_correct_candidates']
        for condition in ('baseline', *CONDITIONS):
            mode = 'global' if condition.startswith('global') or condition == 'baseline' else 'position'
            result = frame['conditions'].get(condition)
            d1 = d0 if result is None else candidates.get(result['selected_before_update'])
            payload = case['baseline'] if result is None else result['answer_before_update']
            assert d1 is None or d1['payload'] == payload
            if payload['R_used'] is None:
                blank.append({'world': world, 'seed': seed, 'trial': trial, 'condition': condition,
                              'day': day, 'baseline_outcome': before, 'outcome': outcome(payload, truth),
                              'winning_R': None if d1 is None else d1['R'],
                              'silence_cause': silence_cause(payload), 'abstain_reason': payload['abstain_reason'],
                              'support_at_adoption': payload['support_at_adoption'],
                              'gate_FH_n': None if d1 is None else d1['n']})
            if result is None:
                continue
            attention = result['a_before']
            after = outcome(payload, truth)
            for candidate in candidates.values():
                scopes = ['all']
                if d1 is not None and candidate['R'] == d1['R']:
                    scopes.append('selected')
                if answer_key(candidate['payload']) == truth:
                    scopes.append('correct_above_gate')
                for detail in candidate['details']:
                    for scope in scopes:
                        census[condition, scope, 'denominator_all_seats'] += 1
                        census[condition, scope, 'denominator_non_door_seats'] += detail['reason'] != 'queried_hidden_position'
                        census[condition, scope, 'missing_ancestor'] += detail['reason'] == 'missing_ancestor'
                        zero_reasons[condition, scope, detail['state'], detail['reason'] or 'counted'] += 1
                    kind = seat_kind(seats[candidate['R']][detail['slot']], detail)
                    if kind is not None:
                        kind_n[condition, kind] += 1
                        kind_sum[condition, kind] += detail['m_' + mode]
            selected_change = answer_key(payload) != answer_key(case['baseline'])
            included = selected_change and (day == 'exception' or before == 'correct' and after in ('wrong', 'abstain'))
            if included:
                row = {'world': world, 'seed': seed, 'trial': trial, 'condition': condition,
                       'shop': case['shop_type'], 'day': day, 'baseline_outcome': before, 'outcome': after}
                if d0 is None or d1 is None:
                    row.update(record_status='unknown_candidate')
                else:
                    old, new = describe(d0, attention, mode), describe(d1, attention, mode)
                    row.update(record_status='complete')
                    row.update({'d0_' + k: v for k, v in old.items()})
                    row.update({'d1_' + k: v for k, v in new.items()})
                    delta, other = old['penalty'] - new['penalty'], old['penalty_other'] - new['penalty_other']
                    row.update(d1_fewer_counted_seats=new['m_counted'] < old['m_counted'],
                               penalty_difference_d0_minus_d1=delta,
                               penalty_difference_seal=old['penalty_seal'] - new['penalty_seal'],
                               penalty_difference_other=other,
                               nonseal_signed_fraction=None if delta == 0 else other / delta,
                               highest_Q_correct_R=None if not good else good[0]['R'],
                               d1_is_highest_Q_correct=bool(good) and d1['R'] == good[0]['R'])
                changed.append(row)
            if world == 2 and day == 'exception' and before == 'wrong' and good and after == 'correct':
                healed.append({'world': world, 'seed': seed, 'trial': trial, 'condition': condition,
                               'd0_R': d0['R'], 'd1_R': d1['R'], 'highest_Q_correct_R': good[0]['R'],
                               'd1_is_highest_Q_correct': d1['R'] == good[0]['R'],
                               'correct_candidates_above_gate': len(good)})
    assert total == 1740
    stem = f'seed{seed:03d}'
    columns = list(dict.fromkeys(k for r in changed for k in r))
    write_csv(folder / f'{stem}.changed.csv.gz', changed, columns or ['world', 'seed', 'trial'])
    write_csv(folder / f'{stem}.blank.csv.gz', blank)
    write_csv(folder / f'{stem}.healed.csv', healed, ['world', 'seed', 'trial', 'condition', 'd0_R', 'd1_R', 'highest_Q_correct_R', 'd1_is_highest_Q_correct', 'correct_candidates_above_gate'])
    cr = [{'world': world, 'seed': seed, 'condition': c, 'scope': scope,
           **{k: census[c, scope, k] for k in ('denominator_all_seats', 'denominator_non_door_seats', 'missing_ancestor')}}
          for c in CONDITIONS for scope in ('all', 'selected', 'correct_above_gate')]
    write_csv(folder / f'{stem}.census.csv', cr)
    kr = [{'world': world, 'seed': seed, 'condition': c, 'seat_kind': k, 'count': kind_n[c, k], 'm_sum': kind_sum[c, k],
           'm_mean': kind_sum[c, k] / kind_n[c, k] if kind_n[c, k] else None}
          for c in CONDITIONS for k in ('F_match', 'F_mismatch', 'H_present', 'H_absent', 'U')]
    write_csv(folder / f'{stem}.seat_kinds.csv', kr)
    zr = [{'world': world, 'seed': seed, 'condition': c, 'scope': sc, 'state': st, 'reason': re, 'count': n}
          for (c, sc, st, re), n in sorted(zero_reasons.items())]
    write_csv(folder / f'{stem}.zero_reasons.csv', zr)
    result = {'passed': True, 'world': world, 'seed': seed, 'trials': total, 'doors': doors,
              'changed_pairs': len(changed), 'blank_records': len(blank),
              'elapsed_seconds': time.monotonic() - start,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'model_called': False, 'selection_or_learning_called': False,
              'researcher_labels_only_post_hoc': True,
              'inputs': [str(p) for p in (featurepath, runpath, casepath, publicpath, checkpath)]}
    check.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--old-job', type=Path, required=True)
    p.add_argument('--world', type=int, choices=(1, 2), required=True)
    p.add_argument('--seed', type=int, choices=range(1, 21), required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    diagnose(a.base, a.old_job, a.world, a.seed, a.output)


if __name__ == '__main__':
    main()
