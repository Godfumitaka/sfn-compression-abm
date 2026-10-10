"""指示33。模型を起動しない構造検査を、一つの受付と新しいruntimeで実施する。"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from birth_census import count_models

SERIAL = [
    'test_stage2_speed_basic.py', 'test_cstar_cache_prune.py', 'test_attncstar.py',
    'test_attnstage2.py', 'test_attnstage2_connection.py', 'test_attnstage2_birth.py',
    'test_attnstage2_birth_hu.py', 'test_attnstage2_distribution.py',
    'test_attnstage2_runtime.py', 'test_cstar_stage2_reuse.py', 'test_attnstage2_readout.py',
    'test_attnstage2_questions.py', 'test_attnstage2_initial.py', 'test_attnstage2_scope.py',
    'test_attnstage2_calibration.py', 'test_verb_snapshot_append_only.py', 'test_smeshared_json_log.py',
]
BIRTH = ['test_birth_workers_instruction22.py']


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def admitted(a):
    source, runtime = Path(a.source).resolve(), Path(a.runtime).resolve()
    required = 5 if a.mode == 'birth' else 1
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    versions = json.loads((Path(__file__).parent/'versions.json').read_text())
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == versions['source_commit']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=source, text=True).strip() == versions['source_tree']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
    assert sys.platform == 'darwin', '別機械への変更はClaudeの正式指定とその機械の受付が必要'
    raw = subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    rows = {}
    for line in raw.splitlines():
        v = line.split(None, 5)
        if len(v) == 6:
            p, parent, group, rss, state, command = v
            rows[int(p)] = dict(pid=int(p),ppid=int(parent),pgid=int(group),rss_bytes=int(rss)*1024,state=state,command=command)
    models, unknown, paused, paused_models = count_models(rows)
    heavy = lambda r: (not r['state'].startswith(('T','Z')) and any(x in r['command'].split(None,1)[0].lower() for x in ('python','pypy'))
        and 'resource_tracker' not in r['command'] and 'jobs.py' not in r['command']
        and (r['rss_bytes'] >= 100*1024**2 or 'spawn_main' in r['command']))
    outside = sum(heavy(r) for pid,r in rows.items() if pid != os.getpid())
    budget = int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.physicalcpu'],text=True))-2
    therm = subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True)
    ok_heat = 'No thermal warning level has been recorded' in therm and not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+',therm)
    machine = dict(at=datetime.now().astimezone().isoformat(),processes=raw,model_count=len(models),models=models,unknown=unknown,
        outside_heavy=outside,cpu_limit=budget,required_cpu_slots=required,model_start_slots=0,reserved_memory_gib=0.5,
        thermal=therm,free_disk_bytes=shutil.disk_usage(runtime).free,
        swap_original_rows=(Path.home()/'jobs/swap.tsv').read_text().splitlines()[-12:],
        admission_registry_original=(Path.home()/'jobs/registry.tsv').read_text(),
        counting_rule='実spawn workerと出生fork子。親/監督/time/tracker/T/Zは稼働模型に足さない。共有分類器不変。',
        model_starts=0)
    write(runtime/'before_start.json',machine)
    if not (len(models)<=8 and not unknown and outside+required<=budget and ok_heat and machine['free_disk_bytes']>=20*2**30):
        write(runtime/'status.json',dict(state='resource_conditions_not_ready',tests_started=False,model_starts=0))
        return 2
    files = SERIAL if a.mode == 'serial' else BIRTH
    command = [a.test_python,'-B','-m','pytest','-q','-p','no:cacheprovider',*[str(source/'tests'/f) for f in files]]
    write(runtime/'status.json',dict(state='testing',tests_started=True,mode=a.mode,model_starts=0))
    start=time.time()
    with (runtime/'tests.log').open('x') as log:
        done=subprocess.run(['/usr/bin/time','-l',*command],cwd=source,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0'))
    write(runtime/'result.json',dict(exit_code=done.returncode,wall_seconds=time.time()-start,mode=a.mode,
        command=command,files=files,source_commit=versions['source_commit'],model_starts=0))
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=source)
    write(runtime/'status.json',dict(state='passed' if done.returncode==0 else 'stopped',tests_started=True,
        passed=done.returncode==0,model_starts=0))
    return done.returncode


def dispatch(a):
    runtime=Path(a.runtime).resolve()
    assert not runtime.exists(), '同じ検査/受付へ再投入しない'
    receipt=json.loads(Path(a.receipt).read_text())
    assert receipt['normal_push_succeeded'] and 33 in receipt['instructions'] and len(receipt['commit'])==40
    runtime.mkdir()
    write(runtime/'status.json',dict(state='submitted_once_to_jobs',tests_started=False,model_starts=0))
    cmd=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner',f'動詞・指示33・{a.mode}構造検査',
         '--mem','0.5','--disk-path',str(runtime),'--',sys.executable,'-B',str(Path(__file__).resolve()),
         a.source,a.runtime,'--test-python',a.test_python,'--mode',a.mode,'--receipt',a.receipt,'--admitted']
    write(runtime/'launcher.json',dict(pid=os.getpid(),command=cmd,receipt_commit=receipt['commit'],model_starts=0))
    with (runtime/'jobs.log').open('x') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        write(runtime/'jobs_pid.json',dict(pid=child.pid))
        rc=child.wait()
    if not (runtime/'result.json').exists():
        write(runtime/'admission_result.json',dict(exit_code=rc,tests_started=False,model_starts=0))
    return rc


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('runtime');p.add_argument('--test-python',required=True)
    p.add_argument('--receipt',required=True);p.add_argument('--mode',choices=('serial','birth'),required=True)
    p.add_argument('--admitted',action='store_true');a=p.parse_args()
    if a.admitted:
        raise SystemExit(admitted(a))
    lock=Path(a.runtime).with_suffix('.dispatch.lock')
    with lock.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        raise SystemExit(dispatch(a))
