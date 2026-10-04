"""記録された後半20試行の照合入力だけを再計算する。学習・世界は走らせない。"""
from pathlib import Path
from random import Random
import cProfile
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'codex_sme_memory_2026-10-04/source_rng_share'
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import sme2017 as sme
import instrument_01 as meter


def tup(value):
    return tuple(tup(x) for x in value) if isinstance(value, list) else value


def graph(nodes):
    return sme.Graph(tuple(sme.Node(n['key'], n['kind'], frozenset(n['names']),
                                    None if n['args'] is None else tuple(n['args']),
                                    n['state'], n['ubiquitous']) for n in nodes))


assert json.loads((ROOT / 'late_assignment_01.json').read_text())['count_gate_passed']
assert not (ROOT / 'late_replay_result_01.json').exists(), '二重に再生しない'
meter.install(sme)
profiler = cProfile.Profile()
excluded = []
passed = 0
with gzip.open(ROOT / 'late_inputs_01.jsonl.gz', 'rt') as stream, (ROOT / 'late_match_rows_01.jsonl').open('w') as output:
    for line in stream:
        item = json.loads(line)
        row = item['record']
        self_match = row['kind'] == 'sme_self'
        if self_match:
            left = right = graph(item['nodes'])
            rng = Random(0)
        else:
            left, right = graph(row['left_nodes']), graph(row['right_nodes'])
            rng = Random()
            rng.setstate(tup(row['rng_before']))
        assert left.fingerprint() == row.get('left', row.get('input'))
        assert right.fingerprint() == row.get('right', row.get('input'))
        meter.TRIAL = item['trial_number'] - 1
        meter.ROWS.clear()
        engine = sme._Engine(left, right, sme.Settings(**row['settings']), rng)
        profiler.enable()
        result = engine.run()
        profiler.disable()
        if self_match and result.choices:
            excluded.append({'trial_number': item['trial_number'], 'input': row['input'],
                             'reason': '自己照合の元の呼び出し直前の乱数が記録されておらず、抽選があるので計測から除く'})
            continue
        best = result.best
        actual = {'selected': result.selected, 'tied': list(result.tied),
                  'entity_mapping': {} if best is None else dict(best.entity_mapping),
                  'relation_mapping': {} if best is None else dict(best.relation_mapping),
                  'points': [] if best is None else json.loads(json.dumps(best.breakdown))}
        expected = {'selected': row['selected'], 'tied': row['tied'],
                    'entity_mapping': dict(row['entity_mapping'] if self_match else row['new_entity_mapping']),
                    'relation_mapping': dict(row['relation_mapping'] if self_match else row['new_relation_mapping']),
                    'points': row['points']}
        if not self_match:
            actual['choices'] = json.loads(json.dumps(result.choices))
            expected['choices'] = row['choices']
        if actual != expected:
            (ROOT / 'late_replay_difference_01.json').write_text(json.dumps(
                {'trial_number': item['trial_number'], 'actual': actual, 'expected': expected},
                ensure_ascii=False, indent=2) + '\n')
            raise SystemExit('保存した入力と乱数からの照合が一致しないので、この再計測を止める')
        sample = meter.ROWS[-1]
        sample['caller'] = '自己照合' if self_match else row['caller']
        sample['self_rng_independent_proven'] = self_match
        output.write(json.dumps(sample, ensure_ascii=False) + '\n')
        passed += 1
profiler.dump_stats(str(ROOT / 'late_replay_01.pstats'))
with gzip.open(ROOT / 'late_canonical_samples_01.jsonl.gz', 'wt') as output:
    for item in meter.FIRST + list(meter.SAMPLES):
        output.write(json.dumps(item, ensure_ascii=False) + '\n')
(ROOT / 'late_replay_result_01.json').write_text(json.dumps({'passed': True,
    'compared_matches': passed, 'excluded_self_with_draws': excluded,
    'kind': '後半20試行の照合だけの診断。世界・学習を走らせていない。cProfile付きの秒は速さの比較に使わない。'},
    ensure_ascii=False, indent=2) + '\n')
print('late replay', passed, 'excluded self with draws', len(excluded), flush=True)
