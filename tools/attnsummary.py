"""段C・D：全関門合格後の固定記憶の三腕の表と記録だけを作る。

段Bに保存したオンライン回答・L・重みを読む。学習の再実行はしない。
段Dは各種の最後の重みで同じ候補を選ぶだけ。ドア名だけ1へ戻し、
正規化せず、記憶・注意の更新・既存の乱数の消費は一切しない。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

W = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(W/'tools'), str(W)]
import attndoor as D
import attnmetrics as M
import attnsel as A
from attnreplay_doors import response_bytes

VARIANTS = [(0, 5., .05)] + [(a, b, e) for a in (1, 2) for b in (1., 5., 10.) for e in (.01, .05, .1)]
GRID = [(b, e) for b in (1., 5., 10.) for e in (.01, .05, .1)]
OUTCOMES = ('correct', 'wrong', 'silent')
CLASSES = ('normal_door', 'exception_door', 'other_name', 'silent')
PARAM = ('world', 'seed', 'arm', 'beta', 'eta')


def read_jsonl(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        yield from (json.loads(line) for line in stream)


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def table_rows(counter, keys, values):
    for key, counts in sorted(counter.items()):
        row = dict(zip(keys, key))
        total = sum(counts[v] for v in values)
        row.update(total=total, **{v: counts[v] for v in values})
        row.update({v+'_rate': counts[v]/total if total else None for v in values})
        yield row


def response_rows(counter, keys):
    for row in table_rows(counter, keys, CLASSES):
        key = tuple(row[k] for k in keys)
        counts = counter[key]
        row.update(hold=counts['hold'], hold_b=counts['hold_b'],
                   hold_rate=counts['hold']/row['total'] if row['total'] else None,
                   hold_b_rate=counts['hold_b']/row['total'] if row['total'] else None,
                   normal_exception_same_predicate=row['world'] == 1,
                   exception_column_applicable=row['world'] == 2)
        # 世界1の独立な例外ドアは存在せず、観測0件と混同しない。
        if row['world'] == 1:
            row['exception_door'] = row['exception_door_rate'] = None
        yield row


def signal_rows(responses, keys):
    prefix_keys = keys[:-1]  # 最後の列がday
    prefixes = {key[:-1] for key in responses}
    for prefix in sorted(prefixes):
        row = dict(zip(prefix_keys, prefix))
        if row['world'] != 2:
            continue
        n, e = responses.get(prefix+('normal',), Counter()), responses.get(prefix+('exception',), Counter())
        h, miss, fa, cr = e['exception_door'], e['normal_door'], n['exception_door'], n['normal_door']
        row.update(hit=h, miss=miss, false_alarm=fa, correct_rejection=cr,
                   excluded_signal_silence=e['silent'], excluded_signal_other=e['other_name'],
                   excluded_noise_silence=n['silent'], excluded_noise_other=n['other_name'])
        row.update(M.dprime_cells(h, miss, fa, cr))
        yield row


def summarize_seed(world, seed, stageB, cases, output):
    if world not in (1, 2) or seed not in range(1, 21):
        raise ValueError('両世界・種1〜20だけ')
    root_name = f'n3_w{world}_A_L50'
    folder = output/root_name/f'seed{seed:03d}'
    if folder.exists():
        raise RuntimeError('既存の集計を上書きしない')
    folder.mkdir(parents=True)
    frames = list(read_jsonl(stageB/'frozen'/root_name/f'seed{seed:03d}.frozen.jsonl.gz'))
    metadata = list(read_jsonl(cases/root_name/f'seed{seed:03d}.cases.jsonl.gz'))
    assert len(frames) == len(metadata) == 1740
    for t, (frame, case) in enumerate(zip(frames, metadata)):
        assert (frame['world'], frame['seed'], frame['trial']) == (world, seed, t)
        assert (case['world'], case['seed'], case['trial']) == (world, seed, t)
    decoded = {t: tuple(D.decode_candidate(c) for c in frame['candidates'])
               for t, frame in enumerate(frames) if frame['door_task']}
    responses, outcomes, changes, errors, reasons, losses = (defaultdict(Counter) for _ in range(6))
    predictions, snapshots, first_seen, seen = {}, [], [], set()
    for frame in frames:
        for name in frame['public_names']:
            if name not in seen:
                first_seen.append({'world': world, 'seed': seed, 'name': name, 'trial': frame['trial'], 'when': 'before_prediction'})
                seen.add(name)
        if frame['feedback']['f_fired']:
            name = frame['feedback']['feedback_content']['predicate']
            if name not in seen:
                first_seen.append({'world': world, 'seed': seed, 'name': name, 'trial': frame['trial'], 'when': 'after_disclosure'})
                seen.add(name)
    started = time.monotonic()
    check = {'world': world, 'seed': seed, 'trial_records': 0, 'variants': len(VARIANTS),
             'door_trials': len(decoded), 'distinction_loss_to_correct': 0,
             'non_door_answer_mismatches': 0, 'analysis_changed_inputs': False,
             'model_updated': False, 'attention_updated': False, 'existing_rng_consumed': False,
             'task_instruction_assumption': '本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う',
             'stageD_weight_time': 'each_seed_final_after_last_trial', 'stageD_normalized': False,
             'mismatch': None, 'phase3_started': False}
    try:
        with gzip.open(folder/'trial_metrics.csv.gz', 'wt', encoding='utf-8', newline='') as lossfile, gzip.open(folder/'votes.jsonl.gz', 'wt', encoding='utf-8') as votes:
            lossfields = (*PARAM, 'trial', 'shop', 'day', 'door_task', 'outcome', 'availability', 'actual_correct_candidates', 'f_realized', 'f_fired', 'updated', 'reason', 'L', 'L_recorded', 'L_source')
            losswriter = csv.DictWriter(lossfile, fieldnames=lossfields)
            losswriter.writeheader()
            for arm, beta, eta in VARIANTS:
                param = (world, seed, arm, beta, eta)
                stem = f'seed{seed:03d}.arm{arm}.b{beta:g}_e{eta:g}'
                source = stageB/'replay'/root_name/(stem+'.attn.jsonl.gz')
                rows = read_jsonl(source)
                answers = []
                for t, row in enumerate(rows):
                    assert t < 1740 and row['trial'] == t and row['world'] == world and row['seed'] == seed
                    frame, case = frames[t], metadata[t]
                    truth = case['truth'][0], tuple(case['truth'][1])
                    response = row['answer_before_update']
                    answers.append(response)
                    actual = M.outcome(response, truth)
                    day, shop = ('exception' if case['shop_cue'] == 'e' else 'normal'), case['shop_type']
                    task = 'door' if frame['door_task'] else 'non_door'
                    loss = row['L']
                    loss_source = 'recorded' if loss is not None else 'undefined'
                    # 注意なしにも、開示されたドア課題の診断用Lを表示する。
                    # 更新は呼ばず、非開示ではこの計算もしない。
                    if arm == 0 and frame['door_task'] and row['f_fired']:
                        cs = M.ranked_candidates(decoded[t], row['weights_before'], arm)
                        mask = tuple(c.answer == truth for c in cs)
                        if any(mask):
                            loss = A.loss_gradient(cs, row['weights_before'], mask, beta)[0]
                            loss_source = 'posthoc_no_attention_beta5'
                    reasons[param+(task,)][row['reason']] += 1
                    strata = ['all']
                    if frame['door_task']:
                        strata += [case['availability'], 'gated_correct_exists' if case['actual_correct_candidates'] else 'gated_correct_absent']
                        response_key = param+(shop, day)
                        category = M.response_class(response, case['normal_door_predicate'], case['exception_door_predicate'])
                        responses[response_key][category] += 1
                        key = M.answer_key(response)
                        if key is not None and key[0] in D.DOOR_NAMES:
                            responses[response_key][key[0]] += 1
                        if not case['actual_correct_candidates'] and actual == 'correct':
                            check['distinction_loss_to_correct'] += 1
                            raise RuntimeError('正解の実候補が無い試行から正解が出た。実装・分類を調べる')
                        if case['baseline_outcome'] == 'wrong':
                            why = 'selection_error' if case['actual_correct_candidates'] else 'distinction_loss'
                            errors[param+(shop, day, why)][actual] += 1
                        result = M.vote(frame, decoded[t], row['weights_before'], arm)
                        votes.write(json.dumps({**dict(zip(PARAM, param)), 'trial': t, 'vote': result,
                            'vote_outcome': M.outcome(result['payload'], truth), 'used_to_answer': False}, ensure_ascii=False)+'\n')
                    elif response_bytes(response) != response_bytes(frame['baseline']):
                        check['non_door_answer_mismatches'] += 1
                        raise RuntimeError('段Cで非ドアの回答が元と違う')
                    for stratum in strata:
                        outcomes[param+(task, shop, day, stratum)][actual] += 1
                    losswriter.writerow({**dict(zip(PARAM, param)), 'trial': t, 'shop': shop, 'day': day,
                        'door_task': frame['door_task'], 'outcome': actual, 'availability': case['availability'],
                        'actual_correct_candidates': case['actual_correct_candidates'],
                        **{k: row[k] for k in ('f_realized', 'f_fired', 'updated', 'reason')},
                        'L': loss, 'L_recorded': row['L'], 'L_source': loss_source})
                    if loss is not None:
                        cell = losses[param+((t//100)*100, shop, day)]
                        cell['defined_count'] += 1
                        cell['sum_L'] += loss
                        cell['updated_count'] += row['updated']
                    if t == 0 or (t+1)%100 == 0 or t == 1739:
                        for name in sorted(row['weights_after']):
                            snapshots.append({**dict(zip(PARAM, param)), 'trial': t, 'name': name,
                                'weight_before': row['weights_before'].get(name, 1.), 'weight_after': row['weights_after'][name]})
                    check['trial_records'] += 1
                assert len(answers) == 1740
                predictions[(arm, beta, eta)] = answers
        for beta, eta in GRID:
            arms = {0: predictions[(0, 5., .05)], 1: predictions[(1, beta, eta)], 2: predictions[(2, beta, eta)]}
            for source_arm, target_arm in ((0, 1), (0, 2), (1, 2)):
                for t, case in enumerate(metadata):
                    truth = case['truth'][0], tuple(case['truth'][1])
                    day, shop = ('exception' if case['shop_cue'] == 'e' else 'normal'), case['shop_type']
                    task = 'door' if case['door_task'] else 'non_door'
                    left, right = M.outcome(arms[source_arm][t], truth), M.outcome(arms[target_arm][t], truth)
                    changes[(world, seed, beta, eta, source_arm, target_arm, task, shop, day)][(left, right)] += 1
        response_fields = (*PARAM, 'shop', 'day', 'total', *CLASSES, *(v+'_rate' for v in CLASSES),
                           'hold', 'hold_b', 'hold_rate', 'hold_b_rate', 'normal_exception_same_predicate', 'exception_column_applicable')
        write_csv(folder/'responses.csv', response_rows(responses, (*PARAM, 'shop', 'day')), response_fields)
        count_fields = (*PARAM, 'task', 'shop', 'day', 'availability', 'total', *OUTCOMES, *(v+'_rate' for v in OUTCOMES))
        write_csv(folder/'outcomes.csv', table_rows(outcomes, (*PARAM, 'task', 'shop', 'day', 'availability'), OUTCOMES), count_fields)
        write_csv(folder/'original_errors.csv', table_rows(errors, (*PARAM, 'shop', 'day', 'error_type'), OUTCOMES),
                  (*PARAM, 'shop', 'day', 'error_type', 'total', *OUTCOMES, *(v+'_rate' for v in OUTCOMES)))
        write_csv(folder/'transitions.csv', transition_rows(changes, ('world', 'seed', 'beta', 'eta', 'source_arm', 'target_arm', 'task', 'shop', 'day')),
                  ('world', 'seed', 'beta', 'eta', 'source_arm', 'target_arm', 'task', 'shop', 'day', 'before', 'after', 'count'))
        write_csv(folder/'weights_100_trials.csv', snapshots, (*PARAM, 'trial', 'name', 'weight_before', 'weight_after'))
        write_csv(folder/'first_seen.csv', first_seen, ('world', 'seed', 'name', 'trial', 'when'))
        write_csv(folder/'update_reasons.csv', ({**dict(zip((*PARAM, 'task'), key)), 'reason': reason, 'count': count}
                  for key, counts in sorted(reasons.items()) for reason, count in sorted(counts.items())), (*PARAM, 'task', 'reason', 'count'))
        write_csv(folder/'loss_100_trials.csv', ({**dict(zip((*PARAM, 'bin_start', 'shop', 'day'), key)),
            'defined_count': cell['defined_count'], 'updated_count': cell['updated_count'], 'sum_L': cell['sum_L'],
            'mean_L': cell['sum_L']/cell['defined_count']} for key, cell in sorted(losses.items())),
            (*PARAM, 'bin_start', 'shop', 'day', 'defined_count', 'updated_count', 'sum_L', 'mean_L'))
        signal = list(signal_rows(responses, (*PARAM, 'shop', 'day')))
        signal_fields = (*PARAM, 'shop', 'hit', 'miss', 'false_alarm', 'correct_rejection', 'excluded_signal_silence', 'excluded_signal_other',
            'excluded_noise_silence', 'excluded_noise_other', 'dprime', 'criterion', 'hit_rate', 'false_alarm_rate', 'adjusted_hit_rate',
            'adjusted_false_alarm_rate', 'corrected', 'undefined_reason')
        write_csv(folder/'signal_detection.csv', signal, signal_fields)
        assert check['trial_records'] == 1740*19
        check['stageD_trial_records'] = 0
        check['passed'] = True
    except BaseException as error:
        check['mismatch'] = {'error': repr(error)}
        check['passed'] = False
        raise
    finally:
        check['elapsed_seconds'] = time.monotonic()-started
        (folder/'check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2)+'\n')
    return check


def intervene_seed(world, seed, stageB, cases, output):
    """全40種の段Cの集計後にだけ、腕1の答える時だけの介入をする。"""
    marker = json.loads((output/'all_C.json').read_text())
    assert marker['passed'] and marker['seeds'] == 40
    root_name = f'n3_w{world}_A_L50'
    folder = output/root_name/f'seed{seed:03d}'
    check_path = folder/'D_check.json'
    if check_path.exists() or (folder/'stageD.jsonl.gz').exists():
        raise RuntimeError('既存の段Dを上書きしない')
    frames = list(read_jsonl(stageB/'frozen'/root_name/f'seed{seed:03d}.frozen.jsonl.gz'))
    metadata = list(read_jsonl(cases/root_name/f'seed{seed:03d}.cases.jsonl.gz'))
    assert len(frames) == len(metadata) == 1740
    decoded = {t: tuple(D.decode_candidate(c) for c in f['candidates']) for t, f in enumerate(frames) if f['door_task']}
    predictions = {}
    for beta, eta in GRID:
        p = stageB/'replay'/root_name/f'seed{seed:03d}.arm1.b{beta:g}_e{eta:g}.attn.jsonl.gz'
        predictions[(1, beta, eta)] = [r['answer_before_update'] for r in read_jsonl(p)]
        assert len(predictions[(1, beta, eta)]) == 1740
    started = time.monotonic()
    check = {'world': world, 'seed': seed, 'model_updated': False, 'attention_updated': False,
             'existing_rng_consumed': False, 'reset_normalized': False,
             'weight_time': 'each_seed_final_after_last_trial', 'mismatch': None,
             'task_instruction_assumption': '本人にドア課題の指示が伝えられるとみなしheld_out_is_doorを使う'}
    try:
        # 段D：各種の最後の重みを固定。実際の学習・記憶へ書き戻さない。
        dchanges = defaultdict(Counter)
        with gzip.open(folder/'stageD.jsonl.gz', 'wt', encoding='utf-8') as stream:
            for beta, eta in GRID:
                stem = f'seed{seed:03d}.arm1.b{beta:g}_e{eta:g}'
                summary = json.loads((stageB/'replay'/root_name/(stem+'.check.json')).read_text())
                final = summary['weights_final']
                reset = {**final, **dict.fromkeys(D.DOOR_NAMES, 1.)}
                input_before = json.dumps(final, sort_keys=True)
                for t, cs in decoded.items():
                    frame, case = frames[t], metadata[t]
                    truth = case['truth'][0], tuple(case['truth'][1])
                    full, full_R = M.static_answer(frame, cs, final, 1)
                    changed, reset_R = M.static_answer(frame, cs, reset, 1)
                    online = predictions[(1, beta, eta)][t]
                    shop, day = case['shop_type'], ('exception' if case['shop_cue'] == 'e' else 'normal')
                    for pair, before in (('final_all_to_reset', full), ('online_to_final_reset', online)):
                        left, right = M.outcome(before, truth), M.outcome(changed, truth)
                        dchanges[(world, seed, beta, eta, pair, shop, day)][(left, right)] += 1
                    stream.write(json.dumps({'world': world, 'seed': seed, 'beta': beta, 'eta': eta, 'trial': t,
                        'final_all_names': full, 'final_door_reset': changed, 'online_arm1': online,
                        'full_selected_R': full_R, 'reset_selected_R': reset_R,
                        'full_Q': None if full_R is None else str(next(c for c in cs if c.definition.name == full_R).terms.value(final)),
                        'reset_Q': None if reset_R is None else str(next(c for c in cs if c.definition.name == reset_R).terms.value(reset)),
                        'reset_normalized': False, 'learning_changed': False, 'memory_changed': False}, ensure_ascii=False)+'\n')
                assert input_before == json.dumps(final, sort_keys=True)
                (folder/(stem+'.D_weights.json')).write_text(json.dumps({'final': final, 'door_reset': reset,
                    'final_trial': 1739, 'normalized': False}, ensure_ascii=False, indent=2)+'\n')
        for frame in frames:
            if not frame['door_task']:
                assert response_bytes(M.static_answer(frame, (), final, 1)[0]) == response_bytes(frame['baseline'])
                assert response_bytes(M.static_answer(frame, (), reset, 1)[0]) == response_bytes(frame['baseline'])
        write_csv(folder/'stageD_transitions.csv', transition_rows(dchanges, ('world', 'seed', 'beta', 'eta', 'pair', 'shop', 'day')),
                  ('world', 'seed', 'beta', 'eta', 'pair', 'shop', 'day', 'before', 'after', 'count'))
        check.update(passed=True, trial_records=len(decoded)*9)
    except BaseException as error:
        check.update(passed=False, mismatch={'error': repr(error)})
        raise
    finally:
        check['elapsed_seconds'] = time.monotonic()-started
        check_path.write_text(json.dumps(check, ensure_ascii=False, indent=2)+'\n')
    return check


def transition_rows(counter, keys):
    for key, counts in sorted(counter.items()):
        for before, after in itertools.product(OUTCOMES, repeat=2):
            yield {**dict(zip(keys, key)), 'before': before, 'after': after, 'count': counts[(before, after)]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument('--summarize-fixed-memory', action='store_true')
    action.add_argument('--intervene-final-door-weights', action='store_true')
    ap.add_argument('--world', type=int, choices=(1, 2), required=True)
    ap.add_argument('--seed', type=int, choices=range(1, 21), required=True)
    ap.add_argument('--stageB', type=Path, required=True)
    ap.add_argument('--cases', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    gate = json.loads((args.stageB/'all_door_gates.json').read_text())
    if not all(gate[f'B{i}_passed'] for i in range(1, 6)):
        raise RuntimeError('段B全ての合格前に成績を読まない')
    check = json.loads((args.cases/f'n3_w{args.world}_A_L50'/f'seed{args.seed:03d}.case.check.json').read_text())
    assert check['full_census'] and not check['mismatch'] and not check['memory_state_hash_changes']
    function = intervene_seed if args.intervene_final_door_weights else summarize_seed
    print(json.dumps(function(args.world, args.seed, args.stageB, args.cases, args.output), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
