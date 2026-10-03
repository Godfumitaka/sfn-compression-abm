from pathlib import Path
import json
root=Path(__file__).resolve().parent.parent
r=json.loads(Path(__file__).with_name('resources.jsonl').read_text().splitlines()[-1])
failures=[]
for folder in ('stage4_full_01/A_seed1','stage4_zero_01/A_zero_seed1','stage4_zero_01/A_zero_seed2','stage4_full_01/analysis_A_seed1'):
 p=root/folder/'manifest.jsonl'
 if p.exists():
  for line in p.read_text().splitlines():
   d=json.loads(line)
   if d.get('error'):failures.append({'run':folder,'error':d['error']})
for base,name in (('stage4_zero_01','seed1.audit'),('stage4_zero_01','seed2.audit'),('stage4_full_01','audit_original'),('stage4_full_01','audit_analysis')):
 log=root/base/(name+'.log');out=root/base/(name+'.json')
 if log.exists() and not out.exists() and 'Traceback' in log.read_text():failures.append({'log':str(log),'last_lines':log.read_text()[-1500:]})
for p in (root/'stage4_gate_stop.json',root/'stage4_full_01/resource_stop.json',root/'stage4_zero_01/resource_stop.json'):
 if p.exists():failures.append({'stop':str(p),'reason':json.loads(p.read_text())})
print(json.dumps({'time':r['time'],'progress':[(x['run'].split('/')[-1],x['last_trial'],x['manifest']) for x in r['progress']],'free_GiB':round(r['free_bytes']/2**30,1),'heavy_units':r.get('heavy_units',len(r['heavy'])),'cpu20_processes':len(r['heavy']),'thermal':r['thermal'].splitlines()[:2],'swap':r['swap'],'failures':failures},ensure_ascii=False))
