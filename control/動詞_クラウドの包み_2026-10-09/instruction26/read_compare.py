"""指示26の別の読取比較。原模型・原比較の例外は変更しない。"""
from pathlib import Path
from datetime import datetime
import hashlib, importlib.util, json, sys, traceback

HERE = Path(__file__).resolve().parent
NR = HERE.parent
number = int(sys.argv[1])
assert number in (20, 22)
original = NR / ('instruction20_probe_pair' if number == 20 else 'instruction22_birth')
sys.path.insert(0, str(original))
import compare_probe100 as original_comparator
from instruction11_io import compare_outputs, names, save
from pair_common import completion, read, sha, time_values, validate_spec

def load_manifest_comparator():
    path = NR / 'instruction22_birth/compare_probe100.py'
    spec = importlib.util.spec_from_file_location('manifest_comparator_original22', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sha(path)

def main():
    output = HERE / f'comparison{number}_approved.json'
    assert not output.exists(), '同じ読取比較を再投入しない'
    status = HERE / f'comparison{number}_status.json'
    status.write_text(json.dumps({'at':datetime.now().astimezone().isoformat(), 'state':'running', 'model_starts':0}, ensure_ascii=False, indent=2)+'\n')
    cases = [original / ('probe100_' + mode) for mode in ('off', 'on')]
    evidence = []
    for case, mode in zip(cases, ('off', 'on')):
        validate_spec(read(case/'spec.json'), mode)
        evidence.append(completion(case))
    machines = [read(case/'machine_before_start.json') for case in cases]
    assert machines[0]['machine_boot_sha256'] == machines[1]['machine_boot_sha256']
    folders = [Path(read(case/'spec.json')['output']) for case in cases]
    sets = [names(folder) for folder in folders]
    ambig = {p for p in original_comparator.required_paths() if p.name.endswith('.ambig.csv')}
    assert len(ambig) == 1 and not any(ambig & paths for paths in sets), '原両側に無いCSVの事実を確認する'
    required_existing = original_comparator.required_paths() - ambig
    assert len(required_existing) == 11 and all(required_existing <= paths for paths in sets)
    # 既存関数そのものを呼ぶ。元の出力から除外するファイル・行はゼロ。
    records = compare_outputs(*folders)
    manifest_module, manifest_comparator_sha = load_manifest_comparator()
    assert sha(original/'instruction11_io.py') == sha(NR/'instruction22_birth/instruction11_io.py')
    dictionaries = manifest_module.manifest_counts(*folders)
    result = dict(records)
    result.update(instruction=26, original_gate_instruction=number,
                  at=datetime.now().astimezone().isoformat(),
                  file_names_identical=sets[0] == sets[1],
                  left_names=sorted(str(p) for p in sets[0]),
                  right_names=sorted(str(p) for p in sets[1]),
                  missing_left=sorted(str(p) for p in sets[1]-sets[0]),
                  missing_right=sorted(str(p) for p in sets[0]-sets[1]),
                  absent_on_both=sorted(str(p) for p in ambig),
                  required_existing=sorted(str(p) for p in required_existing),
                  all_actual_files_compared=True, actual_files_excluded=0, probe_rows_excluded=0,
                  manifest_counts_comparison=dictionaries, completion=evidence,
                  machine_boot_sha256=machines[0]['machine_boot_sha256'],
                  io_sha256=sha(original/'instruction11_io.py'),
                  original_comparator_sha256=sha(original/'compare_probe100.py'),
                  manifest_comparator_sha256=manifest_comparator_sha,
                  reader_sha256=sha(__file__), model_starts=0,
                  original_failure_preserved=True,
                  comparison_policy='両側の全名前集合一致＋既存compare_outputsで全実在ファイル全バイト。既定TIME以外の欄/順/空白/行は保持。全manifest研究者辞書の原字節も既存関数で比較。')
    result['passed'] = result['passed'] and result['file_names_identical'] and dictionaries['passed']
    save(output, result)
    times = dict(off=time_values(cases[0]/'run.log'), on=time_values(cases[1]/'run.log'),
                 off_run_case=evidence[0]['result'], on_run_case=evidence[1]['result'],
                 completed_trials=100, configured_trial_count=5000, horizon=5000,
                 full_5000_completed=False, comparison_passed=result['passed'])
    times['raw_real_ratio'] = times['off']['real_seconds']/times['on']['real_seconds']
    times['run_case_active_wall_ratio'] = (times['off_run_case']['wall_seconds']-times['off_run_case']['paused_seconds'])/(times['on_run_case']['wall_seconds']-times['on_run_case']['paused_seconds'])
    times['time_policy'] = '原time・run_case・停止秒を別に保持。active_wallは原wallから原停止秒を引いた算術参考値で原timeを書き換えない。'
    save(HERE/f'timing{number}_approved.json', times)
    status.write_text(json.dumps({'at':datetime.now().astimezone().isoformat(), 'state':'completed' if result['passed'] else 'stopped_mismatch', 'passed':result['passed'], 'model_starts':0, 'comparison':str(output)}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('passed','file_count','mismatching_files','file_names_identical','probe_rows_excluded')}, ensure_ascii=False), flush=True)
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        (HERE/f'comparison{number}_exception.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(), 'error':repr(exc), 'traceback':traceback.format_exc(), 'model_starts':0},ensure_ascii=False,indent=2)+'\n')
        raise
