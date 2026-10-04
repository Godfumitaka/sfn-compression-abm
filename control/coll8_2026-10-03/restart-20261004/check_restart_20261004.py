"""再開の段1：既存の個体記録・差分・関連構造検査。模型の走行はしない。"""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parent
source = root / 'source'
ev = root / 'evidence/restart-20261004'
ev.mkdir(exist_ok=True)
records = []
for job in [f'baseline_a{i}' for i in range(8)] + [f'solo_r1_a{i}' for i in range(8)]:
    path = root / 'outputs' / job / 'manifest.jsonl'
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if 'v39' not in row:
            records.append({'job': job, 'path': str(path), 'counter_available': False})
            continue
        stats = row['v39']
        records.append({'job': job, 'path': str(path), 'seed': row.get('seed'),
                        'counter_available': True, 'counter_field_present': 'not_in_dictionary' in stats,
                        'not_in_dictionary': stats.get('not_in_dictionary', 0)})
summary = {'scope': 'この作業場所に保存した個体版8本・独立した一個体走行8本',
           'export': 'tools/v3_run.py:544-545でv39.STATS全体を保存',
           'absence_meaning': 'v39.py:93は辞書外発生時にだけ動的カウンタを作る。全STATSの書出しで欄なしは未発生',
           'records': records, 'available': sum(r['counter_available'] for r in records),
           'positive': sum(r.get('not_in_dictionary', 0) >= 1 for r in records)}
(ev / 'existing-individual-dictionary-counts.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
assert summary['available'] == 16 and summary['positive'] == 0
changes = subprocess.check_output(['git', 'diff', '909b1e2', '--', 'abm/', 'tools/v39.py',
                                   'tools/v310be.py', 'tools/v3_run.py', 'config/'], cwd=source)
assert not changes
(ev / 'unchanged-model-files.json').write_text(json.dumps({'comparison_commit': '909b1e2',
    'unchanged': ['abm/', 'tools/v39.py', 'tools/v310be.py', 'tools/v3_run.py', 'config/']}, indent=1) + '\n')
(ev / 'code.diff').write_bytes(subprocess.check_output(['git', 'diff', '909b1e2'], cwd=source))
files = [r['file'] for r in json.loads((root / 'evidence/canonical-unit-suite.json').read_text())]
files.append('test_v311c_dictionary_guard.py')
results = []
for file in files:
    argv = ['/opt/homebrew/bin/uv', 'run', '--offline', '--no-project', '--python',
            '/opt/homebrew/opt/python@3.12/bin/python3.12', '--with', 'pytest==9.1.1',
            'python', '-m', 'pytest', '-q', 'tests/' + file]
    p = subprocess.run(argv, cwd=source, text=True, capture_output=True)
    results.append({'file': file, 'argv': argv, 'returncode': p.returncode, 'output': p.stdout + p.stderr})
    (ev / 'unit-suite.json').write_text(json.dumps(results, ensure_ascii=False, indent=1) + '\n')
    print(file, p.returncode, p.stdout.strip().splitlines()[-1], flush=True)
    assert p.returncode == 0
