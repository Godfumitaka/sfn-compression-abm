"""閉じた後半の測定を表にする。模型を呼ばない。"""
from pathlib import Path
import csv
import json
import pstats
import statistics

ROOT = Path(__file__).resolve().parent
HERE = ROOT / 'profile_late_01'


def table(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    result = json.loads((HERE / 'run_result.json').read_text())
    if result['exit'] != 0:
        raise SystemExit('測定が終了番号0で閉じていない')
    trials = [json.loads(line) for line in (HERE / 'trials.jsonl').read_text().splitlines()]
    assert [row['trial'] for row in trials] == list(range(1740))
    late = [row for row in trials if row['profiled']]
    assert [row['trial'] for row in late] == list(range(1499, 1740))
    stats = pstats.Stats(str(HERE / 'worker.pstats'))
    functions = []
    for (filename, line, name), (primitive, total, own, cumulative, _) in stats.stats.items():
        functions.append({'file': filename, 'line': line, 'function': name,
                          'primitive_calls': primitive, 'total_calls': total,
                          'own_seconds': own, 'cumulative_seconds': cumulative})
    own = sorted(functions, key=lambda row: (-row['own_seconds'], row['file'], row['line'], row['function']))
    cumulative = sorted(functions, key=lambda row: (-row['cumulative_seconds'], row['file'], row['line'], row['function']))
    table(HERE / 'functions_own.csv', own)
    table(HERE / 'functions_cumulative.csv', cumulative)
    table(HERE / 'trial_seconds.csv', [{key: row[key] for key in ('trial', 'trial_number', 'model_seconds', 'profiled')} for row in trials])
    blocks = []
    for first, last in ((1500, 1559), (1560, 1619), (1620, 1679), (1680, 1740)):
        rows = [row for row in late if first <= row['trial_number'] <= last]
        seconds = [row['model_seconds'] for row in rows]
        blocks.append({'first': first, 'last': last, 'trials': len(rows),
                       'sum_seconds': sum(seconds), 'mean_seconds': statistics.mean(seconds),
                       'median_seconds': statistics.median(seconds), 'min_seconds': min(seconds),
                       'max_seconds': max(seconds), **{name + '_count': rows[-1][name + '_count']
                                                     for name in ('cache', 'self_cache', 'cache_rng')}})
    table(HERE / 'late_blocks.csv', blocks)
    sizes = [row for row in trials if 'cache_deep_bytes' in row]
    table(HERE / 'cache_sizes.csv', sizes)
    profile = json.loads((HERE / 'profile.json').read_text())
    manifest = json.loads((HERE / 'output/manifest.jsonl').read_text().splitlines()[-1])
    summary = {'source_commit': manifest['code_commit'], 'trial_count': len(trials),
               'late_trial_count': len(late), 'cprofile_total_seconds': stats.total_tt,
               'late_interval_seconds': sum(row['model_seconds'] for row in late),
               'whole_supervisor_wall_seconds': result['wall_seconds'],
               'whole_manifest_elapsed_seconds': manifest['elapsed_sec'],
               'peak_rss_mb_including_size_observer': manifest['peak_rss_mb'],
               'profile': profile, 'late_blocks': blocks, 'cache_sizes': sizes,
               'functions_own_top20': own[:20], 'functions_cumulative_top20': cumulative[:20]}
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in ('trial_count', 'late_trial_count', 'cprofile_total_seconds',
                                                  'late_interval_seconds', 'peak_rss_mb_including_size_observer')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
