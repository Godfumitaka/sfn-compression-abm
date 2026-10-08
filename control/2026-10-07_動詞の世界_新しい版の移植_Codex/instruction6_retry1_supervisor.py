"""記録の型エラーを除いた版で、お店と動詞の関門を一つずつ行う。"""
from pathlib import Path
from datetime import datetime
import json,subprocess,os
root=Path(__file__).resolve().parent;parent=root.parent
py='/opt/homebrew/opt/python@3.12/bin/python3.12';jobs=str(Path.home()/'jobs/jobs.py')
def state(**value):
 (root/'retry1_status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid(),**value),ensure_ascii=False,indent=2)+'\n')
def run(label):
 case=root/label;spec=json.loads((case/'spec.json').read_text())
 assert not (case/'result.json').exists(),'完了又は停止済みの同じ走行を重ねない'
 state(state='running_or_waiting',label=label)
 command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 '+label,'--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',py,str(parent/'run_case.py'),str(case)]
 with (case/'jobs.log').open('x') as log:rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
 assert rc==0,(label,rc)
 return case
def compare(script,output):
 state(state='comparing',comparison=output)
 command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 '+output,'--mem','.2','--disk-path',str(root),'--',py,str(root/script)]
 with (root/(output+'.jobs.log')).open('x') as log:rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
 assert rc==0 and json.loads((root/output).read_text())['passed'],output
try:
 assert json.loads((root/'cue_counts/output/counts.json').read_text())['passed']
 assert json.loads((parent/'gates/alloff_5000/comparison.json').read_text())['passed']
 run('shop_candidate_retry1')
 compare('shop_retry1_compare.py','shop_retry1_comparison.json')
 for label in ['on100_without_probe_retry1','on100_with_probe_retry1']:
  case=run(label)
  manifest=[json.loads(x) for x in (case/'output/manifest.jsonl').read_text().splitlines()]
  assert len(manifest)==1 and manifest[0]['completed_trials']==100 and manifest[0]['configured_trial_count']==5000 and not manifest[0]['full_5000_completed'] and not manifest[0].get('error'),manifest
 compare('on100_retry1_compare.py','on100_retry1_comparison.json')
 state(state='all_small_gates_passed')
except Exception as e:
 state(state='stopped',reason=repr(e))
 raise
