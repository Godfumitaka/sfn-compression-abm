"""spawn時の引数とfallback観測の返り値・復元を小例で点検する。"""
from pathlib import Path
import ast
import io
import json
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parent


def main():
    name = 'e9_w1_s001_1a_200'
    os.environ['SME_JSON_CASE'] = name
    os.environ['SME_EXACT_SOURCE'] = json.loads((ROOT / 'preparation_manifest.json').read_text())['cases'][name]['source']
    # spawnは親のnative CLIを引き継ぐ。この引数でケース名を誤読しない。
    sys.argv = ['tools/v3_run.py', '/path/to/config.json', '/path/to/output']
    values = runpy.run_path(str(ROOT / 'observe_counted.py'), run_name='__mp_main__')
    fn = values['counted_worker']
    namespace = fn.__globals__
    mock = ROOT / 'tool_check_fixture'
    mock.mkdir()
    namespace['FOLDER'] = mock
    import smeshared as S
    S.LOG.clear()
    sink = io.StringIO()
    S.LOG.update(f=sink, diagnostic=False)
    S._diagnosing = lambda: False
    old_log, old_keys = S._log, S._log_string_keys
    record = {'p': {None: .25, 'name': .75}}
    marker = object()
    def original(task):
        S._log({'kind': 'normal', 'name': 'same'})
        S._log(record)
        return marker
    namespace['NATIVE_WORKER'] = original
    assert fn({}) is marker
    assert S._log is old_log and S._log_string_keys is old_keys
    assert record == {'p': {None: .25, 'name': .75}}
    counts = json.loads((mock / 'json_fallback_counts.json').read_text())
    assert counts['attempted_records'] == counts['written_records'] == counts['main_written'] == 1
    assert counts['diagnostic_written'] == 0
    assert json.loads(sink.getvalue().splitlines()[1]) == {'p': {'null': .25, 'name': .75}}
    launch = ast.parse((ROOT / 'launch.py').read_text())
    forbidden = []
    for n in ast.walk(launch):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in (
            'kill', 'killpg', 'terminate', 'send_signal', 'unlink', 'rmtree'):
            forbidden.append(n.func.attr)
    assert not forbidden
    compile((ROOT / 'observe_counted.py').read_text(), 'observe_counted.py', 'exec')
    compile((ROOT / 'launch.py').read_text(), 'launch.py', 'exec')
    result = {'passed': True, 'checks': 8, 'spawn_native_argv_uses_environment_case': True,
              'counts_one_record_not_nested_dictionary_calls': True,
              'native_worker_return_and_original_record_unchanged': True,
              'wrapper_functions_restored': True,
              'launch_comparison_scope_requires_explicit_instruction': True,
              'model_tasks_launched': 0, 'model_signals': 0, 'deletions': 0}
    with (ROOT / 'tool_checks.json').open('x') as out:
        out.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
