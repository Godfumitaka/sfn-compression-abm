"""完走と監督の終了を待ち、保存原本のsha256と計測表だけを作る。"""
from pathlib import Path
import json
import subprocess
import time

root=Path(__file__).resolve().parent
while True:
    status=json.loads((root/'status.json').read_text())
    if status['state']=='stopped':
        raise SystemExit('関門又は測定が停止したので完走の表は作らない')
    end=root/'pilot_A_global_s01/guardian_complete.json'
    if status['state']=='pilot_complete' and end.exists():
        guard=json.loads(end.read_text())
        assert guard['completed'] and guard['exit_code']==0
        break
    time.sleep(15)
folder=root/'final_measurement';folder.mkdir(exist_ok=True)
output=root.parent/'report-results/control/2026-10-06_動詞の世界_SME版_Codex'
spec={'cwd':str(root),'output':str(output),'sources':{str(root/'source'):'4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'},'cpu_start_slots':1,
      'command':['/opt/homebrew/opt/python@3.12/bin/python3.12',str(root/'finish_report.py')]}
(folder/'spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
cmd=['/usr/bin/python3',str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','Codex 動詞SME 原本sha256と完走の測定表',
     '--mem','0.3','--disk-path',str(output),'--','/opt/homebrew/opt/python@3.12/bin/python3.12',str(root/'run_case.py'),str(folder)]
with (folder/'jobs.log').open('x') as out:
    rc=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT).returncode
(folder/'reader_status.json').write_text(json.dumps({'exit_code':rc})+'\n')
raise SystemExit(rc)
