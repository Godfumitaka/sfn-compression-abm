"""自然終了した一本の新旗offを、原比較器で一度通常受付へ通す。"""
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

here = Path(__file__).resolve().parent
work = here.parent / 'instruction22'
sys.path.insert(0, str(work))
from resource_census_02 import census

assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
request = here / 'off100_comparison_launch_request_02.json'
assert not request.exists(), '同じ比較受付を重複登録しない'
assert not (work / 'candidate_off100_comparison_02.json').exists()
case = work / 'candidate_off100_01'
status = json.loads((case / 'status.json').read_text())
assert status['state'] == 'completed' and status['exit_code'] == 0
assert status['completed_trials'] == 100 and status['protected_unchanged']
rows, active, paused = census()
record = dict(at_jst=datetime.datetime.now().astimezone().isoformat(), active=len(active), paused=len(paused),
    active_pids=sorted(active), paused_pids=sorted(paused), ps=rows,
    free_disk_bytes=shutil.disk_usage(case / 'output').free,
    swap=subprocess.check_output(['sysctl', 'vm.swapusage'], text=True),
    thermal=subprocess.check_output(['pmset', '-g', 'therm'], text=True))
with (here / 'off100_comparison_before_admission_02.json').open('x') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
assert len(active) < 8 and record['free_disk_bytes'] >= 20 * 2**30
epoch = time.time()
argv = [sys.executable, str(Path.home() / 'jobs/jobs.py'), 'run', '--wait', '--owner',
    'intervention-instruction23-verb-off100-comparison02', '--mem', '0.3',
    '--disk-path', str(case / 'output'), '--', sys.executable,
    str(work / 'compare_candidate_off100_02.py')]
with request.open('x') as stream:
    json.dump(dict(at_jst=record['at_jst'], submitted_epoch=epoch, argv=argv, reservation_gb=0.3,
        policy='全名前・原順・全字節・全研究者辞書、試験行、完了札実サイズと実版。原既存TIMEだけ。'),
        stream, ensure_ascii=False, indent=2)
with (here / 'off100_comparison_admission_02.log').open('xb') as log:
    code = subprocess.call(argv, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=log, stderr=subprocess.STDOUT)
with (here / 'off100_comparison_admission_exit_02.json').open('x') as stream:
    json.dump(dict(at_jst=datetime.datetime.now().astimezone().isoformat(), exit_code=code,
        admission_and_comparison_seconds=time.time()-epoch, independent_cpu_wait_seconds=None), stream, indent=2)
sys.exit(code)
