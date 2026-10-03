import json,subprocess,os
from pathlib import Path
r=Path(__file__).resolve().parent
e=dict(os.environ,PYTHONHASHSEED="0")
for k in ("LC_ALL","LANG","LC_CTYPE"):e.pop(k,None)
with (r/"A_seed2.log").open("w") as f:
 p=subprocess.run(json.loads((r/"A_seed2.command.json").read_text()),cwd=r.parent/"source",env=e,stdout=f,stderr=subprocess.STDOUT)
print((r/"A_seed2.log").read_text());raise SystemExit(p.returncode)
