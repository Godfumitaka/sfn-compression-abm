import os,json,subprocess,time,gzip,hashlib,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
src=root.parent/'source';original=root/'A_seed1';output=root/'analysis_A_seed1'
manifest=original/'manifest.jsonl'
while True:
 if (root/'resource_stop.json').exists():raise SystemExit('先行する走行が資源で停止')
 if manifest.exists() and manifest.stat().st_size:
  records=[json.loads(x) for x in manifest.read_text().splitlines()]
  if any(r.get('error') for r in records):raise SystemExit('先行する走行が失敗')
  if records[0].get('smereplay',{}).get('updates')==1740:break
 time.sleep(10)
env=dict(os.environ,PYTHONHASHSEED='0')
for k in ('LC_CTYPE','LC_ALL','LANG'):env.pop(k,None)
def fail(reason):
 (root.parent/'stage4_gate_stop.json').write_text(json.dumps({'reason':reason},ensure_ascii=False)+'\n');raise SystemExit(reason)
with (root/'audit_original.log').open('w') as f:
 p=subprocess.run([os.sys.executable,'tools/sme_replay_audit.py',str(original),str(root/'audit_original.json')],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
if p.returncode:fail('全走行の独立の検査が不一致')
thermal=subprocess.check_output(['pmset','-g','therm'],text=True)
if 'No thermal warning level has been recorded' not in thermal or 'No performance warning level has been recorded' not in thermal:fail('再生の前の熱の確認で停止')
if shutil.disk_usage(root).free<18*1024**3:fail('再生の前に空きが15GiBへ近づいた')
state=next(original.glob('side/*/*.sme.states.jsonl.gz'))
cmd=[os.sys.executable,'tools/selcands_sme.py',str(root/'command.json'),str(output),str(state)]
(root/'analysis.command.json').write_text(json.dumps(cmd,ensure_ascii=False,indent=2)+'\n')
t=time.monotonic()
with (root/'analysis.log').open('w') as f:
 p=subprocess.Popen(cmd,cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
 while p.poll() is None:
  if shutil.disk_usage(root).free<18*1024**3:p.terminate();break
  time.sleep(10)
 code=p.wait()
print(json.dumps({'analysis_exit':code,'seconds':time.monotonic()-t}),flush=True)
if code:fail('1740試行の再生と解析が終了しなかった')
with (root/'audit_analysis.log').open('w') as f:
 p=subprocess.run([os.sys.executable,'tools/sme_replay_audit.py',str(output),str(root/'audit_analysis.json')],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
if p.returncode:fail('全件の解析の独立の検査が不一致')
def body(folder):
 with gzip.open(next(folder.glob('ledgers/cells/*/*.gz')),'rb') as f:f.readline();return hashlib.sha256(f.read()).hexdigest()
sides=[]
for p in original.glob('side/*/*'):
 if '.sme.' in p.name:continue
 q=output/'side'/p.parent.name/p.name
 sides.append({'file':p.name,'equal':q.read_bytes()==p.read_bytes()})
result={'body_sha_original':body(original),'body_sha_analysis':body(output),'sides':sides,'replay':json.loads((output/'manifest.jsonl').read_text())['smereplay']}
(root/'analysis_compare.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
if result['body_sha_original']!=result['body_sha_analysis'] or not all(s['equal'] for s in sides):fail('1740試行の解析で本体か共通sideが変わった')
