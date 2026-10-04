"""受付表で受け付けられた一枠の中で、部品・13本・全走行・計測を順に行う。"""
from pathlib import Path
import csv
from datetime import datetime
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
SOURCE = HERE / 'source'
PYTHON = '/opt/homebrew/opt/python@3.12/bin/python3.12'
TEST_PYTHON = WORK / 'codex_sme_impl_2026-10-03/testenv/bin/python'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compare = load('exact_compare', WORK / 'codex_sme_fast_2026-10-03/exact_tools/compare.py')
resources = load('resource_check', WORK / 'codex_sme_fast_2026-10-03/exact_tools/run_one.py')
jobs = load('job_registry', Path('/Users/tatsu-admin/jobs/jobs.py'))


def check_space():
    row = resources.resources(HERE)
    row['registered_jobs'] = jobs.read_reg()
    ps = jobs.procs()
    row['all_heavy_python'] = [{'pid': p, 'rss_mb': r, 'cmd': c} for p, (_pp, r, c) in ps.items() if jobs.heavy(c, r)]
    with (HERE / 'resources.jsonl').open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    if row['free_bytes'] < 18 * 2**30 or jobs.therm()[0]:
        raise RuntimeError('次の重い処理を始める余裕が無い')
    return row


def run(command, folder, *, model=False, profile=False):
    check_space()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / 'run_result.json').exists() or (folder / 'run.log').exists():
        raise RuntimeError('二重実行・上書きをしない')
    env = dict(os.environ, SME_EXACT_SOURCE=str(SOURCE), PYTHONHASHSEED='0', SME_LIGHT_PROFILE='1' if profile else '0')
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    actual = [PYTHON, str(HERE / 'observe.py'), str(folder / 'command.json')] if model else command
    began = time.perf_counter(); start = datetime.now().astimezone().isoformat()
    with (folder / 'run.log').open('w') as stream:
        child = subprocess.Popen(actual, cwd=SOURCE, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while child.poll() is None:
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    row = resources.resources(HERE)
                    with (folder / 'resources.jsonl').open('a') as out:
                        out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    print(folder.name + '：実行中', flush=True)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait()
    result = {'exit': child.returncode, 'wall_seconds': time.perf_counter() - began,
              'started': start, 'ended': datetime.now().astimezone().isoformat(), 'command': command}
    (folder / 'run_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if child.returncode:
        raise RuntimeError(folder.name + '失敗：' + (folder / 'run.log').read_text()[-2200:])
    print(folder.name + '：終了', flush=True)
    return result


def main():
    state = {'start': datetime.now().astimezone().isoformat(), 'completed': []}
    try:
        for name in ('verify_rng.py', 'verify_keys.py'):
            run([str(TEST_PYTHON), str(HERE / 'component_01' / name)], HERE / 'component_01' / name.removesuffix('.py'))
        run([str(TEST_PYTHON), '-m', 'pytest', '-q', 'tools/test_argorder_component.py', 'tools/test_sme2017_component.py', 'tools/test_sme2017_connection.py'], HERE / 'tests_01')
        state['completed'].append('component')
        timings = []
        small = HERE / 'proof_small_01'
        for row in json.loads((small / 'plan.json').read_text()):
            folder = small / row['name']
            run(row['command'], folder, model=True)
            old = WORK / 'codex_sme_fast_2026-10-03/exact_small_01/baseline' / row['name'] / 'output'
            proof = compare.compare(old, folder / 'output')
            (folder / 'comparison.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
            if not proof['all_bytes_equal']:
                raise RuntimeError('sec_trial以外に不一致。案を採用しない：' + row['name'])
            for record in proof['records']:
                for timing in record.get('timing_values', []):
                    timings.append({'run': row['name'], 'file': record['file'], **timing})
            state['completed'].append(row['name'])
        with (small / 'sec_trial_values.csv').open('w', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=list(timings[0])); writer.writeheader(); writer.writerows(timings)
        (small / 'summary.json').write_text(json.dumps({'runs': 13, 'total_trials': 260, 'all_bytes_equal_except_sec_trial': True, 'timing_rows': len(timings)}, ensure_ascii=False, indent=2) + '\n')
        full = HERE / 'proof_full_01'
        command = json.loads((full / 'command.json').read_text())
        run(command, full, model=True)
        proof = compare.compare(WORK / 'codex_sme_fast_2026-10-03/exact_full_01/baseline/output', full / 'output')
        (full / 'comparison.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
        if not proof['all_bytes_equal']:
            raise RuntimeError('全走行で不一致。案を採用しない')
        state['completed'].append('full_1740_exact')
        profile = HERE / 'profile_200_01'
        run(json.loads((profile / 'command.json').read_text()), profile, model=True, profile=True)
        state['completed'].append('profile_200')
        run([PYTHON, str(HERE / 'collective_counts.py'), str(HERE / 'collective_counts_registered.json')], HERE / 'collective_counts_01')
        state['completed'].append('collective_existing_records')
        state['passed'] = True
    except Exception as error:
        state['passed'] = False
        state['error'] = str(error)
        raise
    finally:
        state['end'] = datetime.now().astimezone().isoformat()
        (HERE / 'pipeline_result.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
