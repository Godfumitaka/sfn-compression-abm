import os,json,subprocess,time,shutil
from pathlib import Path
out=Path(__file__).resolve().parent
env=dict(os.environ,PYTHONHASHSEED="0")
for k in ("LC_CTYPE","LC_ALL","LANG"):env.pop(k,None)
t=time.monotonic()
with (out/"run.log").open("w") as log:
 p=subprocess.Popen(json.loads((out/"command.json").read_text()),cwd=out.parent/"source",env=env,stdout=log,stderr=subprocess.STDOUT)
 while p.poll() is None:
  free=shutil.disk_usage(out).free
  if free<18*1024**3:
   (out/"resource_stop.json").write_text(json.dumps({"free_bytes":free,"reason":"空きが15GiBへ近づいた"})+"\n");p.terminate();break
  time.sleep(10)
 code=p.wait()
print(json.dumps({"exit":code,"wall_seconds":time.monotonic()-t,"output":str(out)},ensure_ascii=False),flush=True)
print((out/"run.log").read_text()[-4000:],flush=True)
raise SystemExit(code)
