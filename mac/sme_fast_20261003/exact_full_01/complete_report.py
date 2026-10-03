"""閉じた二本の全走行だけを比較し、測定値を別に保存する。模型は呼ばない。"""
from pathlib import Path
import importlib.util
import json
import gzip


def main():
    root = Path(__file__).resolve().parent
    reference, candidate = root / 'baseline', root / 'fast'
    for run in (reference, candidate):
        result_file = run / 'run_result.json'
        if not result_file.exists() or json.loads(result_file.read_text())['exit'] != 0:
            raise SystemExit('二本が終了番号0で閉じるまで比較しない')
    spec = importlib.util.spec_from_file_location('exact_compare', root.parent / 'exact_tools/compare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    compared = module.compare(reference / 'output', candidate / 'output')
    (root / 'full.comparison.json').write_text(json.dumps(compared, ensure_ascii=False, indent=2) + '\n')
    if not compared['all_bytes_equal']:
        raise SystemExit('一致しないファイルあり。高速化の変更は採用しない')
    measurements = []
    headers = []
    for run in (reference, candidate):
        result = json.loads((run / 'run_result.json').read_text())
        manifest = json.loads((run / 'output/manifest.jsonl').read_text().splitlines()[-1])
        with gzip.open(next((run / 'output/ledgers').rglob('*.jsonl.gz')), 'rt') as stream:
            headers.append(json.loads(next(stream)))
        resources = [json.loads(line) for line in (run / 'resources.jsonl').read_text().splitlines()]
        final_rng = json.loads((run / 'tie_rng.jsonl').read_text().splitlines()[-1])
        measurements.append({'run': run.name, 'code_commit': manifest['code_commit'],
                             'wall_seconds': result['wall_seconds'], 'manifest_elapsed_sec': manifest['elapsed_sec'],
                             'peak_rss_mb': manifest['peak_rss_mb'], 'trial_count': manifest['trial_count'],
                             'cache_count': final_rng['cache_count'], 'self_cache_count': final_rng['self_cache_count'],
                             'cache_rng_count': final_rng['cache_rng_count'],
                             'min_free_gib': min(row['free_bytes'] for row in resources) / 2**30,
                             'max_observed_python_heavy': max(len(row['python_heavy']) for row in resources),
                             'thermal_warning_samples': sum('No thermal warning level has been recorded' not in row['thermal'] for row in resources),
                             'samples': len(resources)})
    summary = {'baseline_commit': measurements[0]['code_commit'], 'candidate_commit': measurements[1]['code_commit'],
               'all_requested_bytes_equal': True, 'sec_trial_only_exclusion': True,
               'full_run_has_sec_trial': any('timing_values' in record for record in compared['records']),
               'compared_records': len(compared['records']), 'tie_rng_trials': len((reference / 'tie_rng.jsonl').read_text().splitlines()),
               'ledger_header_different_keys': sorted(key for key in headers[0].keys() | headers[1].keys() if headers[0].get(key) != headers[1].get(key)),
               'measurements': measurements,
               'wall_speed_factor': measurements[0]['wall_seconds'] / measurements[1]['wall_seconds'],
               'manifest_speed_factor': measurements[0]['manifest_elapsed_sec'] / measurements[1]['manifest_elapsed_sec'],
               'cache_eviction_changes': 0}
    (root / 'full.summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
