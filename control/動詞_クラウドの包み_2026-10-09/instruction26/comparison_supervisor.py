from pathlib import Path
from datetime import datetime, timezone
import json, os, subprocess, sys

ROOT = Path(__file__).resolve().parent
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'

def save(state, **values):
    (ROOT/'comparison_supervisor_status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(), supervisor_pid=os.getpid(), state=state, model_starts=0, **values),ensure_ascii=False,indent=2)+'\n')

assert not (ROOT/'comparison_supervisor_status.json').exists(), '読取監督の二重起動をしない'
assert json.loads((ROOT/'receipt_published.json').read_text())['push_succeeded']
for number in (20,22):
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    assert not (ROOT/f'comparison{number}_status.json').exists()
    save('reading', gate=number)
    command = [PY, str(Path.home()/'jobs/jobs.py'), 'run', '--wait', '--mem', '0.3', '--disk-path', str(ROOT), '--owner', f'Codex 動詞 指示26 原関門{number}全ファイル読取', '--', PY, str(ROOT/'read_compare.py'), str(number)]
    with (ROOT/f'comparison{number}.jobs.log').open('x') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        save('stopped', gate=number, exit_code=result.returncode)
        sys.exit(result.returncode)
    assert json.loads((ROOT/f'comparison{number}_approved.json').read_text())['passed']
save('both_readonly_gates_passed', gates=[20,22], production_started=False)
