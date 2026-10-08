"""指示15の二つの関門を一度だけ受付へ通す。稼働中の模型と監督を替えない。"""
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
import json,os,sys,subprocess,hashlib,shutil
ROOT=Path(__file__).resolve().parent;NR=ROOT.parent
sys.path.insert(0,str(NR))
from inbox_snapshot import snapshot
PY='/opt/homebrew/opt/python@3.12/bin/python3.12';JOBS=str(Path.home()/'jobs/jobs.py')
def save(name,value):
    (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def state(**value):
    save('status.json',dict(at=datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid(),**value))
def run(label):
    case=ROOT/label;spec=json.loads((case/'spec.json').read_text())
    for name in ['result.json','pid.json','jobs.log','resources.jsonl']:
        assert not (case/name).exists(),'既存の同じ走行へ二重に投入しない'
    assert not Path(spec['output']).exists()
    assert datetime.now(timezone.utc)<datetime.fromisoformat(spec['start_deadline_jst'])
    for name,sha in spec['observer_files'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha
    snapshot(SimpleNamespace(workspace=NR.parent.parent,output=ROOT/(label+'_before_start.json')))
    # 開始の直前だけ機械の原値を保存する。受付・既存資源監督の判定は替えない。
    machine={key:subprocess.check_output(cmd,text=True) for key,cmd in {
        'physical_cpu':['/usr/sbin/sysctl','-n','hw.physicalcpu'],
        'physical_memory_bytes':['/usr/sbin/sysctl','-n','hw.memsize'],
        'vm_stat':['/usr/bin/vm_stat'],
        'swap':['/usr/sbin/sysctl','vm.swapusage'],
        'thermal':['/usr/bin/pmset','-g','therm']}.items()}
    machine.update(at=datetime.now().astimezone().isoformat(),free_disk_bytes=shutil.disk_usage(case).free,
                   swap_window_minutes=10,swap_samples=(Path.home()/'jobs/swap.tsv').read_text().splitlines()[-11:])
    save(label+'_machine_before_start.json',machine)
    state(state='running_or_waiting',label=label)
    cmd=['/usr/bin/python3',JOBS,'run','--wait','--owner','Codex 動詞 指示15 '+label,'--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',PY,str(NR/'run_case.py'),str(case)]
    with (case/'jobs.log').open('x') as f:rc=subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
    assert rc==0,(label,rc)
    manifest=[json.loads(x) for x in (case/'output/manifest.jsonl').read_text().splitlines()]
    assert len(manifest)==1 and not manifest[0].get('error')
    item=manifest[0];assert item['completed_trials']==spec['completed_trials'] and item['configured_trial_count']==item['horizon']==5000 and item['full_5000_completed'] is False
    return case
try:
    assert not (ROOT/'status.json').exists(),'監督を二重起動しない'
    for f in [NR/'gates/alloff_5000/comparison.json',NR/'instruction6_checks/shop_retry1_comparison.json',NR/'instruction6_checks/cue_counts/output/counts.json']:
        assert json.loads(f.read_text())['passed']
    assert json.loads((NR/'instruction6_checks/retry2_status.json').read_text())['state']=='stopped'
    assert json.loads((NR/'instruction14_readonly_status.json').read_text())['state']=='completed'
    assert json.loads((NR/'measurements/allin_s01_300/cancelled_by_instruction14.json').read_text())['started'] is False
    assert json.loads((ROOT/'mac_on100_approved_comparison.json').read_text())['passed']
    run('on100_logfix')
    state(state='comparing_logfix100')
    cmd=['/usr/bin/python3',JOBS,'run','--wait','--owner','Codex 動詞 指示15 記録修正100比較','--mem','.3','--disk-path',str(ROOT),'--',PY,str(ROOT/'compare_logfix100.py')]
    assert not (ROOT/'on100_logfix_comparison.json').exists()
    with (ROOT/'on100_logfix_comparison.jobs.log').open('x') as f:rc=subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
    assert rc==0 and json.loads((ROOT/'on100_logfix_comparison.json').read_text())['passed']
    case=run('production_lambda20')
    count=json.loads((case/'output/measurement/log_fallback_counts.json').read_text())
    assert count['completed_trials']==20 and count['fallback_calls']>=0 and count['model_stats_modified'] is False
    state(state='logfix_gates_passed',fallback_calls=count['fallback_calls'],completed_trials=20,production_started=False)
except Exception as exc:
    state(state='stopped',reason=repr(exc),production_started=False)
    raise
