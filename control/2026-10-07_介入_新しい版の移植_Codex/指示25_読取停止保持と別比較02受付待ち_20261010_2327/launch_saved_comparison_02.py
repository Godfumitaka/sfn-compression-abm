"""指示25：保存二本の別比較だけを通常受付へ通す。"""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'instruction22'))
from resource_census_02 import census
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
assert json.loads((HERE/'receipt_delivery_01.json').read_text())['passed']
request=HERE/'saved_tau04_comparison_launch_request_02.json'
assert not request.exists()
case=HERE.parent/'instruction22/candidate_on_D_04_200_01'
assert json.loads((case/'status.json').read_text())['state']=='completed'
rows,active,paused=census()
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=shutil.disk_usage(case/'output').free,swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(HERE/'saved_tau04_before_admission_02.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8 and record['free_disk_bytes']>=20*2**30
argv=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','intervention-instruction25-saved-tau04-comparison02','--mem','1','--disk-path',str(case/'output'),'--',sys.executable,str(HERE/'compare_saved_tau04_02.py'),'candidate_on_D_04_200_01']
epoch=time.time()
with request.open('x') as stream:json.dump(dict(at_jst=record['at_jst'],submitted_epoch=epoch,argv=argv,reservation_gb=1,reservation_basis='off100/B6全量比較実測と25%余裕により新規比較だけ1GB。既存模型や受付の予約は変更しない。'),stream,ensure_ascii=False,indent=2)
with (HERE/'saved_tau04_comparison_admission_02.log').open('xb') as log:
    code=subprocess.call(argv,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
(HERE/'saved_tau04_comparison_admission_completion_02.json').write_text(json.dumps(dict(submitted_epoch=epoch,ended_epoch=time.time(),exit_code=code,independent_admission_wait_seconds=None,independent_cpu_wait_seconds=None),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(exit_code=code,request=str(request)),ensure_ascii=False),flush=True)
sys.exit(code)
