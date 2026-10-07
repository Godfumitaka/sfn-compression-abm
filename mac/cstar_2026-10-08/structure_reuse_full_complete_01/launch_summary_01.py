"""全長の完了記録の読み取り受付を一回だけ作る。"""
from pathlib import Path
from datetime import datetime
import fcntl, json, os, subprocess

ROOT=Path(__file__).resolve().parent
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
with (ROOT/'summary_launch_01.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    assert not (ROOT/'full_summary_01.json').exists() and not (ROOT/'summary_claim_01.json').exists()
    assert json.loads((ROOT/'full1740_01/complete.json').read_text())['passed']
    command=[PY,str(Path.home()/'jobs/jobs.py'),'run','--owner','SME_structure_full_summary_01',
             '--wait','--mem','1','--disk-path',str(ROOT),'--',PY,str(ROOT/'summarize_full_01.py')]
    with (ROOT/'summary_claim_01.log').open('x') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=ROOT)
    value=dict(at=datetime.now().astimezone().isoformat(),pid=proc.pid,command=command,memory_claim_gb=1,model_started=False)
    (ROOT/'summary_claim_01.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value,ensure_ascii=False),flush=True)
