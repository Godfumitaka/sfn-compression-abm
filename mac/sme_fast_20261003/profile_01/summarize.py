"""完了した200試行の実測だけを表へする。模型は読み込まない。"""
from pathlib import Path
from collections import Counter
import csv
import io
import json
import pstats
import statistics

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / 'A_seed1_200/manifest.jsonl').read_text())
assert not manifest.get('error') and manifest['trial_count'] == 200
trials = [json.loads(line) for line in (HERE / 'trials.jsonl').read_text().splitlines()]
assert [r['trial'] for r in trials] == list(range(200))
profile = pstats.Stats(str(HERE / 'worker.pstats'))
functions = []
for (file, line, name), (primitive_calls, total_calls, own_seconds, cumulative_seconds, callers) in profile.stats.items():
    functions.append({'file': file, 'line': line, 'name': name,
                      'primitive_calls': primitive_calls, 'total_calls': total_calls,
                      'own_seconds': own_seconds, 'cumulative_seconds': cumulative_seconds})
for rank in ('own_seconds', 'cumulative_seconds'):
    selected = sorted(functions, key=lambda r: r[rank], reverse=True)[:40]
    with (HERE / (rank + '.csv')).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
blocks = []
for start in range(0, 200, 20):
    sample = trials[start:start+20]
    times = [r['model_seconds'] for r in sample]
    last = sample[-1]
    blocks.append({'trial_first': start, 'trial_last': start+19,
                   'mean_seconds': statistics.mean(times), 'median_seconds': statistics.median(times),
                   'min_seconds': min(times), 'max_seconds': max(times),
                   **{k: v for k, v in last.items() if k not in ('trial', 'model_seconds')}})
with (HERE / 'blocks20.csv').open('w') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(blocks[0]))
    writer.writeheader()
    writer.writerows(blocks)
summary = {'trials': 200, 'manifest_elapsed_seconds': manifest['elapsed_sec'],
           'worker_profile_total_seconds': profile.total_tt,
           'sum_model_interval_seconds': sum(r['model_seconds'] for r in trials),
           'peak_rss_mb_manifest': manifest['peak_rss_mb'],
           'blocks20': blocks,
           'top_own': sorted(functions, key=lambda r: r['own_seconds'], reverse=True)[:20],
           'top_cumulative': sorted(functions, key=lambda r: r['cumulative_seconds'], reverse=True)[:20],
           'instrumentation': json.loads((HERE / 'profile.json').read_text())}
(HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k in ('trials', 'manifest_elapsed_seconds', 'worker_profile_total_seconds', 'sum_model_interval_seconds', 'peak_rss_mb_manifest')}, ensure_ascii=False))
for row in summary['top_cumulative'][:12]:
    print(row['name'], row['line'], row['total_calls'], round(row['own_seconds'], 3), round(row['cumulative_seconds'], 3))
