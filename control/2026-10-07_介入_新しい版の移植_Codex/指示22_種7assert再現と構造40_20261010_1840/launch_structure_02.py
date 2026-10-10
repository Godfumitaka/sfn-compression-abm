"""指示22：構造だけを同じ通常受付へ一回投入する。"""
from pathlib import Path
import datetime, json, os, shutil, subprocess, sys, time
from resource_census_02 import census
here=Path(__file__).resolve().parent
assert not (here/'structure_launch_request_02.json').exists()
rows,active,paused=census()
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
            active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,
            free_disk_bytes=shutil.disk_usage(here).free,
            swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
            thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(here/'before_structure_02.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8 and record['free_disk_bytes']>=20*2**30
cmd=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait',
     '--owner','intervention-instruction22-verb-candidate-structure01',
     '--mem','0.3','--disk-path',str(here/'structure_01'),'--',sys.executable,str(here/'check_candidate_02.py')]
(here/'structure_launch_request_02.json').write_text(json.dumps(dict(at_jst=record['at_jst'],
    submitted_epoch=time.time(),argv=cmd),ensure_ascii=False,indent=2)+'\n')
with (here/'structure_admission_02.log').open('xb') as log:
    code=subprocess.call(cmd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
sys.exit(code)
