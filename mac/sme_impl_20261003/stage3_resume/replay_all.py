import os,json,subprocess,time,gzip
from pathlib import Path
root=Path(__file__).resolve().parent.parent
src=root/"source"
out=Path(__file__).resolve().parent
env=dict(os.environ, PYTHONHASHSEED="0")
for k in ("LC_CTYPE","LC_ALL","LANG"):env.pop(k,None)
results=[]
for folder in ("stage3_learning_02","stage3_learning_03"):
 for cf in sorted((root/folder).glob("*.command.json")):
  cmd=json.loads(cf.read_text()); old=Path(cmd[3]); states=list(old.glob("side/*/*.sme.states.jsonl.gz"))
  if len(states)!=1:raise RuntimeError((cf,states))
  dest=out/(folder+"_"+cf.name.removesuffix(".command.json"))
  if dest.exists():raise RuntimeError("出力先が既にある")
  cmd[3]=str(dest);cmd+= ["--sme-replay",str(states[0])]
  (out/(dest.name+".command.json")).write_text(json.dumps(cmd,ensure_ascii=False,indent=2)+"\n")
  t=time.monotonic()
  with (out/(dest.name+".log")).open("w") as log:r=subprocess.run(cmd,cwd=src,env=env,stdout=log,stderr=subprocess.STDOUT)
  manifests=[json.loads(x) for x in (dest/"manifest.jsonl").read_text().splitlines()]
  record={"source":str(old),"output":str(dest),"exit_code":r.returncode,"wall_seconds":time.monotonic()-t,"manifest":manifests}
  results.append(record);(out/"replays.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")
  print(json.dumps({"run":dest.name,"exit":r.returncode,"seconds":record["wall_seconds"],"replay":manifests[0].get("smereplay"),"error":manifests[0].get("error")},ensure_ascii=False),flush=True)
  if r.returncode or any(x.get("error") for x in manifests):raise SystemExit(3)
