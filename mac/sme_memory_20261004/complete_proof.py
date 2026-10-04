"""閉じた探索の記録を元のbdaa110と全バイトで比較する。模型を呼ばない。"""
from pathlib import Path
import argparse
import gzip
import importlib.util
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'codex_sme_fast_2026-10-03/exact_full_01/baseline'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', choices=('profile_late_01', 'proof_rng_share_01'))
    args = parser.parse_args()
    candidate = ROOT / args.run
    for path in (BASE, candidate):
        if json.loads((path / 'run_result.json').read_text())['exit'] != 0:
            raise SystemExit('終了番号0で閉じた記録だけを比較する')
    spec = importlib.util.spec_from_file_location('exact_compare', ROOT.parent / 'codex_sme_fast_2026-10-03/exact_tools/compare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    comparison = module.compare(BASE / 'output', candidate / 'output')
    (candidate / 'full.comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n')
    if not comparison['all_bytes_equal']:
        raise SystemExit('不一致。変更は採用せず止める')
    headers = []
    measurements = []
    for path in (BASE, candidate):
        with gzip.open(next((path / 'output/ledgers').rglob('*.jsonl.gz')), 'rt') as stream:
            headers.append(json.loads(next(stream)))
        manifest = json.loads((path / 'output/manifest.jsonl').read_text().splitlines()[-1])
        resources = [json.loads(line) for line in (path / 'resources.jsonl').read_text().splitlines()]
        with (path / 'tie_rng.jsonl').open() as stream:
            rng_count = 0
            for line in stream:
                last = json.loads(line)
                rng_count += 1
        assert rng_count == 1740
        measurements.append({'run': path.name, 'source_commit': manifest['code_commit'],
                             'manifest_elapsed_seconds': manifest['elapsed_sec'],
                             'supervisor_wall_seconds': json.loads((path / 'run_result.json').read_text())['wall_seconds'],
                             'peak_rss_mb': manifest['peak_rss_mb'], 'tie_rng_trials': rng_count,
                             'cache_count': last['cache_count'], 'self_cache_count': last['self_cache_count'],
                             'cache_rng_count': last['cache_rng_count'],
                             'min_free_gib': min(row['free_bytes'] for row in resources) / 2**30,
                             'max_sampled_heavy': max(len(row['python_heavy']) for row in resources),
                             'thermal_warning_samples': sum('No thermal warning level has been recorded' not in row['thermal'] for row in resources),
                             'paused_samples': sum(row.get('measurement_paused', False) for row in resources)})
    summary = {'all_requested_bytes_equal': True, 'compared_records': len(comparison['records']),
               'ledger_header_different_keys': sorted(key for key in headers[0].keys() | headers[1].keys()
                                                      if headers[0].get(key) != headers[1].get(key)),
               'full_run_has_sec_trial': any('timing_values' in row for row in comparison['records']),
               'measurements': measurements,
               'size_observer_included_in_candidate_rss': args.run == 'profile_late_01'}
    (candidate / 'full.summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
