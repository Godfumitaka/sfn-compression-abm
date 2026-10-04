"""新規関門の直近の記録だけを軽く読む。"""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parent
ev = root / 'evidence/restart-20261004'
def last_json(path):
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - 131072))
        lines = f.read().splitlines()
    for line in reversed(lines):
        try: return json.loads(line)
        except ValueError: pass
result = json.loads((ev / 'gates.json').read_text())
job = last_json(ev / 'jobs.jsonl')
state = Path(job['argv'][3]) / 'comm/run001.jsonl.state.jsonl'
trial = last_json(state)['t'] + 1 if state.exists() and state.stat().st_size else None
if trial is None:
    for path in (Path(job['argv'][3]) / 'side').glob('*/*.jsonl'):
        if re.fullmatch(r'seed\d+\.jsonl', path.name) and path.stat().st_size:
            row = last_json(path)
            if row is not None and 'trial' in row:
                trial = row['trial'] + 1
                break
health = last_json(ev / 'run-health.jsonl')
print(json.dumps({'status': result['status'], 'job': job['name'], 'trial': trial,
                  'completed_runs': len(result['runs']), 'checks': len(result['checks']),
                  'reason': result.get('reason'), 'rss_bytes': health['rss_sum_bytes'],
                  'swap_mib': health['swap_mib'], 'foreign_heavy': len(health['foreign_heavy']),
                  'last_checks': [[c['name'],c['passed']] for c in result['checks'][-2:]]},
                 ensure_ascii=False))
