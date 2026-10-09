"""両方が試験つきの100。試験の行も含め、既存TIME条件だけで全部を比べる。"""
from pathlib import Path
from datetime import datetime
import sys
from instruction11_io import compare_outputs, names, save
from pair_common import CELL, ROOT, completion, read, sha, time_values, validate_spec


def required_paths():
    side = 'side/' + CELL + '/seed001'
    return {Path('attention/' + CELL + '/seed001.jsonl.gz'),
            Path('attention/' + CELL + '/seed001.jsonl.gz.summary.json'),
            Path('evictions/' + CELL + '/seed001.keys.jsonl.gz'),
            Path('evictions/' + CELL + '/seed001.keys.jsonl.gz.summary.json'),
            Path('ledgers/cells/' + CELL + '/seed001.jsonl.gz'),
            *(Path(side + suffix) for suffix in ('.ambig.csv', '.answers.csv', '.jsonl',
              '.routing.jsonl', '.sme.jsonl.gz', '.sme.states.jsonl.gz', '.probe.jsonl'))}


def compare_recordings(left, right):
    required = required_paths()
    assert required <= names(left) and required <= names(right), '台帳・全side・保存状態・試験記録を必須にする'
    result = compare_outputs(left, right)
    assert any(row['path'].endswith('.probe.jsonl') for row in result['files'])
    assert any(row['path'].endswith('.sme.states.jsonl.gz') for row in result['files'])
    return {**result, 'probe_rows_excluded': 0,
            'comparison_policy': '既存TIME値だけ除外。試験・学習・保存状態の行、欄、順、空白を保持'}


def main():
    cases = [ROOT / ('probe100_' + mode) for mode in ('off', 'on')]
    evidence = []
    for case, mode in zip(cases, ('off', 'on')):
        spec = read(case / 'spec.json')
        validate_spec(spec, mode)
        evidence.append(completion(case))
    machines = [read(case / 'machine_before_start.json') for case in cases]
    assert machines[0]['machine_boot_sha256'] == machines[1]['machine_boot_sha256'], '同じMacの二本だけを比べる'
    result = compare_recordings(*(Path(read(case / 'spec.json')['output']) for case in cases))
    result.update(instruction=19, at=datetime.now().astimezone().isoformat(),
                  completion=evidence, machine_boot_sha256=machines[0]['machine_boot_sha256'],
                  comparator_sha256=sha(__file__), io_sha256=sha(ROOT / 'instruction11_io.py'))
    save(ROOT / 'probe100_comparison.json', result)
    times = dict(off=time_values(cases[0] / 'run.log'), on=time_values(cases[1] / 'run.log'),
                 off_run_case=evidence[0]['result'], on_run_case=evidence[1]['result'],
                 completed_trials=100, configured_trial_count=5000, horizon=5000,
                 full_5000_completed=False, comparison_passed=result['passed'])
    times['off_real_divided_by_on_real'] = times['off']['real_seconds'] / times['on']['real_seconds']
    save(ROOT / 'timing_comparison.json', times)
    print({key: result[key] for key in ('passed', 'file_count', 'mismatching_files', 'probe_rows_excluded')}, flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
