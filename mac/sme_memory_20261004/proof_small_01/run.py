"""枠が空いてから13本を直列で比較する。診断の実測秒だけを別表にする。"""
from pathlib import Path
import csv
import importlib.util
import json
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
spec = importlib.util.spec_from_file_location('exact_compare', WORKSPACE / 'codex_sme_fast_2026-10-03/exact_tools/compare.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)
spec = importlib.util.spec_from_file_location('resource_check', WORKSPACE / 'codex_sme_fast_2026-10-03/exact_tools/run_one.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def main():
    for full in ('profile_late_01', 'proof_rng_share_01'):
        path = HERE.parent / full / 'run_result.json'
        if not path.exists():
            raise SystemExit('二本の全走行が閉じてから開始する')
        if json.loads(path.read_text())['exit'] != 0:
            raise SystemExit('全走行の終了番号が0でない')
        proof = HERE.parent / full / 'full.summary.json'
        if not proof.exists() or not json.loads(proof.read_text())['all_requested_bytes_equal']:
            raise SystemExit('二本とも全バイトの比較が通ってから開始する')
    results, timings = [], []
    for row in json.loads((HERE / 'plan.json').read_text()):
        case = HERE / row['name']
        if (case / 'run.log').exists():
            raise SystemExit('同じ小走行を二度始めない')
        while True:
            resource = check.resources(HERE)
            with (HERE / 'queue_resources.jsonl').open('a') as stream:
                stream.write(json.dumps(resource, ensure_ascii=False) + '\n')
            if resource['free_bytes'] >= 18 * 2**30 and len(resource['python_heavy']) < 4 and 'No thermal warning level has been recorded' in resource['thermal']:
                break
            time.sleep(20)
        subprocess.run([sys.executable, str(case / 'supervise.py')], check=True)
        baseline = WORKSPACE / 'codex_sme_fast_2026-10-03/exact_small_01/baseline' / row['name'] / 'output'
        result = compare.compare(baseline, case / 'output')
        (case / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        if not result['all_bytes_equal']:
            raise SystemExit('sec_trial以外に不一致。案は採用せず止める: ' + row['name'])
        for record in result['records']:
            for timing in record.get('timing_values', []):
                timings.append({'run': row['name'], 'file': record['file'], **timing})
        results.append({'run': row['name'], 'all_bytes_equal_except_sec_trial': True,
                        'compared_files': len(result['records'])})
        print(row['name'] + '：sec_trial以外の全バイト一致', flush=True)
    summary = {'runs': len(results), 'trials_per_run': 20, 'total_trials': len(results) * 20,
               'exception': 'sec_trialの数値だけ', 'results': results, 'timing_rows': len(timings)}
    (HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    with (HERE / 'sec_trial_values.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(timings[0]))
        writer.writeheader()
        writer.writerows(timings)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
