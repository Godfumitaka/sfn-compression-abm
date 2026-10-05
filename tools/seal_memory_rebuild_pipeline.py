"""独立した腕を3本まで受付け、各腕は不一致で次の種を止める。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,os,subprocess,sys,time,threading
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/tools'))
import seal_memory_rebuild as rebuild
JOB=ROOT/'memory_rebuild_2026-10-05';PY='/opt/homebrew/bin/python3.12'
state=json.loads((JOB/'status.json').read_text())
state.update(workers=3,current_arm=None,current_seed=None)
lock=threading.RLock()
pending=json.loads((JOB/'pending_jobs.json').read_text()) if (JOB/'pending_jobs.json').exists() else {}
def save(**values):
 with lock:
  state.update(values);state['time']=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat()
  p=JOB/'status.tmp';p.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');p.replace(JOB/'status.json')
def one(arm,seed):
 dest=JOB/Path(arm).name;proof=dest/f'seed{seed:03d}.comparison.json'
 waiting=pending.get(arm)
 if waiting and waiting['seed']==seed:
  while not proof.exists():
   try:os.kill(waiting['pid'],0)
   except ProcessLookupError:raise RuntimeError(f'{arm} 種{seed}の引き継いだ受付が照合記録なしで終了した')
   time.sleep(5)
 if proof.exists():return json.loads(proof.read_text())
 cmd=[PY,'/Users/tatsu-admin/jobs/jobs.py','run','--wait','--owner',f'Codex-介入材料-{Path(arm).name}-s{seed:02d}',
      '--mem','0.4','--disk-path',str(dest),'--','/usr/bin/time','-l',PY,'tools/seal_memory_rebuild.py',arm,str(dest),'--seed',str(seed)]
 with (JOB/f'{Path(arm).name}_seed{seed:03d}.log').open('a') as log:
  result=subprocess.run(cmd,cwd=ROOT/'source',stdout=log,stderr=subprocess.STDOUT)
 if result.returncode not in (0,3) or not proof.exists():raise RuntimeError(f'{arm} 種{seed}の実行エラー（終了符号{result.returncode}）')
 return json.loads(proof.read_text())
def arm_run(arm):
 with lock:
  if state['arms'].get(arm,{}).get('phase') in ('stopped_at_mismatch','complete'):return
  state['arms'][arm]={'matched_seeds':[],'phase':'verifying'};save()
 try:
  for seed in range(1,21):
   with lock:state['arms'][arm]['current_seed']=seed;save()
   comparison=one(arm,seed)
   with lock:
    if not (comparison['body_hash_match'] and comparison['table_match']):
     state['arms'][arm].update(phase='stopped_at_mismatch',seed=seed,comparison=comparison);save();return
    state['arms'][arm]['matched_seeds'].append(seed);save()
  with lock:state['arms'][arm]['phase']='complete';save()
 except Exception as exc:
  with lock:state['arms'][arm].update(phase='failed',error=repr(exc));save()
  raise
if __name__=='__main__':
 save(controller_pid=os.getpid(),phase='rebuilding')
 errors=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(arm_run,arm):arm for arm in rebuild.ARMS}
  for future in as_completed(futures):
   try:future.result()
   except Exception as exc:errors.append(futures[future]+': '+repr(exc))
 save(phase='failed' if errors else 'complete_checks',error='; '.join(errors))
