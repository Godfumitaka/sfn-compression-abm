"""同じ既存記録解析を一度だけ通常受付へ通す。"""
from pathlib import Path
from datetime import datetime
import json,os,shutil,subprocess,sys,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'instruction22'))
from resource_census_02 import census
assert json.loads((HERE/'receipt_delivery_01.json').read_text())['passed']
assert datetime.now().astimezone()<datetime.fromisoformat('2026-10-13T09:00:00+09:00')
request=HERE/'analysis_launch_request_02.json'
assert not request.exists()
rows,active,paused=census()
record=dict(at_jst=datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=shutil.disk_usage(HERE).free,swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(HERE/'analysis_before_admission_02.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8 and record['free_disk_bytes']>=20*2**30
argv=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','intervention-instruction26-existing-times-analysis02','--mem','0.3','--disk-path',str(HERE),'--',sys.executable,str(HERE/'analyze_existing_02.py')]
epoch=time.time()
with request.open('x') as f:json.dump(dict(at_jst=record['at_jst'],submitted_epoch=epoch,argv=argv,reservation_gb=.3,reservation_basis='原時間記録を数MB以内のJSONLとして読取のみ。これまでの構造/小さい証拠解析の0.3GB予約を継承し、RSSを実測保存。'),f,ensure_ascii=False,indent=2)
with (HERE/'analysis_admission_02.log').open('xb') as log:
    code=subprocess.call(argv,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
(HERE/'analysis_admission_completion_02.json').write_text(json.dumps(dict(submitted_epoch=epoch,ended_epoch=time.time(),exit_code=code,independent_admission_wait_seconds=None,independent_cpu_wait_seconds=None),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(exit_code=code)))
sys.exit(code)
