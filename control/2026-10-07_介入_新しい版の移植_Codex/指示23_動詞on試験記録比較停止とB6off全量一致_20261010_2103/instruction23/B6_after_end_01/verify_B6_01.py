"""外側の終了だけで通さず、模型の完了と全控えを通常受付で点検する。"""
from pathlib import Path
import ast
import copy
import datetime
import gzip
import hashlib
import json
import shutil
import subprocess
import sys

here = Path(__file__).resolve().parent
port = here.parents[1]
b5 = port / 'instruction12/B5'
label = 'B6_off_on200_candidate03'
case = port / 'instruction21/B6_gate_03' / label
result_path = here / 'verification_01.json'
assert not result_path.exists()
sys.path.insert(0, str(port/'instruction22'))
from resource_census_02 import census
rows_ps, active, paused = census()
assert len(active) < 8 and shutil.disk_usage(case/'output').free >= 20 * 2**30
at = datetime.datetime.now().astimezone().isoformat()
with (here / 'verification_before_start_01.json').open('x') as f:
    json.dump(dict(at_jst=at, active=len(active), paused=len(paused),
        processes=[dict(pid=p, **rows_ps[p]) for p in sorted(active | paused)],
        free_disk_bytes=shutil.disk_usage(case/'output').free), f, ensure_ascii=False, indent=2)

def read(path):
    return json.loads(path.read_text())

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def lines(path):
    with (gzip.open(path, 'rb') if path.suffix == '.gz' else path.open('rb')) as f:
        yield from f

reference = read(b5 / 'command_reference.json')
assert sha(b5 / 'reference_compare.py') == reference[next(p for p in reference if p.endswith('/compare.py'))]
tree = ast.parse((b5 / 'reference_compare.py').read_text())
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ['checked_done', 'rows']]
assert len(selected) == 2
exec(compile(ast.Module(body=selected, type_ignores=[]), str(b5 / 'reference_compare.py'), 'exec'), globals())
result = dict(at_jst=at, state='stopped', case=label, passed=False, production_started=False)
current = str(case / 'status.json')
try:
    status = read(Path(current))
    command = read(case / 'runtime.json')
    fixed = read(case.parent / 'commands_B6_03.json')[label]
    assert status['command'] == fixed
    assert all(command[key] == value for key, value in fixed.items())
    assert status['state'] == 'completed' and status['exit_code'] == 0 and status['protected_unchanged'], status
    count = int(command['model_argv'][command['model_argv'].index('--trial-count') + 1])
    assert count == 200 and command['models'] == 1 and command['seeds'] == [1]
    assert read(case / 'protected_before.json') == read(case / 'protected_after.json')
    protected = read(case / 'protected_before.json')
    for root, files in protected.items():
        for name, digest in files.items():
            current = str(Path(root) / name)
            assert sha(Path(current)) == digest, current
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=command['cwd'], text=True).strip() == command['commit']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=command['cwd'], text=True).strip()
    output = case / 'output'
    ledgers = list((output / 'ledgers/cells').glob('*/*.jsonl.gz'))
    dones = list((output / 'ledgers/cells').glob('*/*.done'))
    assert len(ledgers) == len(dones) == 1, (len(ledgers), len(dones))
    current = str(ledgers[0])
    records = rows(ledgers[0]); head = next(records)
    assert head['code_commit'] == command['commit'] and head['trial_count'] == count
    actual = 0
    for i, row in enumerate(records):
        assert row['prediction_order'] == i and row['f_realized'] == head['f_setting'], i
        actual += 1
    assert actual == count, actual
    current = str(dones[0]); done = read(dones[0])
    checked_done(done, output, command['commit'])
    assert done['trial_count'] == count
    current = str(output / 'manifest.jsonl')
    manifest = list(rows(Path(current)))
    assert len(manifest) == 1 and not manifest[0].get('error'), manifest
    assert manifest[0]['trial_count'] == count
    checked_done(manifest[0], output, command['commit'])
    current = str(output / 'comm/run001.summary.json')
    comm = read(Path(current))
    assert comm['trials'] == count and not comm['errors'] and len(comm['agents']) == 1
    for agent in comm['agents']:
        assert not agent.get('error') and agent.get('type') != 'error', agent
        checked_done(agent, output, command['commit'])
        assert agent['v39'].get('not_in_dictionary', 0) == 0
        assert agent['v311c']['dictionary_checks'] == 2 * count
    rng_checks = {}
    for suffix in ['model-rng.jsonl', 'rng.jsonl']:
        current = str(case / ('agent0.' + suffix)); total = 0
        for i, row in enumerate(rows(Path(current))):
            assert row['trial'] == i and row['python_global_unchanged'], i
            total += 1
        assert total == count, total
        rng_checks[suffix] = total
    for suffix in ['final-sme.jsonl.gz', 'cstar-final.json']:
        current = str(case / ('agent0.' + suffix))
        assert Path(current).is_file() and Path(current).stat().st_size > 0
    performance = list(rows(case / 'agent0.performance.jsonl'))
    assert [row['trial'] for row in performance] == list(range(count))
    final_phase = list(rows(case / 'agent0.validation.jsonl'))
    assert [row['phase'] for row in final_phase] == ['begin', 'end']
    hashes = {str(p.relative_to(case)): dict(sha256=sha(p), bytes=p.stat().st_size)
              for p in case.rglob('*') if p.is_file()}
    result.update(state='passed', passed=True, trial_count=count, ledger_rows=actual,
        source_commit=command['commit'], machine_boot_sha256=read(case / 'before_start.json')['machine_boot_sha256'],
        manifest_records=len(manifest), communication_errors=0, agent_errors=0,
        dictionary_checks=2 * count, rng_records=rng_checks, observer_sha256=sha(case.parent / 'observe.py'),
        protected_unchanged=True, peak_agent_rss_bytes=max(row['peak_rss_bytes'] for row in performance),
        peak_children_rss_bytes=status['peak_children_rss_bytes'],
        admission_wait_seconds=status['admission_wait_seconds'], cpu_wait_seconds=status['cpu_wait_seconds'],
        model_seconds=status['model_seconds'], completed_at_jst=status['ended_at_jst'], all_case_files=hashes)
except Exception as exc:
    result.update(first_error=dict(file=current, error=repr(exc)))
with result_path.open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
print(json.dumps({k: result[k] for k in ['state', 'case', 'passed', 'first_error', 'trial_count', 'peak_agent_rss_bytes'] if k in result}, ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
