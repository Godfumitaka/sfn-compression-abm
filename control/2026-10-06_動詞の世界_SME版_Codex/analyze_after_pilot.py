"""完走した一本の既存記録だけを読み、移した分類道具の再現を確かめる。"""
from pathlib import Path
import json
import subprocess
import time

root=Path(__file__).resolve().parent
while True:
    p=root/'status.json'
    status=json.loads(p.read_text()) if p.exists() else {}
    if status.get('state')=='stopped':
        raise SystemExit('関門又は測定が止まったので読取を始めない')
    if status.get('state')=='pilot_complete':
        break
    time.sleep(15)
folder=root/'pilot_analysis';folder.mkdir(exist_ok=True)
output=folder/'output'
command=['/opt/homebrew/opt/python@3.12/bin/python3.12','tools/verb/analyze.py',
         str(root/'pilot_A_global_s01/output'),'1',str(output)]
source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root/'source',text=True).strip()
spec={'cwd':str(root/'source'),'output':str(output),'sources':{str(root/'source'):source_commit},'command':command,'cpu_start_slots':1}
(folder/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
cmd=['/usr/bin/python3',str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','Codex 動詞SME 分類道具の読取検査',
     '--mem','1.3','--disk-path',str(output),'--','/opt/homebrew/opt/python@3.12/bin/python3.12',str(root/'run_case.py'),str(folder)]
with (folder/'jobs.log').open('x') as out:
    rc=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT).returncode
(folder/'reader_status.json').write_text(json.dumps({'exit_code':rc})+'\n')
raise SystemExit(rc)
