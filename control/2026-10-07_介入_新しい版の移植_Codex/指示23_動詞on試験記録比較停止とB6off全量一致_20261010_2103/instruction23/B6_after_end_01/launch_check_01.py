"""同じ模型の自然終了後だけ、点検又は全量比較を一度通常受付へ通す。"""
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

here = Path(__file__).resolve().parent
port = here.parents[1]
sys.path.insert(0, str(port/'instruction22'))
from resource_census_02 import census

mode = sys.argv[1]
assert mode in ('verification', 'comparison')
case = port/'instruction21/B6_gate_03/B6_off_on200_candidate03'
status = json.loads((case/'status.json').read_text())
assert status['state'] == 'completed' and status['exit_code'] == 0 and status['protected_unchanged']
assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
request = here/f'{mode}_launch_request_01.json'
assert not request.exists(), '同じ受付を重複登録しない'
if mode == 'comparison':
    verification = json.loads((here/'verification_01.json').read_text())
    assert verification['passed'] and verification['trial_count'] == 200
rows, active, paused = census()
record = dict(at_jst=datetime.datetime.now().astimezone().isoformat(), active=len(active), paused=len(paused),
    active_pids=sorted(active), paused_pids=sorted(paused), ps=rows,
    free_disk_bytes=shutil.disk_usage(case/'output').free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'], text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'], text=True))
with (here/f'{mode}_before_admission_01.json').open('x') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
assert len(active) < 8 and record['free_disk_bytes'] >= 20*2**30
reservation = .3 if mode == 'verification' else .6
script = here/('verify_B6_01.py' if mode == 'verification' else 'compare_B6_01.py')
epoch = time.time()
argv = [sys.executable, str(Path.home()/'jobs/jobs.py'), 'run', '--wait', '--owner',
        f'intervention-instruction23-B6-off200-{mode}01', '--mem', str(reservation),
        '--disk-path', str(case/'output'), '--', sys.executable, str(script)]
with request.open('x') as stream:
    json.dump(dict(at_jst=record['at_jst'], submitted_epoch=epoch, argv=argv,
        reservation_gb=reservation, reservation_basis='B5必要点検0.3GBと指定全量比較の実測最大RSS528777216Bを保持'),
        stream, ensure_ascii=False, indent=2)
with (here/f'{mode}_admission_01.log').open('xb') as log:
    code = subprocess.call(argv, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1',
        'INTERVENTION_COMPARISON_SUBMITTED_EPOCH':str(epoch)}, stdout=log, stderr=subprocess.STDOUT)
sys.exit(code)
