import json,subprocess,os,gzip,hashlib
from pathlib import Path
r=Path(__file__).resolve().parent;root=r.parent;e=dict(os.environ,PYTHONHASHSEED="0")
for k in ("LC_ALL","LANG","LC_CTYPE"):e.pop(k,None)
checks=[]
for run,folder,seed in (("A","stage3_learning_03",1),("C","stage3_learning_02",2),("D","stage3_learning_02",2)):
 source=root/folder/run;states=next(source.glob("side/*/*.sme.states.jsonl.gz"));out=r/("analysis2_"+run)
 cmd=["/opt/homebrew/opt/python@3.12/bin/python3.12","tools/selcands_sme.py",str(root/folder/(run+".command.json")),str(out),str(states)]
 with (r/("analysis2_"+run+".log")).open("w") as f:p=subprocess.run(cmd,cwd=root/"source",env=e,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise SystemExit(p.returncode)
 def body(folder):
  with gzip.open(next(folder.glob("ledgers/cells/*/*.gz")),"rb") as f:f.readline();return hashlib.sha256(f.read()).hexdigest()
 files=[{"file":p.name,"equal":(out/"side"/p.parent.name/p.name).read_bytes()==p.read_bytes()} for p in source.glob("side/*/*") if "diagnostics" not in p.name]
 with gzip.open(next(out.glob("side/*/*.sme.candidates.jsonl.gz")),"rt") as f:rows=[json.loads(x) for x in f]
 check={"run":run,"body_equal":body(source)==body(out),"common_sides":files,"trials":len(rows),"candidates":sum(len(x["candidates"]) for x in rows)}
 checks.append(check);(r/"analyses2_check.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n");print(json.dumps(check),flush=True)
 if not check["body_equal"] or not all(x["equal"] for x in files):raise SystemExit(3)
