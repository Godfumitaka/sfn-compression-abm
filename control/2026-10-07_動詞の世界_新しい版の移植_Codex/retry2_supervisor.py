"""模型40e87b2を保ち、測定カウンターだけ直した100二本の関門。"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,os
root=Path(__file__).resolve().parent;parent=root.parent
py='/opt/homebrew/opt/python@3.12/bin/python3.12';jobs=str(Path.home()/'jobs/jobs.py')
def state(**value):
 (root/'retry2_status.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),supervisor_pid=os.getpid(),**value),ensure_ascii=False,indent=2)+'\n')
def run(label):
 case=root/label;spec=json.loads((case/'spec.json').read_text())
 assert not (case/'result.json').exists() and not (case/'pid.json').exists() and not (case/'jobs.log').exists(),'完了・停止済みの同じ出力へ重ねない'
 assert datetime.now(timezone.utc)<datetime.fromisoformat(spec['start_deadline_jst'])
 for filename,expected in spec['observer_files'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==expected
 state(state='running_or_waiting',label=label)
 command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 '+label,'--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',py,str(parent/'run_case.py'),str(case)]
 with (case/'jobs.log').open('x') as log:rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
 assert rc==0,(label,rc)
 return case
def compare():
 state(state='comparing',comparison='on100_retry2_comparison.json')
 command=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞 指示6 on100_retry2_comparison','--mem','.2','--disk-path',str(root),'--',py,str(root/'on100_retry2_compare.py')]
 with (root/'on100_retry2_comparison.jobs.log').open('x') as log:rc=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
 assert rc==0 and json.loads((root/'on100_retry2_comparison.json').read_text())['passed']
try:
 assert not (root/'retry2_status.json').exists(),'監督を二重起動しない'
 assert json.loads((root/'on100_without_probe_retry1/result.json').read_text())['exit_code']==3
 assert json.loads((parent/'measurement_counter_retry2_checks/output/checks.json').read_text())['passed']
 for p in [root/'cue_counts/output/counts.json',parent/'gates/alloff_5000/comparison.json',root/'shop_retry1_comparison.json']:assert json.loads(p.read_text())['passed']
 for label in ['on100_without_probe_retry2','on100_with_probe_retry2']:
  case=run(label)
  manifest=[json.loads(x) for x in (case/'output/manifest.jsonl').read_text().splitlines()]
  assert len(manifest)==1 and manifest[0]['completed_trials']==100 and manifest[0]['configured_trial_count']==manifest[0]['horizon']==5000 and not manifest[0]['full_5000_completed'] and not manifest[0].get('error'),manifest
  if 'with_probe' in label:
   probe=manifest[0]['probeworld'];assert probe['probes']==48 and probe['fingerprint_checks']==1
   ac=probe['attention_checks'];assert len(ac)==1 and all(x['passed'] and x['attention_before']==x['attention_after'] and x['questions_before']==x['questions_after'] for x in ac)
 compare()
 state(state='all_small_gates_passed')
except Exception as e:
 state(state='stopped',reason=repr(e))
 raise
