"""指示22：同じ受付を再登録しないため投入時刻と命令を先に保存する。"""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,time
from resource_census_01 import census
here=Path(__file__).resolve().parent
assert not (here/'launch_request_01.json').exists(), '同じ診断の重複投入を拒否'
spec=json.loads((here/'reproduction_spec_01.json').read_text())
rows,active,paused=census()
free=shutil.disk_usage(here).free
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
    active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(here/'before_admission_01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)+1<=8 and free>=20*2**30, '模型又は容量の受付条件待ち'
epoch=time.time()
cmd=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','intervention-instruction22-verb-seed7-tau04-diagnosis01',
     '--mem','0.6','--disk-path',str(Path(spec['destination'])/'output'),'--',sys.executable,str(here/'run_reproduction_01.py')]
(here/'launch_request_01.json').write_text(json.dumps(dict(submitted_epoch=epoch,
    submitted_at_jst=datetime.datetime.now().astimezone().isoformat(),argv=cmd,reservation_gb=.6),ensure_ascii=False,indent=2)+'\n')
env=dict(os.environ,INTERVENTION22_SUBMITTED_EPOCH=str(epoch),PYTHONDONTWRITEBYTECODE='1')
with (here/'admission_01.log').open('xb') as log:
    code=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
(here/'admission_exit_01.json').write_text(json.dumps(dict(exit_code=code,ended_at_jst=datetime.datetime.now().astimezone().isoformat()))+'\n')
sys.exit(code)
