import os,json,subprocess,gzip,hashlib
from pathlib import Path
r=Path(__file__).resolve().parent;env=dict(os.environ,PYTHONHASHSEED="0")
for k in ("LC_ALL","LANG","LC_CTYPE"):env.pop(k,None)
checks=[]
for job in json.loads((r/"commands.json").read_text()):
 with (r/(job["name"]+".log")).open("w") as f:p=subprocess.run(job["cmd"],cwd=r.parent/"source",env=env,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise SystemExit(p.returncode)
 actual=Path(job["cmd"][3]);ref=Path(job["reference"])
 def body(root):
  with gzip.open(next(root.glob("ledgers/cells/*/*.gz")),"rb") as f:f.readline();return hashlib.sha256(f.read()).hexdigest()
 sides=[{"file":p.name,"equal":(actual/"side"/p.parent.name/p.name).read_bytes()==p.read_bytes()} for p in ref.glob("side/*/*")]
 check={"name":job["name"],"body_sha_reference":body(ref),"body_sha_current":body(actual),"body_equal":body(actual)==body(ref),"sides":sides};checks.append(check);print(json.dumps(check),flush=True)
 (r/"checks.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n")
 if not check["body_equal"] or not all(x["equal"] for x in sides):raise SystemExit(3)
