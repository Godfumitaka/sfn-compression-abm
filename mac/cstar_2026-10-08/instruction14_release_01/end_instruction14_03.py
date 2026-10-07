"""指示14で指定した自分の古い再生解析だけを終了し受付を解放する。"""
from pathlib import Path
from datetime import datetime
import json,os,signal,subprocess,time
R=Path(__file__).resolve().parent;DONE=R/'instruction14_ended_01.json'
assert not DONE.exists(),'済んだ終了を繰り返さない'
before=json.loads((R/'instruction14_before_01.json').read_text())
assert before['instruction']==14 and (R/'instruction14_received_01.json').exists()
def ps():
 rows={}
 for line in subprocess.check_output(['ps','-axo','pid=,ppid=,stat=,rss=,lstart=,command='],text=True).splitlines():
  s=line.strip().split(None,9)
  if len(s)==10:rows[int(s[0])]=dict(pid=int(s[0]),ppid=int(s[1]),stat=s[2],rss_kib=int(s[3]),start=' '.join(s[4:9]),command=s[9])
 return rows
initial=ps();targets={}
for r in before['records']:
 assert r['seed'] in (17,18,19) and r['claim_pid'] in (20806,20915,27521)
 for row in r['process_tree']:
  live=initial.get(row['pid'])
  if live is None or 'Z' in live['stat']:continue
  assert (live['start'],live['command'],live['ppid'])==(row['start'],row['command'],row['ppid']),'識別が変わった。停止しない'
  targets[row['pid']]=row
 if r['replay_pid'] in initial and 'Z' not in initial[r['replay_pid']]['stat']:assert 'T' in initial[r['replay_pid']]['stat'],'再生の停止状態が変わった'
plan=dict(at=datetime.now().astimezone().isoformat(),instruction=14,signal='SIGKILL',reason='指示14の再開しない停止中の自分の解析。SIGCONTで解析を進めず終了する。',targets=list(targets.values()))
(R/'instruction14_termination_plan_03.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
sent=[]
for record in before['records']:
 tree={row['pid']:row for row in record['process_tree']}
 def depth(pid):
  d=0
  while tree[pid]['ppid'] in tree:d+=1;pid=tree[pid]['ppid']
  return d
 for pid in sorted(tree,key=depth):
  current=ps().get(pid)
  if current is None or 'Z' in current['stat'] or current['command']=='<defunct>':continue
  saved=tree[pid];assert (current['start'],current['command'])==(saved['start'],saved['command']),'PIDの識別が変わった。操作を中止'
  try:
   os.kill(pid,signal.SIGKILL);sent.append(pid)
   with (R/'instruction14_signals_03.jsonl').open('a') as f:f.write(json.dumps(dict(at=datetime.now().astimezone().isoformat(),pid=pid,identity=current),ensure_ascii=False)+'\n')
  except ProcessLookupError:pass
for i in range(10):
 remaining={p:v for p,v in ps().items() if p in targets and 'Z' not in v['stat']}
 if not remaining:break
 time.sleep(.5)
assert not remaining,remaining
releases=[]
for claim in (20806,20915,27521):
 p=subprocess.run(['/opt/homebrew/opt/python@3.12/bin/python3.12','/Users/tatsu-admin/jobs/jobs.py','release','--pid',str(claim)],text=True,capture_output=True)
 releases.append(dict(pid=claim,exit=p.returncode,out=p.stdout,err=p.stderr));assert p.returncode==0,p.stderr
registry=Path('/Users/tatsu-admin/jobs/registry.tsv').read_text();registered={int(l.split('\t')[0]) for l in registry.splitlines()[1:] if l.strip()}
assert not registered & {20806,20915,27521}
after=ps();assert not {p for p in targets if p in after and 'Z' not in after[p]['stat']}
result=dict(at=datetime.now().astimezone().isoformat(),instruction=14,done=True,signal_pids=sent,release=releases,registry_after=registry,released_reserved_gb=6.0,production_stopped=False,files_deleted=False,seeds_21_40_touched=False,management_error_count=2,management_error='二回の終了台本は、子を終了した後の親の自然終了中に命令欄が変わり中止。種17と18の木は終了済みと確認した。残る種19の開始時刻と命令を再照合し、監督から順に終了した。模型の関門ではない。',remaining_live_target_pids=[])
DONE.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
