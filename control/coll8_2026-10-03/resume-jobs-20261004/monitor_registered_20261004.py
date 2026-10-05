"""受付表で再開した関門の直近の進行だけを読む。模型は呼ばない。"""
from pathlib import Path
import json
import re
import sys

root = Path(__file__).resolve().parent
ev = root/'evidence/resume-jobs-20261004'
result = json.loads((ev/'gates.json').read_text())

def last_json(path):
    with path.open('rb') as file:
        file.seek(max(0, path.stat().st_size - 131072))
        rows = file.read().splitlines()
    for line in reversed(rows):
        try:
            return json.loads(line)
        except ValueError:
            pass

progress = []
for name in result['active_jobs']:
    spec = json.loads((ev/name/'spec.json').read_text())
    path = Path(spec['argv'][3])
    trial = None
    for state in (path/'comm').glob('*.state.jsonl'):
        row = last_json(state)
        if row is not None:
            trial = row.get('t', -1) + 1
    if trial is None:
        for file in (path/'side').glob('*/*.jsonl'):
            if re.fullmatch(r'seed\d+\.jsonl', file.name) and file.stat().st_size:
                row = last_json(file)
                if row is not None and 'trial' in row:
                    trial = row['trial'] + 1
                    break
    log = (ev/name/'receipt-console.log').read_text()
    progress.append({'name':name, 'trial':trial, 'receipt_message':log[-1000:]})
snapshot = {'status':result['status'], 'gates_status':result.get('gates_status'),
    'completed_new_jobs':result['completed_new_jobs'], 'pending':len(result['pending_jobs']),
    'checks':len(result['checks']), 'active':progress, 'reason':result.get('reason'),
    'profile_started':result.get('profile_started')}
if '--compact' in sys.argv:
    snapshot['completed_new_jobs'] = len(result['completed_new_jobs'])
    snapshot['last_completed'] = result['completed_new_jobs'][-2:]
    snapshot['active'] = [{k:v for k,v in p.items() if k!='receipt_message'}
                          if p['trial'] is not None else p for p in progress]
print(json.dumps(snapshot, ensure_ascii=False))
