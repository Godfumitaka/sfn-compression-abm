"""関門で保存済みの通信と世界の台帳を突き合わせる。模型を動かさない。"""
from pathlib import Path
import collections
import gzip
import json

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT/'outputs'
observed = json.loads((OUTPUTS/'checks_counts_observed.json').read_text())
results = []
for population in observed:
    name = population['condition']
    comm_path = OUTPUTS/name/'comm'/population['run']
    comm = [json.loads(l) for l in comm_path.read_text().splitlines()]
    summary = next(r for r in comm if r['kind'] == 'summary')
    lookup = {}
    for agent, meta in enumerate(summary['agents']):
        seed = meta['seed']
        assert seed in (1, 1001)
        path = OUTPUTS/name/'ledgers/cells'/meta['cell']/f'seed{seed:03d}.jsonl.gz'
        with gzip.open(path, 'rt') as f:
            next(f)
            for l in f:
                row = json.loads(l)
                lookup[agent, row['prediction_order']] = row
    counts = collections.Counter()
    mismatches = []
    for b in (r for r in comm if r['kind'] == 'bundle'):
        world = lookup[b['agent'], b['t']]
        counts['bundles_including_empty'] += 1
        counts['nonempty_bundles'] += not b.get('empty')
        counts['bundles_in_abstained_world_trial'] += world.get('coverage') != 1
        counts['sent_in_abstained_world_trial'] += bool(b.get('send')) and world.get('coverage') != 1
        actual = world.get('predicted_edge')
        prediction = [actual['relation_id'], actual['predicate'], actual['arguments']] if actual else None
        different = not b.get('empty') and b.get('pred') != prediction
        counts['bundle_prediction_differs_from_world_prediction'] += different
        counts['sent_prediction_differs_from_world_prediction'] += bool(b.get('send')) and different
        if different or world.get('coverage') != 1:
            mismatches.append({'trial_zero_based': b['t'], 'agent': b['agent'], 'seed': summary['agents'][b['agent']]['seed'],
                               'world': world, 'bundle': b})
    results.append({'condition': name, 'run': population['run'], 'counts': dict(counts),
                    'first_mismatch': min(mismatches, key=lambda r:(r['trial_zero_based'],r['agent'])) if mismatches else None,
                    'mismatches': mismatches})
out = OUTPUTS/'bundle_world_mismatches.json.gz'
assert not out.exists()
out.write_bytes(gzip.compress((json.dumps(results,ensure_ascii=False,separators=(',',':'))+'\n').encode(),mtime=0))
print(json.dumps([{k:v for k,v in r.items() if k not in ('mismatches','first_mismatch')} for r in results],ensure_ascii=False,indent=1))
first = next(r['first_mismatch'] for r in results if r['condition']=='q0')
print(json.dumps({'q0_first': {'trial_zero_based':first['trial_zero_based'],'agent':first['agent'],'seed':first['seed'],
                             'coverage':first['world']['coverage'],'abstain_reason':first['world']['abstain_reason'],
                             'actual_pred':first['world']['predicted_edge'],'bundle_pred':first['bundle'].get('pred'),
                             'bundle_size':first['bundle'].get('n_rel'),'sent':first['bundle'].get('send')}},ensure_ascii=False,indent=1))
