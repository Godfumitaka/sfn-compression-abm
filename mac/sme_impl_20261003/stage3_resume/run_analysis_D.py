import json,subprocess,os
from pathlib import Path
r=Path(__file__).resolve().parent;root=r.parent;e=dict(os.environ,PYTHONHASHSEED="0")
for k in ("LC_ALL","LANG","LC_CTYPE"):e.pop(k,None)
source=root/"stage3_learning_02/D";state=next(source.glob("side/*/*.sme.states.jsonl.gz"));cmd=["/opt/homebrew/opt/python@3.12/bin/python3.12","tools/selcands_sme.py",str(root/"stage3_learning_02/D.command.json"),str(r/"analysis2_D"),str(state)]
with (r/"analysis2_D.log").open("w") as f:p=subprocess.run(cmd,cwd=root/"source",env=e,stdout=f,stderr=subprocess.STDOUT)
print((r/"analysis2_D.log").read_text()[-1800:]);raise SystemExit(p.returncode)
