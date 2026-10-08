"""投入前に未登録予約と模型枠、元版の観測経路を小例で点検する。"""
from pathlib import Path
import ast
import importlib.util
import io
import json
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parent


def main():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('prepared_controller', ROOT / 'controller.py')
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    m = dict(model_children=3, registered=[dict(pid=1, mem_gb=9)], disk_free_bytes=100 * 2**30,
             swap_ok=True, thermal_warnings=0, unregistered_heavy=[])
    assert C.can_start(m, 13, 5)
    assert not C.can_start(dict(m, model_children=4), 13, 5)
    assert not C.can_start(dict(m, registered=[dict(pid=1, mem_gb=12)]), 13, 5)
    assert C.can_start(m, 4, 2, pending_models=3, pending_mem=4)
    assert not C.can_start(m, 4, 3, pending_models=3, pending_mem=4)
    assert not C.can_start(m, 4, 2, pending_models=3, pending_mem=12)
    assert C.warned(dict(m, swap_ok=False)) and not C.warned(m)
    name = 'e9_w1_s001_1a_200'
    os.environ.update(SME_JSON_CASE=name, SME_EXACT_SOURCE=C.plan()['cases'][name]['source'])
    sys.argv = ['tools/v3_run.py', '/native/config', '/native/output']
    ns = runpy.run_path(str(ROOT / 'observe_counted.py'), run_name='__mp_main__')
    fn = ns['counted_worker']
    namespace = fn.__globals__
    import smeshared as S
    old_log, old_keys = S._log, S._log_string_keys
    marker = object()
    fixture = ROOT / 'tool_check_fixture'
    fixture.mkdir()
    for label, has_helper in [('fixed', True), ('original', False)]:
        folder = fixture / label
        folder.mkdir()
        namespace['FOLDER'] = folder
        S.LOG.clear()
        sink = io.StringIO()
        S.LOG.update(f=sink, diagnostic=False)
        S._diagnosing = lambda: False
        if has_helper:
            S._log_string_keys = old_keys
            value = {'p': {None: .25, 'name': .75}}
        else:
            del S._log_string_keys
            value = {'kind': 'normal', 'name': 'same'}
        def native(task):
            S._log(value)
            return marker
        namespace['NATIVE_WORKER'] = native
        assert fn({}) is marker
        assert S._log is old_log
        assert hasattr(S, '_log_string_keys') == has_helper
        counts = json.loads((folder / 'json_fallback_counts.json').read_text())
        assert counts['written_records'] == counts['attempted_records'] == int(has_helper)
        if not has_helper:
            assert sink.getvalue() == json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n'
    S._log_string_keys = old_keys
    tree = ast.parse((ROOT / 'controller.py').read_text())
    forbidden = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr in
                 ('kill', 'killpg', 'terminate', 'send_signal', 'unlink', 'rmtree')]
    assert not forbidden
    C.verify()
    result = dict(passed=True, checks=14, pending_model_slots_counted=True,
        unregistered_receipt_reservations_counted=True, original_source_without_helper_supported=True,
        fixed_fallback_one_record_counted=True, original_worker_return_and_normal_record_bytes_unchanged=True,
        wrapper_restoration=True, native_spawn_argv_uses_environment_case=True,
        model_tasks_launched=0, model_signals=0, deletes=0)
    with (ROOT / 'tool_checks.json').open('x') as out:
        out.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
