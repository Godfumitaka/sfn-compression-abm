"""指示33の確定した比較範囲と原記録の確認後だけ一件を受け付ける。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('readonly_resource', ROOT.parent / 'instruction19_speed_gate/gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def write(path, value):
    with path.open('x') as out:
        out.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def verify(case):
    assert G.stamp()[:19] < '2026-10-11T09:00:00', '期限後の新規投入無し'
    source = Path(case['source'])
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == case['commit']
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=source, text=True).strip()
    assert hashlib.sha256(Path(case['native_command'][2]).read_bytes()).hexdigest() == case['configuration_sha256']
    plan = json.loads((ROOT / 'preparation_manifest.json').read_text())
    for path, digest in plan['immutable_sha256'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    # 結果の前に比較範囲を確定する。elapsed timeは指定の代わりにしない。
    approval = json.loads((ROOT / 'comparison_scope_confirmed.json').read_text())
    assert approval['instruction_receipt_pushed'] and approval['comparison_fixed_before_results']
    assert approval['source_of_scope'] in ('own_inbox_instruction', 'direct_astra')
    if case['observer'] == 'plain':
        assert approval['original_2a_all_files_verified']


def resources(case, registered):
    m = G.machine()
    assert G.start_ok(m) and m['model_children'] + 1 <= 8
    assert sum(x['mem_gb'] for x in m['registered']) + (0 if registered else case['mem_gb']) <= 24
    return m


if __name__ == '__main__':
    action, name = sys.argv[1:]
    assert action in ('run', 'entry')
    case = json.loads((ROOT / 'preparation_manifest.json').read_text())['cases'][name]
    folder = Path(case['folder'])
    verify(case)
    assert not (folder / 'output').exists()
    assert not (ROOT / 'warning.json').exists() and not (ROOT / 'failure.json').exists()
    if action == 'entry':
        m = resources(case, True)
        write(folder / 'entry_started.json', {'at': G.stamp(), 'machine': m, 'source_commit': case['commit'],
            'actual_native_command': case['native_command'], 'production_started': False})
        os.execv(G.PY, [G.PY, str(ROOT / 'observe_counted.py'), name])
    assert not (folder / 'receipt_submitted.json').exists()
    m = resources(case, False)
    command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示33 ' + name,
        '--mem', str(case['mem_gb']), '--disk-path', str(folder / 'output'),
        '--', G.PY, str(ROOT / 'launch.py'), 'entry', name]
    env = os.environ.copy()
    env.update(case['environment'], SME_JSON_CASE=name)
    with (folder / 'run.log').open('x') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        write(folder / 'receipt_submitted.json', {'at': G.stamp(), 'pid': proc.pid, 'command': command,
            'machine': m, 'mem_gb': case['mem_gb'], 'automatic_retry': False, 'production_started': False})
        halted = False
        while proc.poll() is None:
            try:
                # 走行中は期限を理由に模型を止めない。警告後は新規投入無し。
                source = Path(case['source'])
                assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == case['commit']
                assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip()
                current = G.machine()
                warning = (current['model_children'] > 8 or current['disk_free_bytes'] < 18.5 * 2**30
                    or not current['swap_ok'] or current['thermal_warnings'] or current['unregistered_heavy']
                    or sum(x['mem_gb'] for x in current['registered']) > 24)
                if warning and not halted:
                    write(ROOT / 'warning.json', {'at': G.stamp(), 'machine': current, 'models_not_signaled': True})
                    halted = True
            except Exception as exc:
                if not halted:
                    write(ROOT / 'failure.json', {'at': G.stamp(), 'error': repr(exc), 'automatic_retry': False})
                halted = True
            time.sleep(20)
    write(folder / 'receipt_ended.json', {'at': G.stamp(), 'pid': proc.pid, 'exit_code': proc.returncode,
        'actual_child_exit_code': True, 'automatic_retry': False, 'model_signals': 0})
    assert not halted and proc.returncode == 0, '原記録を保全して再試行しない'
    measure = json.loads((folder / 'measurement.json').read_text())
    assert measure['trials'] == case['trials']
    with (folder / 'run.log').open('rb') as stream:
        stream.seek(max(0, (folder / 'run.log').stat().st_size - 65536))
        assert b'ALLDONE' in stream.read()
    rows = G.G.processes()
    assert measure['pid'] not in rows or 'Z' in rows[measure['pid']][1]
    write(folder / 'completed.json', {'at': G.stamp(), 'source_commit': case['commit'],
        'receipt_exit_code': proc.returncode, 'receipt_exit_code_observable': True,
        'trials': case['trials'], 'measurement': measure, 'native_all_done': True,
        'comparison_complete': False, 'production_authorized': False})
