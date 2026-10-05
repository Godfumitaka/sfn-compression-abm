"""既存30本だけのH式の再現関門。予測・照合・学習・分類は呼ばない。"""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
sys.path.insert(0, str(SOURCE))
from abm.loop import _apply, _json_bytes
from abm.seed import load_seed, higher_order_predicates

OUT = Path(__file__).resolve().parent
OLD = ROOT / 'stage3_night'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def csv_out(path, rows):
    if not rows:
        path.write_text('')
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return {'path':str(path.relative_to(ROOT)), 'sha256':h.hexdigest(), 'bytes':path.stat().st_size}


def seat(d, row, state):
    key = str((d['name'], row['slot_index']))
    hist = state['slot_history'].get(key)
    counts = dict(hist) if isinstance(hist, dict) else {p:1 for p in hist or ()}
    st = 'F' if row['alive'] else 'H' if key in state['slot_history'] else 'U'
    return st, counts


def formula(d, row, state, hop, lam):
    """元の演算順・浮動小数点同点をそのまま再現。設計確率で代用しない。"""
    hist = seat(d, row, state)[1]
    ids = {r['relation']['relation_id'] for r in d['constituents']}
    higher = any(a in ids for a in row['relation']['arguments'])
    names = sorted(p for p in hist if (p in hop) == higher)
    if not names:
        return None, {}, 'no_pool'
    ph = state['p_hat']
    n = sum(hist[p] for p in names)
    weights = {}
    for p in names:
        empirical = ph['counts'].get(p, 0) / ph['total'] if ph['total'] else 0.0
        prob = (1/max(len(ph['alive_vocab']),1) if not ph['total'] else
                empirical if empirical != 0.0 else ph['lambda_mix']/max(len(ph['alive_vocab']),1))
        weights[p] = ((hist[p]/n)**lam)*prob if lam != 0.0 and hist and n > 0 else prob
    maximum = max(weights.values())
    winners = [p for p,w in weights.items() if w == maximum]
    return (winners[0] if len(winners)==1 else None), weights, ('unique' if len(winners)==1 else 'tie')


def v39_records(path):
    with path.open() as f:
        for line in f:
            row = json.loads(line)
            if row.get('kind') == 'v39':
                yield row


