"""指示6の300一本だけを、先行関門と期限を再確認して受付する。"""
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess,os,re
folder=Path(__file__).resolve().parent;root=folder.parents[1];checks=root/'instruction6_checks'
py='/opt/homebrew/opt/python@3.12/bin/python3.12';jobs=str(Path.home()/'jobs/jobs.py')
def state(**v):
 (folder/'status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid(),**v),ensure_ascii=False,indent=2)+'\n')
try:
 assert not (folder/'result.json').exists() and not (folder/'pid.json').exists(),'同じ300を二重起動しない'
 spec=json.loads((folder/'spec.json').read_text())
 assert datetime.now(timezone.utc)<datetime.fromisoformat(spec['start_deadline_jst']),'期限以降は新しい300を始めない'
 assert json.loads((checks/'retry1_status.json').read_text())['state']=='all_small_gates_passed'
 for p in [root/'gates/alloff_5000/comparison.json',checks/'cue_counts/output/counts.json',checks/'shop_retry1_comparison.json',checks/'on100_retry1_comparison.json']:
  assert json.loads(p.read_text())['passed'],str(p)
 m=[json.loads(x) for x in (checks/'on100_with_probe_retry1/output/manifest.jsonl').read_text().splitlines()]
 assert len(m)==1 and m[0]['completed_trials']==100 and not m[0]['full_5000_completed']
 probe=m[0]['probeworld'];assert probe['probes']==48 and probe['fingerprint_checks']==1
 ac=probe['attention_checks'];assert len(ac)==1 and all(x['passed'] and x['attention_before']==x['attention_after'] and x['questions_before']==x['questions_after'] for x in ac)
 inbox=(root.parent/'report-results/control/受け箱/動詞の世界の係.md').read_text()
 blocks=re.split(r'^## 指示 ',inbox,flags=re.M)[1:]
 assert all(re.search(r'\n受領（\d{4}-',b) for b in blocks),'未受領の新しい指示を先に確認する'
 source=Path(next(iter(spec['sources'])))
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==next(iter(spec['sources'].values()))
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
 subprocess.check_call([py,str(root/'inbox_snapshot.py'),'--workspace',str(root.parent.parent),'--output',str(folder/'before_start.json')])
 snap=json.loads((folder/'before_start.json').read_text());assert snap['model_process_count']<8 and not snap['other_active_spawn_workers']
 (folder/'supervisor_pid.json').write_text(json.dumps(dict(pid=os.getpid(),at=datetime.now().astimezone().isoformat()))+'\n')
 state(state='running_or_waiting',source_commit=next(iter(spec['sources'].values())),completed_trials=0)
 command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 全部入り先頭300一本測定','--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',py,str(root/'run_case.py'),str(folder)]
 with (folder/'jobs.log').open('x') as log:rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
 assert rc==0,rc
 marker=json.loads((folder/'output/measurement/partial_done.json').read_text());assert marker['completed_trials']==300 and marker['configured_trial_count']==marker['horizon']==5000 and not marker['full_5000_completed']
 state(state='measurement300_completed',completed_trials=300,full_5000_completed=False)
except Exception as e:
 state(state='stopped_before_start_or_after_failure',reason=repr(e))
 raise
