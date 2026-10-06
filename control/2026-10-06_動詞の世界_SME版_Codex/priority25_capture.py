"""受付と ps を読むだけの軽い確認。処理の開始・停止は行わない。"""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
own = a.workspace / 'codex_verb_2026-10-04'
peer = a.workspace / 'codex_sme_time_evict_2026-10-06'
registry = Path.home() / 'jobs/registry.tsv'
raw = registry.read_bytes()
entries = list(csv.DictReader(io.StringIO(raw.decode()), delimiter='\t'))
ps = subprocess.check_output(['ps', '-axo', 'pid,ppid,stat,lstart,command'], text=True)
rows = []
for line in ps.splitlines()[1:]:
    v = line.split(None, 8)
    if len(v) != 9:
        continue
    pid, ppid, state = int(v[0]), int(v[1]), v[2]
    command = v[8]
    executable = command.split(None, 1)[0]
    if 'python' not in Path(executable).name.lower():
        continue
    rows.append({'pid': pid, 'ppid': ppid, 'state': state,
                 'process_started_local': ' '.join(v[3:8]), 'command': command})
own_rows = [r for r in rows if r['pid'] != os.getpid() and str(own) in r['command']]
own_entries = [r for r in entries if str(own) in r['cmd']]
priority_entries = [r for r in entries if r['owner'].startswith('SME25 ')]
priority_rows = [r for r in rows if str(peer) in r['command']]
relevant_parents = {r['pid'] for r in priority_rows}
for _ in range(6):
    for r in rows:
        if r['ppid'] in relevant_parents:
            relevant_parents.add(r['pid'])
priority_rows = [r for r in rows if r['pid'] in relevant_parents]
completed = {}
for f in ['status.json', 'pilot_A_global_s01/guardian_complete.json',
          'pilot_analysis/reader_status.json', 'final_measurement/reader_status.json']:
    completed[f] = json.loads((own / 'sme_2026-10-06' / f).read_text())
data = {'checked_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'registry_path': str(registry), 'registry_sha256': hashlib.sha256(raw).hexdigest(),
        'own_registered': own_entries, 'own_python_processes': own_rows,
        'own_completed_records': completed,
        'priority25_registered': priority_entries, 'priority25_processes': priority_rows,
        'withdrawn_commands': [], 'restored_commands': [], 'new_jobs_submitted': 0,
        'signals_sent': 0, 'registry_release_calls': 0,
        'confirmation_commands': ['python3 $USER_HOME/jobs/jobs.py status --disk-path $WORKSPACE/codex_verb_2026-10-04/sme_2026-10-06',
                                  'ps -axo pid,ppid,stat,lstart,command'],
        'new_heavy_submissions_held': True,
        'resume_condition': 'both SME25 measurements have started, or two hours have elapsed',
        'no_restore_needed': not own_entries and not own_rows}
assert data['no_restore_needed'], '自分の処理が見つかったので手動で未開始か確認する'
encoded = json.dumps(data, ensure_ascii=False, indent=2)
encoded = encoded.replace(str(a.workspace), '$WORKSPACE').replace(str(Path.home()), '$USER_HOME')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(encoded + '\n')
print(json.dumps({'checked_at': data['checked_at'], 'own_processes': len(own_rows),
                  'own_registered': len(own_entries), 'priority25_registered': priority_entries}, ensure_ascii=False))
