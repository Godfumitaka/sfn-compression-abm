"""一台帳の黙り・語別質問数・新語の選択定義を読む。予測や学習は呼ばない。"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'tools')]
from abm.loop import _apply, _json_bytes
from abm.world import opaque_id
from aggregate import write_csv
from followup import abstain_detail


def history_counts(value):
    return dict(value) if isinstance(value, dict) else {v: 1 for v in value or ()}


def seat_record(definition, row, histories):
    key = str((definition['name'], row['slot_index']))
    h = history_counts(histories.get(key))
    # 模型と同じく、空表でも履歴の欄があればH。
    state = 'F' if row['alive'] else 'H' if key in histories else 'U'
    maxima = sorted(k for k, v in h.items() if v == max(h.values())) if h else []
    answer = row['relation']['predicate'] if state == 'F' else maxima[0] if len(maxima) == 1 else None
    return {'slot': row['slot_index'], 'state': state, 'predicate': row['relation']['predicate'] if row['alive'] else None,
            'history': h, 'history_maxima': maxima, 'stored_answer': answer}


def selected_record(probe, state, name_ids, past_ids):
    if not probe.get('R_used') or not probe.get('R'):
        raise RuntimeError('不規則回答の選択定義が記録されていない')
    name, born = probe['R'].rsplit('@', 1)
    d = state['definitions'].get(name)
    if d is None or d['registered_at'] != int(born):
        raise RuntimeError('試験と状態の選択定義が一致しない')
    names, pasts = [], []
    for r in d['constituents']:
        rid = r['relation']['relation_id']
        if rid in name_ids:
            names.append(seat_record(d, r, state['slot_history']))
        if rid in past_ids:
            pasts.append(seat_record(d, r, state['slot_history']))
    return {'t': probe['t'], 'verb': probe['verb_name'], 'answer': probe['answer'], 'source': probe.get('source'),
            'R': name, 'born': int(born), 'selected_name_states': [r['state'] for r in names] or ['no_name_seat'],
            'name_seats': names, 'past_seats': pasts, 'definition_missing': False}


def read_run(root, seed, output):
    if seed not in range(1, 6):
        raise ValueError('種1〜5だけを明示する')
    output.mkdir(parents=True, exist_ok=True)
    files = list((root/'ledgers/cells').glob(f'*/seed{seed:03d}.jsonl.gz'))
    if len(files) != 1:
        raise ValueError('台帳を一本だけ指定する')
    cell = files[0].parent.name
    probes = [json.loads(line) for line in (root/'side'/cell/f'seed{seed:03d}.probe.jsonl').open()]
    novel_irr = defaultdict(list)
    for p in probes:
        if p.get('verb_class') == 'novel' and (p.get('answer') or '').startswith('IRR_'):
            novel_irr[p['t']].append(p)
    ambig_path = root/'side'/cell/f'seed{seed:03d}.ambig.csv'
    ambig = {int(r['trial']): r for r in csv.DictReader(ambig_path.open())} if ambig_path.exists() else {}
    counts = defaultdict(Counter)
    query_times = defaultdict(list)
    cases = []
    appearances, question_design = hashlib.sha256(), hashlib.sha256()
    with gzip.open(files[0], 'rt') as stream:
        header = json.loads(next(stream))
        assert header['run_seed'] == seed and header['trial_count'] == 5000
        name_ids = {opaque_id(seed,t,'relation:shop:sig') for t in range(5000)}
        past_ids = {opaque_id(seed,t,'relation:tree:0.0.0') for t in range(5000)}
        state = None
        for t, line in enumerate(stream):
            r = json.loads(line)
            assert r['prediction_order'] == t
            appearances.update((r['verb_name']+'\n').encode())
            question_design.update((str(int(r['held_out_is_past']))+'\n').encode())
            for phase in ('training_all', *(['training_past'] if r['held_out_is_past'] else [])):
                key = (phase, r['verb_class'])
                counts[key]['queries'] += 1
                if not r.get('predicted_edge'):
                    reason = r['abstain_reason']
                    assert reason
                    counts[key]['abstain'] += 1
                    counts[key]['reason:'+reason] += 1
                    counts[key]['detail:'+abstain_detail(reason,r,ambig.get(t))] += 1
            if r['held_out_is_past']:
                query_times[r['verb_name']].append(t)
            ss = r['state_snapshot']
            state = ss['value'] if ss['kind'] == 'full' else _apply(state, ss['changes'])
            if t+1 in novel_irr:
                assert hashlib.sha256(_json_bytes(state)).hexdigest() == r['agent_state_snapshot_hash']
                cases.extend(selected_record(p,state,name_ids,past_ids) for p in novel_irr[t+1])
        assert t == 4999
    for p in probes:
        key = ('probe_all',p['verb_class'])
        counts[key]['queries'] += 1
        if p.get('answer') is None:
            reason = p['abstain']
            counts[key]['abstain'] += 1
            counts[key]['reason:'+reason] += 1
            counts[key]['detail:'+abstain_detail(reason,p,probe=True)] += 1
    rows = [{'phase':k[0], 'class':k[1], **dict(c)} for k,c in sorted(counts.items())]
    write_csv(output/'silence.csv', rows)
    with gzip.open(output/'novel_IRR_cases.jsonl.gz','wt') as stream:
        for c in cases:
            stream.write(json.dumps(c,ensure_ascii=False)+'\n')
    grouped = Counter((tuple(c['selected_name_states']), tuple(r['state'] for r in c['past_seats']),
                       tuple(r['stored_answer'] or 'none_or_tie' for r in c['past_seats']), c['answer'], c['source']) for c in cases)
    write_csv(output/'novel_IRR_selected.csv', [{'name_state':'+'.join(n), 'past_state':'+'.join(p),
              'past_stored_answer':'+'.join(a), 'probe_answer':b,'source':s,'count':v} for (n,p,a,b,s),v in sorted(grouped.items())])
    result = {'seed':seed,'ledger_rows':5000,'probe_rows':len(probes),'novel_IRR_cases':len(cases),
              'appearance_sha256':appearances.hexdigest(),'past_question_sha256':question_design.hexdigest(),
              'query_times':dict(query_times)}
    (output/'record_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('root', type=Path)
    ap.add_argument('seed', type=int, choices=range(1,6))
    ap.add_argument('output', type=Path)
    a=ap.parse_args()
    result=read_run(a.root,a.seed,a.output)
    print(json.dumps({k:v for k,v in result.items() if k!='query_times'},ensure_ascii=False),flush=True)
