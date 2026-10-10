"""新旗offの全量合格後だけ、指定の修正on関門を一度通常受付へ通す。"""
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from resource_census_02 import census

here = Path(__file__).resolve().parent
mode, label = sys.argv[1:]
assert mode in ('model', 'verification', 'comparison')
assert label in ('candidate_on_D_04_200_01', 'candidate_on_D_015_200_01')
assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
spec = json.loads((here/'candidate_on200_commands_02.json').read_text())[label]
off = json.loads(Path(spec['requires_off_comparison']).read_text())
assert off['passed'] and off['actual_files_excluded'] == off['probe_rows_excluded'] == 0
structure = json.loads(Path(spec['requires_structure']).read_text())
assert structure['passed'] and structure['protected_unchanged'] and structure['exit_code'] == 0
request = here/f'{label}_{mode}_launch_request_02.json'
assert not request.exists(), '同じ受付を重複登録しない'
case = Path(spec['destination'])
if mode == 'model':
    assert not case.exists(), '同じ模型を重複起動しない'
    if label == 'candidate_on_D_015_200_01':
        first = json.loads((here/'candidate_on_D_04_200_01_comparison_02.json').read_text())
        assert first['passed'], '最初の不一致で後続を止める'
else:
    status = json.loads((case/'status.json').read_text())
    assert status['state'] == 'completed' and status['exit_code'] == 0 and status['protected_unchanged']
    if mode == 'comparison':
        assert json.loads((here/(label+'_verification_02.json')).read_text())['status'] == 'passed'
rows, active, paused = census()
record = dict(at_jst=datetime.datetime.now().astimezone().isoformat(), active=len(active), paused=len(paused),
    active_pids=sorted(active), paused_pids=sorted(paused), ps=rows,
    free_disk_bytes=shutil.disk_usage(here).free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'], text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'], text=True))
with (here/f'{label}_{mode}_before_admission_02.json').open('x') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
assert len(active) < 8 and record['free_disk_bytes'] >= 20*2**30
reservation = spec['reservation_gb'] if mode == 'model' else .3
script = {'model':'run_candidate_on200_02.py', 'verification':'verify_candidate_on200_02.py',
          'comparison':'compare_candidate_on200_02.py'}[mode]
epoch = time.time()
argv = [sys.executable, str(Path.home()/'jobs/jobs.py'), 'run', '--wait', '--owner',
        f'intervention-instruction23-verb-{label}-{mode}02', '--mem', str(reservation),
        '--disk-path', str(case/'output'), '--', sys.executable, str(here/script), label]
with request.open('x') as stream:
    json.dump(dict(at_jst=record['at_jst'], submitted_epoch=epoch, argv=argv, reservation_gb=reservation,
        reservation_basis='模型は指示13の先頭200の実測最大335036416Bと余裕、点検比較は既存0.3GB'),
        stream, ensure_ascii=False, indent=2)
with (here/f'{label}_{mode}_admission_02.log').open('xb') as log:
    code = subprocess.call(argv, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1',
        'INTERVENTION22_ON_SUBMITTED_EPOCH':str(epoch)}, stdout=log, stderr=subprocess.STDOUT)
sys.exit(code)
