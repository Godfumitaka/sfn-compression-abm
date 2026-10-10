"""自然終了後の必要記録・成分比較を、同じ通常受付へ一度だけ通す。"""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'instruction22'))
from resource_census_02 import census
mode,label=sys.argv[1:]
assert mode in ('verification','comparison')
assert label in ('left_tau04_200_02','right_tau04_200_02','both')
assert (mode=='comparison')==(label=='both')
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
labels=['left_tau04_200_02','right_tau04_200_02'] if label=='both' else [label]
for item in labels:
    status=json.loads((HERE/item/'status.json').read_text())
    assert status['state']=='completed' and status['exit_code']==0 and status['protected_unchanged']
    if mode=='comparison':
        assert json.loads((HERE/(item+'_verification_03.json')).read_text())['status']=='passed'
request=HERE/f'{label}_{mode}_launch_request_03.json'
assert not request.exists()
rows,active,paused=census()
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
    active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=shutil.disk_usage(HERE).free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
(HERE/f'{label}_{mode}_before_admission_03.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8 and record['free_disk_bytes']>=20*2**30
script='verify_case_03.py' if mode=='verification' else 'compare_components_03.py'
argv=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner',
    'intervention-instruction24-'+label+'-'+mode,'--mem','0.3',
    '--disk-path',str(HERE/labels[-1]/'output'),'--',sys.executable,str(HERE/script)]
if mode=='verification':argv.append(label)
epoch=time.time()
with request.open('x')as stream:
    json.dump(dict(at_jst=record['at_jst'],submitted_epoch=epoch,argv=argv,reservation_gb=.3,
        reservation_basis='既存必要記録点検と成分の小さい原字節のみ。巨大控えの展開・全量比較は行わない'),stream,ensure_ascii=False,indent=2)
with (HERE/f'{label}_{mode}_admission_03.log').open('xb')as log:
    code=subprocess.call(argv,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
timing=dict(submitted_epoch=epoch,ended_epoch=time.time(),exit_code=code,
    independent_admission_wait_seconds=None,independent_cpu_wait_seconds=None)
(HERE/f'{label}_{mode}_admission_completion_03.json').write_text(json.dumps(timing,ensure_ascii=False,indent=2)+'\n')
sys.exit(code)
