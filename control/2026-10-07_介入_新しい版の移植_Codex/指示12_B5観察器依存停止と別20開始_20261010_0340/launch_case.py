"""実際の受付前時刻と受付PIDを保存し、通常受付だけを呼ぶ。"""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import time

here = Path(__file__).resolve().parent
label, memory = sys.argv[1:]
assert not (here / label).exists()
spec = json.loads((here / 'commands.json').read_text())[label]
assert spec['reservation_gb'] is not None and float(memory) == spec['reservation_gb']
log = here / (label + '_admission.log')
record = here / (label + '_launch_request.json')
assert not log.exists() and not record.exists()
submitted = time.time()
env = dict(os.environ, INTERVENTION_ADMISSION_SUBMITTED_EPOCH=str(submitted), PYTHONDONTWRITEBYTECODE='1')
argv = [sys.executable, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner',
        'intervention-instruction12-' + label, '--mem', memory, '--disk-path', str(here),
        '--', sys.executable, str(here / 'run_case.py'), label]
row = dict(at_jst=datetime.datetime.now().astimezone().isoformat(), submitted_epoch=submitted,
           label=label, argv=argv, production_started=False)
with log.open('xb') as out:
    child = subprocess.Popen(argv, env=env, stdout=out, stderr=subprocess.STDOUT)
    row['admission_pid'] = child.pid
    record.write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)
    code = child.wait()
row.update(exit_code=code, ended_at_jst=datetime.datetime.now().astimezone().isoformat())
record.write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
sys.exit(code)