def main():
    started = time.monotonic()
    plan = json.loads((OLD/'plan.json').read_text())
    wanted = {(a,u,s) for a in ('A','C','D') for u in ('global','abstain') for s in range(1,6)}
    assert len(plan['runs'])==30 and {(r['arm'],r['U'],r['seed']) for r in plan['runs']}==wanted
    config = SOURCE/'config/sweep_verb_hide1_s1_2026-10-04.json'
    dictionary = SOURCE/'tools/verb/U-011_seed_verb.json'
    hop = higher_order_predicates(load_seed(dictionary))
    lam = json.loads(config.read_text())['fixed']['local_lambda']
    assert lam == 1.0
    manifests = []
    target = OLD/'aggregate/overregularization_per_verb.csv'
    expected = {(r['arm'],r['U'],int(r['bin']),r['verb']):(int(r['queries']),int(r['REG']))
                for r in csv.DictReader(target.open())}
    obtained = defaultdict(Counter)
    counts = []
    missing_rows = []
    examples = []
    mismatch_rows = []
    gate2 = Counter()
    for run in plan['runs']:
        label, seed = run['label'], run['seed']
        assert seed in range(1,6)
        folder = OLD/label/'run'
        ledgers = list((folder/'ledgers/cells').glob(f'*/seed{seed:03d}.jsonl.gz'))
        assert len(ledgers)==1
        ledger = ledgers[0]
        side = folder/'side'/ledger.parent.name
        paths = [ledger, side/f'seed{seed:03d}.jsonl', side/f'seed{seed:03d}.answers.csv',
                 side/f'seed{seed:03d}.probe.jsonl', side/f'seed{seed:03d}.select.jsonl.gz']
        amb_path = side/f'seed{seed:03d}.ambig.csv'
        if amb_path.exists():
            paths.append(amb_path)
        manifests += [{'run':label, **fingerprint(p)} for p in paths]
        answers = {int(r['trial']):r for r in csv.DictReader(paths[2].open())}
        ambig = {int(r['trial']):r for r in csv.DictReader(amb_path.open())} if amb_path.exists() else {}
        probes = defaultdict(list)
        for line in paths[3].open():
            p = json.loads(line)
            assert p['verb_probe']=='past'
            probes[p['t']].append(p)
        v39 = iter(v39_records(paths[1]))
        tally = Counter()
        missing = Counter()
        def unresolved(phase, t, verb, field, detail):
            missing[(phase,field,detail)] += 1
            if sum(1 for e in examples if e['run']==label and e['field']==field and e['detail']==detail)<2:
                examples.append({'run':label,'phase':phase,'t':t,'verb':verb,'field':field,'detail':detail})
        def check_h(phase, t, verb, d, row, state, recorded, origin):
            calc, weights, status = formula(d,row,state,hop,lam)
            gate2[phase+':checked'] += 1
            if calc != recorded:
                gate2[phase+':mismatch'] += 1
                mismatch_rows.append({'run':label,'phase':phase,'t':t,'verb':verb,'R':d['name'],
                    'slot':row['slot_index'],'recorded':recorded,'calculated':calc,'origin':origin,
                    'history':json.dumps(seat(d,row,state)[1],sort_keys=True),
                    'p_hat':json.dumps(state['p_hat'],sort_keys=True),'weights':json.dumps(weights,sort_keys=True)})
        state = None
        previous_hash = None
        with gzip.open(ledger,'rt') as f:
            header = json.loads(next(f))
            assert header['run_seed']==seed and header['trial_count']==5000 and header['arm_local_lambda']==lam
            for t,line in enumerate(f):
                row = json.loads(line)
                assert row['prediction_order']==t
                srec = next(v39)
                assert srec['trial']==t
                pre = state
                if row['held_out_is_past']:
                    if pre is not None:
                        assert hashlib.sha256(_json_bytes(pre)).hexdigest()==previous_hash
                        tally['state_hashes'] += 1
                    tally['training_past'] += 1
                    pred = row.get('predicted_edge')
                    answer = pred['predicate'] if pred else None
                    if row['verb_class']=='irregular':
                        obtained[(run['arm'],run['U'],t//500,row['verb_name'])].update(queries=1,REG=int(answer=='REG'))
                    if row.get('R_used'):
                        d = pre['definitions'][row['R_used']]
                        assert 'p_hat' in pre and 'counts' in pre['p_hat'] and 'total' in pre['p_hat']
                        tally['training_definition'] += 1
                        rec = answers.get(t) if pred else ambig.get(t)
                        slot = rec.get('slot' if pred else 'held_slot') if rec else None
                        if slot not in (None,''):
                            slot = int(slot)
                            rr = next(r for r in d['constituents'] if r['slot_index']==slot)
                            st,hist = seat(d,rr,pre)
                            assert st == rec['seat_state' if pred else 'held_state']
                            tally['training_seat_'+st] += 1
                            if pred:
                                assert rec['R']==row['R_used'] and rec['pred']==answer
                                assert int(rec['R_born'])==d['registered_at']
                                rid = pred['relation_id']
                                assert (rid == 'sme_projection__'+rr['relation']['relation_id'] or
                                        rid == f"filling__{d['name']}__{slot}__{rr['registered_at']}")
                                if st=='H':
                                    assert int(rec['h_total'])==sum(hist.values())
                                    check_h('training_answer',t,row['verb_name'],d,rr,pre,answer,'answers.csv')
                            if st=='H':
                                it = next((a for a in srec.get('answers',[]) if a[0]==slot),None)
                                if it is None or not it[2] or it[3] is None or 'H' not in it[3]:
                                    unresolved('training',t,row['verb_name'],'H_pre_answer','sideに当該H席の答えが無い')
                                else:
                                    check_h('training_side',t,row['verb_name'],d,rr,pre,it[3]['H'],'side.answers')
                        else:
                            if not pred and row['abstain_reason']=='no_projectable_relation' and not row['candidate_distribution']:
                                tally['training_known_no_answer_seat'] += 1
                            else:
                                unresolved('training',t,row['verb_name'],'answer_slot','黙りの対象の席が記録から決まらない')
                    else:
                        tally['training_no_used_definition'] += 1
                snap = row['state_snapshot']
                state = snap['value'] if snap['kind']=='full' else _apply(state,snap['changes'])
                previous_hash = row['agent_state_snapshot_hash']
                if probes.get(t+1):
                    assert hashlib.sha256(_json_bytes(state)).hexdigest()==previous_hash
                    tally['state_hashes'] += 1
                for p in probes.get(t+1,[]):
                    tally['probe_past'] += 1
                    if not p.get('R_used'):
                        tally['probe_no_used_definition'] += 1
                        continue
                    name,born = p['R'].rsplit('@',1)
                    d = state['definitions'][name]
                    assert int(born)==d['registered_at']
                    tally['probe_definition'] += 1
                    assert 'p_hat' in state and 'counts' in state['p_hat'] and 'total' in state['p_hat']
                    if p['answer'] is None:
                        unresolved('probe',p['t'],p['verb_name'],'answer_slot','試験の黙りに席・分布・対応先の記録が無い')
                        continue
                    src = p.get('source')
                    st = 'F' if src=='F_proj' else src.removesuffix('_fill') if src else ''
                    tally['probe_answer_source_'+st] += 1
                    if st not in ('F','H','U'):
                        unresolved('probe',p['t'],p['verb_name'],'answer_slot','試験の答えの出所が席状態にならない')
                        continue
                    candidates = []
                    ids = {r['relation']['relation_id'] for r in d['constituents']}
                    for rr in d['constituents']:
                        s,hist = seat(d,rr,state)
                        if s!=st or len(rr['relation']['arguments'])!=len(p['args']):
                            continue
                        # 過去形の試験で渡される引数は二つの物。一階の席だけが答えられる。
                        if any(a in ids for a in rr['relation']['arguments']):
                            continue
                        calc = rr['relation']['predicate'] if st=='F' else formula(d,rr,state,hop,lam)[0] if st=='H' else None
                        if st=='U' or calc==p['answer']:
                            candidates.append(rr)
                    if len(candidates)!=1:
                        unresolved('probe',p['t'],p['verb_name'],'answer_slot',f'試験の席番号なし・状態と答えに適合する候補{len(candidates)}席')
                        continue
                    rr = candidates[0]
                    tally['probe_seat_'+st] += 1
                    if st=='H':
                        check_h('probe_inferred_answer',p['t'],p['verb_name'],d,rr,state,p['answer'],'source+候補一意（独立関門ではない）')
            assert t==4999
        for (phase,field,detail),n in sorted(missing.items()):
            missing_rows.append({'run':label,'arm':run['arm'],'U':run['U'],'seed':seed,'phase':phase,'field':field,'detail':detail,'count':n})
        counts.append({'run':label,'arm':run['arm'],'U':run['U'],'seed':seed,**dict(tally),'missing':sum(missing.values())})
        csv_out(OUT/'record_coverage.csv',counts)
        csv_out(OUT/'missing_fields.csv',missing_rows)
        dump(OUT/'status.json',{'complete':len(counts),'planned':30,'last_run':label})
        print(json.dumps({'run':label,**dict(tally),'missing':sum(missing.values())},ensure_ascii=False),flush=True)
    gate1=[]
    for key in sorted(expected.keys()|obtained.keys()):
        eq,er = expected.get(key,(0,0)); actual=obtained[key]
        gate1.append({'arm':key[0],'U':key[1],'bin':key[2],'verb':key[3],
                      'expected_queries':eq,'actual_queries':actual['queries'],'expected_REG':er,'actual_REG':actual['REG'],
                      'equal':eq==actual['queries'] and er==actual['REG']})
    csv_out(OUT/'gate1_counts.csv',gate1)
    csv_out(OUT/'gate2_mismatches.csv',mismatch_rows)
    csv_out(OUT/'missing_fields.csv',missing_rows)
    dump(OUT/'missing_examples.json',examples)
    csv_out(OUT/'input_manifest.csv',manifests+[fingerprint(target),fingerprint(config),fingerprint(dictionary),fingerprint(OUT/'audit.py')])
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={'stage':'1','model_reruns':0,'runs':30,'state_hashes':sum(r['state_hashes'] for r in counts),
            'training_past':sum(r['training_past'] for r in counts),'probe_past':sum(r['probe_past'] for r in counts),
            'p_hat':'全試行後の状態にcounts/total/lambda_mix/alive_vocab。学習中は直前試行の状態、試験はt試行後の状態。',
            'gate1_rows':len(gate1),'gate1_mismatch_rows':sum(not r['equal'] for r in gate1),
            'gate2_counts':dict(gate2),'missing_instances':sum(r['count'] for r in missing_rows),
            'gate2_independent_probe_check':False,
            'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':peak}
    # 試験の席を式の答えから逆算した一致は独立の再現検査にならない。
    result['stop_at_stage1']= bool(result['missing_instances'] or result['gate1_mismatch_rows'] or mismatch_rows or not result['gate2_independent_probe_check'])
    result['stage2_executed']=False
    dump(OUT/'gate_result.json',result)
    dump(OUT/'status.json',{'state':'stopped_at_stage1' if result['stop_at_stage1'] else 'stage1_passed',**result})
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
