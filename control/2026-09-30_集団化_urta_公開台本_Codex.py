"""公開の時間切れを避ける小分けの転送。元の記録・大きい保存コミット・索引は保全する。"""
from pathlib import Path
import json,os,subprocess,time
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]/'codex_v310ans_2026-09-30/results'
ARCHIVE='ee202d06da5d4155258813c3a5deb6c6b0e9cb3c'
BRANCH='codex/collective-urta-results-batches-2026-09-30'
INDEX=ROOT/'publish_batches.index'
assert not INDEX.exists()
def git(args,env=None):
 p=subprocess.run(['git',*args],cwd=REPO,env=env,capture_output=True)
 if p.returncode:raise RuntimeError((p.stdout+p.stderr).decode(errors='replace'))
 return p.stdout
parent=git(['rev-parse',ARCHIVE+'^']).decode().strip()
names=set(x.decode() for x in git(['diff-tree','--no-commit-id','--name-only','-r','-z',parent,ARCHIVE]).split(b'\0') if x)
rows=[]
for raw in git(['ls-tree','-r','-z',ARCHIVE]).split(b'\0'):
 if not raw:continue
 left,path=raw.split(b'\t',1);path=path.decode()
 if path in names:
  mode,kind,sha=left.decode().split();assert kind=='blob'
  rows.append(dict(path=path,mode=mode,sha=sha,bytes=(REPO/path).stat().st_size))
assert len(rows)==308,len(rows)
control=[r for r in rows if r['path'].startswith('control/')]
others=[r for r in rows if r not in control]
batches=[control];part=[];size=0
for r in others:
 if size+r['bytes']>95_000_000 and part:batches.append(part);part=[];size=0
 part.append(r);size+=r['bytes']
if part:batches.append(part)
env={**os.environ,'GIT_INDEX_FILE':str(INDEX)}
git(['read-tree',parent],env)
records=[];prev=parent
for i,batch in enumerate(batches):
 for r in batch:git(['update-index','--add','--cacheinfo',r['mode'],r['sha'],r['path']],env)
 tree=git(['write-tree'],env).decode().strip()
 commit=git(['commit-tree',tree,'-p',prev,'-m',f'集団化urtaの結果を小分けで保全 {i+1}/{len(batches)}'],env).decode().strip()
 git(['update-ref','refs/heads/'+BRANCH,commit])
 start=time.monotonic();result=None
 for attempt in range(3):
  result=subprocess.run(['git','push','origin',f'refs/heads/{BRANCH}:refs/heads/{BRANCH}'],cwd=REPO,text=True,capture_output=True)
  if result.returncode==0:break
  print(json.dumps({'batch':i+1,'attempt':attempt+1,'error':result.stderr[-600:]},ensure_ascii=False),flush=True)
 if result.returncode:raise RuntimeError(result.stderr)
 record=dict(batch=i+1,batches=len(batches),files=len(batch),bytes=sum(r['bytes'] for r in batch),commit=commit,seconds=round(time.monotonic()-start,2))
 records.append(record);(ROOT/'publish_batches_progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(record,ensure_ascii=False),flush=True)
 prev=commit
assert git(['rev-parse',prev+'^{tree}'])==git(['rev-parse',ARCHIVE+'^{tree}'])
(ROOT/'publish_batches_final.json').write_text(json.dumps(dict(branch=BRANCH,tip=prev,archive=ARCHIVE,identical_tree=True,records=records),ensure_ascii=False,indent=2)+'\n')
print('全ファイルを転送し、元の保存コミットとの木の一致を確認',flush=True)
