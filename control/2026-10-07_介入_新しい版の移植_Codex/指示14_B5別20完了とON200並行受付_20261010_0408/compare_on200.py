"""B5の同一機械・同じ一体ON200。既存比較関数で全出力を読む。"""
import ast
import copy
import datetime
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
reference = read(here / 'command_reference.json')
for path, digest in reference.items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
assert hashlib.sha256((here / 'reference_compare.py').read_bytes()).hexdigest() == reference[next(p for p in reference if p.endswith('/compare.py'))]
tree = ast.parse((here / 'reference_compare.py').read_text())
functions = ['lines', 'encode', 'byte_check', 'header_diff', 'checked_done', 'normalized']
selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
assert len(selected) == len(functions)
exec(compile(ast.Module(body=selected, type_ignores=[]), str(here / 'reference_compare.py'), 'exec'), globals())

labels = ['B5_on200_before', 'B5_on200_after']
cases = [here / label for label in labels]
statuses = [read(case / 'status.json') for case in cases]
commands = [read(case / 'runtime.json') for case in cases]
for status in statuses:
    assert status['state'] == 'completed' and status['exit_code'] == 0 and status['protected_unchanged']
machines = [read(case / 'before_start.json')['machine_boot_sha256'] for case in cases]
assert machines[0] == machines[1]
assert commands[0]['config_sha256'] == commands[1]['config_sha256']
assert commands[0]['model_argv'][3:] == commands[1]['model_argv'][3:]
assert commands[0]['models'] == commands[1]['models'] == 1
commits = tuple(c['commit'] for c in commands)
outputs = [case / 'output' for case in cases]
maps = [{str(p.relative_to(out)): p for p in out.rglob('*') if p.is_file()} for out in outputs]
checks = []
metadata = []
if maps[0].keys() != maps[1].keys():
    checks.append(dict(name='全出力の名前集合', passed=False, first_difference=None,
                       left_only=sorted(maps[0].keys()-maps[1].keys()), right_only=sorted(maps[1].keys()-maps[0].keys())))

def finished_rows(path, out, commit):
    for raw in lines(path):
        row = json.loads(raw)
        assert row['trial_count'] == 200 and not row.get('error')
        yield encode(checked_done(row, out, commit))

def comm_records(path, out, commit):
    for raw in lines(path):
        row = json.loads(raw)
        if row.get('kind') == 'summary':
            row['agents'] = [checked_done(v, out, commit) for v in row['agents']]
            yield encode(row)
        else:
            yield raw

for name in sorted(maps[0].keys() & maps[1].keys()):
    paths = [m[name] for m in maps]
    if name.startswith('ledgers/') and name.endswith('.jsonl.gz'):
        streams = [lines(path) for path in paths]
        heads = [json.loads(next(stream)) for stream in streams]
        metadata.append(dict(file=name, differences=header_diff(*heads, commits)))
        for path, head in zip(paths, heads):
            assert head['trial_count'] == 200
            body = [json.loads(raw) for raw in lines(path)][1:]
            assert len(body) == 200 and [v['prediction_order'] for v in body] == list(range(200))
        values = streams
    elif name.endswith('.done'):
        values = [[encode(checked_done(read(path), out, commit))] for path, out, commit in zip(paths, outputs, commits)]
    elif name == 'manifest.jsonl':
        values = [finished_rows(path, out, commit) for path, out, commit in zip(paths, outputs, commits)]
    elif name == 'flag.json':
        values = []
        for path, commit in zip(paths, commits):
            raw = path.read_bytes()
            row = json.loads(raw)
            assert row['commit'] == commit and row['config'] == commands[0]['config']
            token = ('"commit": "' + commit + '"').encode()
            assert raw.count(token) == 1
            values.append([raw.replace(token, b'"commit": ""')])
        metadata.append(dict(file=name, differences=['実版と照合したcommitのみ']))
    elif name == 'comm/run001.summary.json':
        values = []
        for path, out, commit in zip(paths, outputs, commits):
            row = read(path)
            assert row['trials'] == 200 and not row['errors'] and len(row['agents']) == 1
            row['agents'] = [checked_done(v, out, commit) for v in row['agents']]
            values.append([encode(row)])
    elif name == 'comm/run001.jsonl':
        values = [comm_records(path, out, commit) for path, out, commit in zip(paths, outputs, commits)]
    else:
        values = [normalized(path) for path in paths]
    checks.append(byte_check(name, *values))

for suffix in ['final-sme.jsonl.gz', 'model-rng.jsonl', 'rng.jsonl', 'cstar-final.json']:
    paths = [case / ('agent0.' + suffix) for case in cases]
    assert all(path.is_file() for path in paths), suffix
    checks.append(byte_check('研究者の全状態と乱数：' + suffix, *(lines(path) for path in paths)))
for case in cases:
    rows = [json.loads(raw) for raw in lines(case / 'agent0.model-rng.jsonl')]
    assert len(rows) == 200 and all(row['python_global_unchanged'] for row in rows)
result = dict(at_jst=datetime.datetime.now().astimezone().isoformat(),
              passed=bool(checks) and all(row['passed'] for row in checks), candidate=commits[1], baseline=commits[0],
              machine_boot_sha256=machines[0], checks=checks, mandatory_metadata=metadata,
              left_names=sorted(maps[0]), right_names=sorted(maps[1]), model_rows_excluded=0,
              original_comparison_reference=reference,
              first_mismatch=next((row for row in checks if not row['passed']), None),
              exclusions=['実版と物理サイズを照合したcode_commit/ledger_bytes',
                          'done/manifest/終了集計のelapsed_sec/finished_at/peak_rss_mb',
                          '既存cfvalue.sec_trial、stage2.seconds/wrapper_seconds/summary.seconds',
                          'flagの実版照合済みcommitだけ。全模型行・順・状態・乱数は保持'])
result['state'] = 'passed' if result['passed'] else 'stopped'
with (here / 'on200_comparison_01.json').open('x') as out:
    out.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(state=result['state'], first_mismatch=result['first_mismatch'], files=len(maps[0])), ensure_ascii=False))
sys.exit(0 if result['passed'] else 1)
