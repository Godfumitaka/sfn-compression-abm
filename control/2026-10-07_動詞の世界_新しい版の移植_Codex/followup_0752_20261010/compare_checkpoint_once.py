"""指示27の確定境界の読み取り。模型と既存比較器は変更しない。"""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, time
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
NR=HERE.parent
ROOT=NR.parent
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
LEFT=NR/'instruction23_production/19_seed001_score_e_off'
RIGHT=ROOT.parent/'codex_cstar_pending_2026-10-06/queue19p_20261010/19_seed001_flags_on'
COMP=NR/'instruction27/checkpoint_digest.py'
DEST=HERE/'checkpoint_0500.json'
STATE=HERE/'checkpoint_0500_status.json'
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def status(s,**x):write(STATE,dict(at=datetime.now().astimezone().isoformat(),state=s,model_starts=0,**x))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def admitted():
    assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    assert not DEST.exists(),'既存比較を重ねない'
    assert sha(COMP)=='f9dfd958bb14e6964df8aa503757939cd21009c2f3362f752de8d759f0642ced'
    fixed=json.loads((NR/'instruction27/fixed_tools.json').read_text())
    for f in ['tools/instruction11_io.py','run_registered.py','birth_census.py']:
        assert sha(NR/'instruction27'/f)==fixed[f]
    proofs=[]
    for case in [LEFT,RIGHT]:
        spec=json.loads((case/'spec.json').read_text())
        proof=Path(spec['output'])/'comparison_checkpoints/completed_0500/confirmed.json'
        value=json.loads(proof.read_text())
        assert value['confirmed'] and value['completed_trials']==500 and value['last_trial']==499
        proofs.append(dict(path=str(proof),sha256=sha(proof)))
    sys.path.insert(0,str(NR/'instruction27'))
    from run_registered import start_counts
    raw=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,stat=,args='],text=True)
    counts=start_counts(raw)
    limit=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.physicalcpu'],text=True))-2
    therm=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True)
    thermal_ok='No thermal warning level has been recorded' in therm and not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+',therm)
    free=shutil.disk_usage(HERE).free
    snapshot=dict(at=datetime.now().astimezone().isoformat(),processes=raw,counts=counts,cpu_budget=limit,
        comparison_cpu_slots=1,comparison_model_slots=0,reserved_memory_gib=0.3,thermal=therm,free_disk_bytes=free,
        swap_original_rows=(Path.home()/'jobs/swap.tsv').read_text().splitlines()[-12:],
        admission_registry_original=(Path.home()/'jobs/registry.tsv').read_text(),original_confirmed=proofs,
        counting_rule=counts['counting_rule'],unchanged_shared_classifier=True)
    write(HERE/'checkpoint_0500_before_start.json',snapshot)
    if not(counts['outside_heavy']+1<=limit and counts['unknown_active_spawn']==0 and counts['model_process_count']<=8 and thermal_ok and free>=20*2**30):
        status('resource_conditions_not_ready',admitted_pid=os.getpid(),comparison_started=False);return 2
    status('comparing_confirmed_500',admitted_pid=os.getpid(),comparison_started=True)
    command=[PY,'-B',str(COMP),str(LEFT),str(RIGHT),'500',str(DEST)]
    start=time.time()
    with (HERE/'checkpoint_0500.run.log').open('x') as log:
        done=subprocess.run(['/usr/bin/time','-l',*command],stdout=log,stderr=subprocess.STDOUT)
    write(HERE/'checkpoint_0500_result.json',dict(at=datetime.now().astimezone().isoformat(),exit_code=done.returncode,wall_seconds=time.time()-start,command=command,model_starts=0))
    result=json.loads(DEST.read_text()) if DEST.exists() else None
    status('completed' if done.returncode==0 else 'stopped',exit_code=done.returncode,
        comparison_present=DEST.exists(),passed=result['passed'] if result else None,
        full_length_match=False,flagged_results_usable=False)
    return done.returncode
if '--admitted' in sys.argv:
    raise SystemExit(admitted())
with (HERE/'checkpoint_0500.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not STATE.exists() and not DEST.exists() and not (HERE/'checkpoint_0500_launcher.json').exists()
    status('submitted_once_to_jobs',launcher_pid=os.getpid(),comparison_started=False)
    command=[PY,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','動詞・指示27・確定500境界の読取比較','--mem','0.3','--disk-path',str(HERE),'--',PY,'-B',str(Path(__file__).resolve()),'--admitted']
    write(HERE/'checkpoint_0500_launcher.json',dict(at=datetime.now().astimezone().isoformat(),pid=os.getpid(),command=command,model_starts=0))
    with (HERE/'checkpoint_0500.jobs.log').open('x') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        write(HERE/'checkpoint_0500_jobs_pid.json',dict(pid=child.pid))
        rc=child.wait()
    if not (HERE/'checkpoint_0500_result.json').exists():
        write(HERE/'checkpoint_0500_admission_result.json',dict(at=datetime.now().astimezone().isoformat(),exit_code=rc,comparison_started=False))
    raise SystemExit(rc)
