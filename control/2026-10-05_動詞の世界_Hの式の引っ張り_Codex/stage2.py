"""追加承認：有回答と席が記録された黙りだけを、既存30本から数える。"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path
import audit
from abm.world import opaque_id

OUT = audit.OUT / 'stage2'
CATEGORIES = ('F', 'H-一致', 'H-引っ張り', 'H-黙り', 'U', 'その他', '席が未特定の黙り')


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def pool(d, rr, hist, hop):
    ids = {r['relation']['relation_id'] for r in d['constituents']}
    higher = any(a in ids for a in rr['relation']['arguments'])
    return sorted(p for p in hist if (p in hop) == higher)


def majority(d, rr, state, hop):
    hist = audit.seat(d, rr, state)[1]
    names = pool(d, rr, hist, hop)
    maximum = max((hist[p] for p in names), default=0)
    winners = [p for p in names if hist[p] == maximum]
    return winners[0] if len(winners) == 1 else None, winners


def main():
    began = time.monotonic()
    OUT.mkdir(exist_ok=True)
    old_gate = json.loads((audit.OUT/'gate_result_refined.json').read_text())
    assert old_gate['runs'] == 30 and old_gate['gate1_mismatch_rows'] == 0
    assert old_gate['training_answer_mismatches'] == 0
    assert old_gate['counts'].get('independent_H_mismatches', 0) == 0
    plan = json.loads((audit.OLD/'plan.json').read_text())
    assert len(plan['runs']) == 30
    assert {(r['arm'], r['U'], r['seed']) for r in plan['runs']} == {
        (a, u, s) for a in ('A', 'C', 'D') for u in ('global', 'abstain') for s in range(1, 6)}
    hop = audit.higher_order_predicates(audit.load_seed(audit.SOURCE/'tools/verb/U-011_seed_verb.json'))
    expected_manifest = {r['path']: r['sha256'] for r in csv.DictReader((audit.OUT/'input_manifest.csv').open())}
    inputs, per_run, snapshots = [], [], []
    rate_counts, category_counts, breakdown, changes, transitions, unidentified = (defaultdict(Counter) for _ in range(6))
    checks = Counter()
    expected = {(r['arm'], r['U'], int(r['bin']), r['verb']): (int(r['queries']), int(r['REG']))
                for r in csv.DictReader((audit.OLD/'aggregate/overregularization_per_verb.csv').open())}
    reproduced = defaultdict(Counter)
    columns = ['run', 'arm', 'U', 'seed', 'phase', 't', 'bin', 'verb', 'verb_class', 'truth',
               'answer', 'abstain_reason', 'R', 'R_born', 'slot', 'seat_state', 'category', 'subtype',
               'classification', 'history', 'history_pool', 'history_maxima', 'majority_answer', 'formula_answer',
               'formula_status', 'weights', 'p_hat_total', 'p_hat_candidate_counts', 'counterfactual_answer',
               'counterfactual_scope', 'counterfactual_change', 'actual_correct', 'counterfactual_correct', 'arguments_correct']
    with (OUT/'past_questions.csv').open('w', newline='') as ef:
        writer = csv.DictWriter(ef, columns)
        writer.writeheader()
        for index, run in enumerate(plan['runs'], 1):
            label, seed = run['label'], run['seed']
            root = audit.OLD/label/'run'
            ledger = next((root/'ledgers/cells').glob(f'*/seed{seed:03d}.jsonl.gz'))
            side = root/'side'/ledger.parent.name
            ap, mp, pp = (side/f'seed{seed:03d}.{ext}' for ext in ('answers.csv', 'ambig.csv', 'probe.jsonl'))
            cp = audit.OLD/label/'analysis/cases.jsonl.gz'
            for path in (ledger, ap, mp, pp, cp):
                if not path.exists():
                    assert path == mp
                    continue
                fp = audit.fingerprint(path)
                if fp['path'] in expected_manifest:
                    assert fp['sha256'] == expected_manifest[fp['path']], fp['path']
                inputs.append({'run': label, **fp})
            answers = {int(r['trial']): r for r in csv.DictReader(ap.open())}
            ambig = {int(r['trial']): r for r in csv.DictReader(mp.open())} if mp.exists() else {}
            cases = {r['trial']: r for r in map(json.loads, gzip.open(cp, 'rt'))}
            probes = defaultdict(list)
            for p in map(json.loads, pp.open()):
                assert p['verb_probe'] == 'past' and p['level'] == 1
                probes[p['t']].append(p)
            past_ids = {opaque_id(seed, t, 'relation:tree:0.0.0') for t in range(5000)}
            probe_args = [opaque_id(f'probe\x1f{seed}', 0, 'entity:'+role) for role in ('a', 'b')]
            tally = Counter()

            def emit(phase, t, verb, cls, truth, answer, args_ok, reason, d, rr, state, recorded=None, known_no_answer_seat=False):
                b = t//500 if phase == 'training' else min((t-1)//500, 9)
                e = {'run': label, 'arm': run['arm'], 'U': run['U'], 'seed': seed,
                     'phase': phase, 't': t, 'bin': b, 'verb': verb, 'verb_class': cls,
                     'truth': truth, 'answer': answer, 'abstain_reason': reason,
                     'R': d['name'] if d else None, 'R_born': d['registered_at'] if d else None,
                     'slot': rr['slot_index'] if rr else None, 'seat_state': None,
                     'category': 'その他', 'subtype': reason or '', 'classification': '',
                     'counterfactual_answer': answer, 'counterfactual_scope': 'unchanged',
                     'counterfactual_change': False, 'actual_correct': bool(answer is not None and truth is not None and answer == truth and args_ok),
                     'arguments_correct': args_ok if answer is not None else None}
                if d and rr:
                    st, hist = audit.seat(d, rr, state)
                    e.update(seat_state=st, history=compact(hist), history_pool=compact(pool(d, rr, hist, hop)))
                    if st == 'H':
                        calc, weights, status = audit.formula(d, rr, state, hop, 1.0)
                        maj, tops = majority(d, rr, state, hop)
                        e.update(history_maxima=compact(tops), majority_answer=maj, formula_answer=calc,
                                 formula_status=status, weights=compact(weights), p_hat_total=state['p_hat']['total'],
                                 p_hat_candidate_counts=compact({p: state['p_hat']['counts'].get(p, 0) for p in weights}))
                        if answer is not None:
                            assert calc == answer, (label, phase, t, verb, calc, answer)
                            tally['H_answer_checked'] += 1
                            e['category'] = 'H-一致' if maj == answer else 'H-引っ張り'
                            e['subtype'] = 'unique_majority' if len(tops) == 1 else 'history_maximum_tie'
                            e.update(counterfactual_answer=maj, counterfactual_scope='answered_H')
                        else:
                            if status == 'tie':
                                assert recorded and recorded['held_tied'] == '1' and not recorded['held_answer']
                                e.update(category='H-黙り', subtype='formula_tie', counterfactual_answer=maj,
                                         counterfactual_scope='identified_H_silence_lower_bound')
                            else:
                                e.update(category='その他', subtype='identified_H_silence:'+reason,
                                         counterfactual_scope='identified_H_silence_blocked_elsewhere')
                    elif st == 'F':
                        if answer is not None:
                            assert answer == rr['relation']['predicate']
                            e.update(category='F', subtype='fixed')
                        else:
                            e.update(category='その他', subtype='identified_F_silence:'+reason)
                    elif st == 'U':
                        e.update(category='U', subtype='answer' if answer is not None else reason)
                elif d:
                    if known_no_answer_seat:
                        e.update(category='その他', subtype='no_projectable_relation')
                    else:
                        assert answer is None
                        e.update(category='席が未特定の黙り', subtype=reason)
                else:
                    assert answer is None
                    e.update(category='その他', subtype=reason or 'no_used_definition')
                if cls == 'irregular' and answer == 'REG':
                    if phase == 'training':
                        case = cases[t]
                        assert case['verb'] == verb
                        assert case['classification'] in ('selection_error', 'distinction_loss')
                        e['classification'] = case['classification']
                        tally['joined_existing_classification'] += 1
                    else:
                        e['classification'] = 'not_recorded_probe'
                cf = e['counterfactual_answer']
                e['counterfactual_change'] = cf != answer
                # 置換は既存の写像・引数を固定。既知の黙りからの出力は局所の席の答えの下限。
                e['counterfactual_correct'] = (bool(cf is not None and truth is not None and cf == truth and args_ok)
                                               if answer is not None else None)
                key = (run['arm'], run['U'], seed, phase, b, verb, cls)
                c = rate_counts[key]
                c['queries'] += 1
                c['answered' if answer is not None else 'abstain'] += 1
                c['correct'] += int(e['actual_correct'])
                c['REG'] += int(cls == 'irregular' and answer == 'REG')
                c['other'] += int(answer is not None and not e['actual_correct'] and not (cls == 'irregular' and answer == 'REG'))
                c['counterfactual_answered_scope'] += int(e['counterfactual_scope'] == 'answered_H')
                c['counterfactual_correct'] += int(e['counterfactual_correct'] is True)
                c['counterfactual_REG'] += int(cls == 'irregular' and cf == 'REG' and answer is not None)
                category_counts[(*key, e['category'])]['queries'] += 1
                category_counts[(*key, e['category'])]['answered'] += int(answer is not None)
                if cls == 'irregular' and answer == 'REG':
                    breakdown[(*key, e['category'], e['subtype'], e['classification'])]['REG'] += 1
                if e['category'] == '席が未特定の黙り':
                    unidentified[(run['arm'], run['U'], seed, phase, b, reason)]['count'] += 1
                ck = (*key, e['category'], e['subtype'])
                cc = changes[ck]
                cc['queries'] += 1
                cc['changed'] += int(e['counterfactual_change'])
                cc['overREG_to_correct'] += int(cls == 'irregular' and answer == 'REG' and e['counterfactual_correct'] is True)
                cc['correct_to_wrong'] += int(e['actual_correct'] and cf is not None and not e['counterfactual_correct'])
                cc['correct_to_silence'] += int(e['actual_correct'] and cf is None)
                cc['regular_changed'] += int(cls == 'regular' and e['counterfactual_change'])
                cc['silence_to_seat_answer_lower_bound'] += int(answer is None and cf is not None)
                if e['seat_state'] == 'H' and answer is not None:
                    before = e.get('majority_answer') or 'TIE'+e['history_maxima']
                    transitions[(*key, e['category'], e['subtype'], before, answer)]['count'] += 1
                tally[phase+':queries'] += 1
                tally[phase+':'+e['category']] += 1
                tally[phase+':answered'] += int(answer is not None)
                if phase == 'training' and cls == 'irregular':
                    reproduced[(run['arm'], run['U'], b, verb)].update(queries=1, REG=int(answer == 'REG'))
                writer.writerow(e)

            state = None
            with gzip.open(ledger, 'rt') as f:
                header = json.loads(next(f))
                assert header['run_seed'] == seed and header['trial_count'] == 5000 and header['arm_local_lambda'] == 1.0
                for t, line in enumerate(f):
                    row = json.loads(line)
                    assert row['prediction_order'] == t
                    if row['held_out_is_past']:
                        pe = row.get('predicted_edge')
                        rec = answers.get(t) if pe else ambig.get(t)
                        d = state['definitions'][row['R_used']] if row.get('R_used') else None
                        slot = rec.get('slot' if pe else 'held_slot') if rec else None
                        rr = next(r for r in d['constituents'] if r['slot_index'] == int(slot)) if d and slot not in (None, '') else None
                        if rr:
                            assert audit.seat(d, rr, state)[0] == rec['seat_state' if pe else 'held_state']
                        if pe:
                            assert d and rr and rec['pred'] == pe['predicate'] and rec['R'] == d['name']
                            rid = pe['relation_id']
                            assert rid in ('sme_projection__'+rr['relation']['relation_id'],
                                           f"filling__{d['name']}__{rr['slot_index']}__{rr['registered_at']}")
                        args_ok = bool(pe and pe['arguments'] == row['held_out_content']['arguments'])
                        emit('training', t, row['verb_name'], row['verb_class'], row['correct_past'],
                             pe['predicate'] if pe else None, args_ok, row['abstain_reason'], d, rr, state, rec,
                             known_no_answer_seat=(not pe and row['abstain_reason'] == 'no_projectable_relation' and not row['candidate_distribution']))
                    snap = row['state_snapshot']
                    state = snap['value'] if snap['kind'] == 'full' else audit._apply(state, snap['changes'])
                    if probes.get(t+1):
                        assert hashlib.sha256(audit._json_bytes(state)).hexdigest() == row['agent_state_snapshot_hash']
                        tally['probe_state_hashes'] += 1
                    for p in probes.get(t+1, []):
                        d, rr = None, None
                        if p.get('R_used'):
                            name, born = p['R'].rsplit('@', 1)
                            d = state['definitions'][name]
                            assert d['registered_at'] == int(born)
                        if p['answer'] is not None:
                            assert d
                            st = 'F' if p['source'] == 'F_proj' else p['source'].removesuffix('_fill')
                            possible = []
                            ids = {r['relation']['relation_id'] for r in d['constituents']}
                            for r in d['constituents']:
                                s, hist = audit.seat(d, r, state)
                                if s != st or len(r['relation']['arguments']) != len(p['args']):
                                    continue
                                higher = any(a in ids for a in r['relation']['arguments'])
                                if (p['answer'] in hop) != higher:
                                    continue
                                if st == 'H' and p['answer'] in hist or st == 'F' and r['relation']['predicate'] == p['answer']:
                                    possible.append(r)
                            assert len(possible) == 1, (label, p['t'], p['verb_name'], st, len(possible))
                            rr = possible[0]
                        args_ok = p.get('args') == probe_args
                        if p['answer'] == p['truth'] and p['truth'] is not None:
                            assert bool(p['oracle']) == args_ok
                        emit('probe', p['t'], p['verb_name'], p['verb_class'], p['truth'], p['answer'],
                             args_ok, p.get('abstain'), d, rr, state,
                             known_no_answer_seat=p.get('abstain') == 'no_projectable_relation')
                    if (t+1) % 500 == 0:
                        count = Counter()
                        for d in state['definitions'].values():
                            count['definitions'] += 1
                            had_h = had_multi = had_both = False
                            for r in d['constituents']:
                                if r['relation']['relation_id'] not in past_ids:
                                    continue
                                st, hist = audit.seat(d, r, state)
                                if st != 'H':
                                    continue
                                had_h = True
                                had_multi |= len(hist) >= 2
                                had_both |= 'REG' in hist and any(p.startswith('IRR_') for p in hist)
                            count['past_H_definitions'] += int(had_h)
                            count['past_H_multiple_names_definitions'] += int(had_multi)
                            count['past_H_REG_and_IRR_definitions'] += int(had_both)
                        snapshots.append({'run': label, 'arm': run['arm'], 'U': run['U'], 'seed': seed, 't': t+1, **dict(count)})
                assert t == 4999
            assert tally['probe:queries'] == 2400
            assert tally['joined_existing_classification'] == len(cases)
            checks.update(tally)
            per_run.append({'run': label, 'arm': run['arm'], 'U': run['U'], 'seed': seed, **dict(tally)})
            audit.csv_out(OUT/'coverage_partial.csv', per_run)
            audit.csv_out(OUT/'mixed_history_definitions_partial.csv', snapshots)
            audit.csv_out(OUT/'input_manifest_partial.csv', inputs)
            audit.dump(OUT/'status.json', {'state': 'running', 'runs_complete': index, 'planned': 30, 'last': label})
            print(compact(per_run[-1]), flush=True)

    gate_rows = []
    for key, expected_pair in sorted(expected.items()):
        c = reproduced[key]
        got = (c['queries'], c['REG'])
        assert got == expected_pair, (key, expected_pair, got)
        gate_rows.append(dict(zip(('arm', 'U', 'bin', 'verb'), key), queries=c['queries'], REG=c['REG'], exact=True))
    assert checks['training:queries'] == 13650 and checks['probe:queries'] == 72000
    assert checks['H_answer_checked'] == 49178
    assert checks['training:席が未特定の黙り'] == 740 and checks['probe:席が未特定の黙り'] == 8260
    keys = ('arm', 'U', 'seed', 'phase', 'bin', 'verb', 'verb_class')
    rate_rows = []
    for k, c in sorted(rate_counts.items()):
        den = c['correct'] + c['REG']
        cfden = c['counterfactual_correct'] + c['counterfactual_REG']
        rate_rows.append({**dict(zip(keys, k)), **dict(c), 'marcus_denominator': den,
                          'marcus_rate': c['REG']/den if den else None, 'REG_all_queries_rate': c['REG']/c['queries'],
                          'counterfactual_answered_marcus_denominator': cfden,
                          'counterfactual_answered_marcus_rate': c['counterfactual_REG']/cfden if cfden else None,
                          'counterfactual_answered_REG_all_queries_rate': c['counterfactual_REG']/c['queries']})
    over_rows = []
    for k, c in sorted(breakdown.items()):
        denom = rate_counts[k[:7]]
        md = denom['correct'] + denom['REG']
        over_rows.append({**dict(zip((*keys, 'category', 'subtype', 'classification'), k)), 'REG': c['REG'],
                          'queries_all_categories': denom['queries'], 'marcus_denominator_all_categories': md,
                          'REG_component_marcus_rate': c['REG']/md if md else None,
                          'REG_component_all_queries_rate': c['REG']/denom['queries']})
    audit.csv_out(OUT/'overregularization_breakdown.csv', over_rows)
    audit.csv_out(OUT/'rates_per_verb.csv', rate_rows)
    pooled = defaultdict(Counter)
    for k, c in rate_counts.items():
        pooled[(k[0], k[1], k[3], k[4], k[5], k[6])].update(c)
    pooled_rows = []
    for k, c in sorted(pooled.items()):
        den = c['correct'] + c['REG']
        pooled_rows.append({**dict(zip(('arm', 'U', 'phase', 'bin', 'verb', 'verb_class'), k)), **dict(c),
                            'marcus_denominator': den, 'marcus_rate': c['REG']/den if den else None,
                            'REG_all_queries_rate': c['REG']/c['queries']})
    audit.csv_out(OUT/'rates_pooled_seeds.csv', pooled_rows)
    audit.csv_out(OUT/'categories.csv', [{**dict(zip((*keys, 'category'), k)), **dict(c)} for k, c in sorted(category_counts.items())])
    audit.csv_out(OUT/'counterfactual.csv', [{**dict(zip((*keys, 'category', 'subtype'), k)), **dict(c)} for k, c in sorted(changes.items())])
    audit.csv_out(OUT/'H_transitions.csv', [{**dict(zip((*keys, 'category', 'subtype', 'before', 'after'), k)), **dict(c)} for k, c in sorted(transitions.items())])
    audit.csv_out(OUT/'unidentified_silence.csv', [{**dict(zip(('arm', 'U', 'seed', 'phase', 'bin', 'abstain_reason'), k)), **dict(c)} for k, c in sorted(unidentified.items())])
    audit.csv_out(OUT/'mixed_history_definitions.csv', snapshots)
    audit.csv_out(OUT/'coverage.csv', per_run)
    audit.csv_out(OUT/'gate1_recheck.csv', gate_rows)
    for p in (Path(__file__), audit.OUT/'audit.py'):
        inputs.append(audit.fingerprint(p))
    audit.csv_out(OUT/'input_manifest.csv', inputs)
    result = {'state': 'complete', 'runs': 30, 'model_reruns': 0, 'gate1_rows': len(gate_rows), 'gate1_mismatches': 0,
              'H_answer_formula_mismatches': 0, 'counts': dict(checks), 'elapsed_seconds': time.monotonic()-began,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'stage1_stop_replaced_by_explicit_limited_scope_authorization': True,
              'probe_error_classification': 'not_recorded_probe', 'unidentified_silence_imputed': False}
    audit.dump(OUT/'result.json', result)
    audit.dump(OUT/'status.json', {'state': 'complete', 'runs_complete': 30})
    print(compact(result), flush=True)


if __name__ == '__main__':
    main()
