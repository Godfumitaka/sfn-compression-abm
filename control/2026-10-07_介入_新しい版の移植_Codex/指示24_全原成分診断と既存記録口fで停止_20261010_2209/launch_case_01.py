"""指示24の各一本を、実測予約と原資源条件の通常受付へ一度投入する。"""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'instruction22'))
from resource_census_02 import census
label=sys.argv[1]
assert label in ('left_tau04_200_01','right_tau04_200_01')
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
spec=json.loads((HERE/'commands_01.json').read_text())[label]
request=HERE/f'{label}_launch_request_01.json'
assert not request.exists() and not Path(spec['destination']).exists(), '同じ受付・模型を重複登録しない'
rows,active,paused=census()
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
    active_pids=sorted(active),paused_pids=sorted(paused),ps=rows,free_disk_bytes=shutil.disk_usage(HERE).free,
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True),
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True))
with (HERE/f'{label}_before_admission_01.json').open('x') as stream:
    json.dump(record,stream,ensure_ascii=False,indent=2)
assert len(active)<8 and record['free_disk_bytes']>=20*2**30
epoch=time.time()
argv=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner',
    'intervention-instruction24-components-'+label,'--mem',str(spec['reservation_gb']),
    '--disk-path',str(Path(spec['destination'])/'output'),'--',sys.executable,str(HERE/'run_case_01.py'),label]
with request.open('x') as stream:
    json.dump(dict(at_jst=record['at_jst'],submitted_epoch=epoch,argv=argv,reservation_gb=spec['reservation_gb'],
        reservation_basis='同じ200試行の実測最大335036416Bと余裕、成分保存は数MiB以下の控えを逐次処理'),
        stream,ensure_ascii=False,indent=2)
with (HERE/f'{label}_admission_01.log').open('xb') as log:
    code=subprocess.call(argv,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
        'INTERVENTION24_SUBMITTED_EPOCH':str(epoch)},stdout=log,stderr=subprocess.STDOUT)
sys.exit(code)
