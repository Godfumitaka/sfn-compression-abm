import os,json,subprocess,time,shutil,sys
from pathlib import Path
out=Path(__file__).resolve().parent
src=out.parent/'source'
env=dict(os.environ,PYTHONHASHSEED='0')
for k in ('LC_CTYPE','LC_ALL','LANG'):env.pop(k,None)
results=[]
for job in json.loads((out/'commands.json').read_text()):
 thermal=subprocess.check_output(['pmset','-g','therm'],text=True)
 if 'No thermal warning level has been recorded' not in thermal or 'No performance warning level has been recorded' not in thermal:
  (out/'resource_stop.json').write_text(json.dumps({'reason':'新しい走行の前の熱の確認','thermal':thermal},ensure_ascii=False)+'\n');raise SystemExit(4)
 if shutil.disk_usage(out).free<18*1024**3:raise SystemExit('空きが15GiBへ近づいた')
 if (out.parent/'stage4_full_01/resource_stop.json').exists():raise SystemExit('先行する関門が資源で停止')
 if Path(job['cmd'][3]).exists():raise SystemExit('出力先が既にある')
 start=time.monotonic()
 with (out/f"seed{job['seed']}.log").open('w') as f:
  p=subprocess.Popen(job['cmd'],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
  while p.poll() is None:
   if shutil.disk_usage(out).free<18*1024**3:
    (out/'resource_stop.json').write_text(json.dumps({'reason':'空きが15GiBへ近づいた'})+'\n');p.terminate();break
   time.sleep(10)
  code=p.wait()
 print(json.dumps({'seed':job['seed'],'exit':code,'seconds':time.monotonic()-start}),flush=True)
 if code:raise SystemExit(code)
 audit=out/f"seed{job['seed']}.audit.json"
 p=subprocess.run([sys.executable,'tools/sme_replay_audit.py',job['cmd'][3],str(audit)],cwd=src,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (out/f"seed{job['seed']}.audit.log").write_text(p.stdout)
 if p.returncode:print(p.stdout,flush=True);raise SystemExit(p.returncode)
 results.append(json.loads(audit.read_text()));(out/'audits.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'seed':job['seed'],'conv_FH':results[-1]['conv_FH'],'conv_HU':results[-1]['conv_HU'],'u_trials':results[-1]['post_u_trials']}),flush=True)
