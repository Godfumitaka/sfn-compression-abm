"""構造合格後だけ、新旗off一本を一度通常受付へ通す。"""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,time
from resource_census_02 import census
here=Path(__file__).resolve().parent
assert not (here/'off100_launch_request_01.json').exists()
gate=json.loads((here/'structure_status_01.json').read_text())
assert gate['passed'] and gate['protected_unchanged']
rows,active,paused=census();free=shutil.disk_usage(here).free
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
    active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(here/'before_off100_admission_01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)+1<=8 and free>=20*2**30
epoch=time.time()
cmd=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner',
    'intervention-instruction22-verb-candidate-off100-01','--mem','0.6','--disk-path',
    str(here/'candidate_off100_01/output'),'--',sys.executable,str(here/'run_candidate_off100_01.py')]
(here/'off100_launch_request_01.json').write_text(json.dumps(dict(at_jst=record['at_jst'],submitted_epoch=epoch,
    argv=cmd,reservation_gb=.6),ensure_ascii=False,indent=2)+'\n')
with (here/'off100_admission_01.log').open('xb') as log:
    code=subprocess.call(cmd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
        'INTERVENTION22_OFF_SUBMITTED_EPOCH':str(epoch)},stdout=log,stderr=subprocess.STDOUT)
sys.exit(code)
