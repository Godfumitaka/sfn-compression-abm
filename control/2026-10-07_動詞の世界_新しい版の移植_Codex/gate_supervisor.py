"""一度だけ受付へ出し、全長関門後に読み取り比較を行う。on走行は開始しない。"""
from datetime import datetime
from pathlib import Path
import json,subprocess,time,os
root=Path(__file__).resolve().parent
case=root/'gates/alloff_5000';spec=json.loads((case/'spec.json').read_text())
py='/opt/homebrew/opt/python@3.12/bin/python3.12';jobs=str(Path.home()/'jobs/jobs.py')
def state(value):
    (root/'gate_status.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),'supervisor_pid':os.getpid(),**value},ensure_ascii=False,indent=2)+'\n')
try:
    assert not (case/'result.json').exists(), '既存の走行を二重起動しない'
    cmd=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞新移植 追加旗off5000',
         '--mem',str(spec['memory_reservation_gb']),'--disk-path',spec['output'],'--',py,str(root/'run_case.py'),str(case)]
    state({'state':'running_or_waiting','label':'alloff_5000','command':cmd})
    with (case/'jobs.log').open('x') as log:rc=subprocess.call(cmd,stdout=log,stderr=subprocess.STDOUT)
    assert rc==0,(rc,'受付又は模型が非0終了')
    result=json.loads((case/'result.json').read_text());assert result['exit_code']==0,result
    records=[json.loads(x) for x in (Path(spec['output'])/'manifest.jsonl').read_text().splitlines()]
    assert len(records)==1 and records[0].get('trial_count')==5000 and not records[0].get('error') and not records[0].get('v39_unfit')
    state({'state':'comparing_alloff'})
    cmd=['/usr/bin/python3',jobs,'run','--wait','--owner','Codex 動詞新移植 全バイト比較',
         '--mem','0.2','--disk-path',str(case),'--',py,str(root/'compare_alloff.py')]
    with (case/'comparison.jobs.log').open('x') as log:rc=subprocess.call(cmd,stdout=log,stderr=subprocess.STDOUT)
    result=json.loads((case/'comparison.json').read_text());assert rc==0 and result['passed'],result
    state({'state':'alloff_gate_passed','on_gate':'public_question_entry_pending'})
except Exception as e:
    state({'state':'stopped','reason':repr(e)})
    raise
