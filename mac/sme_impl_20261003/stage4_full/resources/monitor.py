from pathlib import Path
import json,datetime,subprocess,shutil,time
root=Path(__file__).resolve().parent.parent
last_report=datetime.datetime(2026,10,3,19,0,tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
for line in (root/'source/control/2026-09-30_Codex_進み具合.md').read_text().splitlines():
 if 'SME段4：' in line:
  try: last_report=datetime.datetime.strptime(line[:16],'%Y-%m-%d %H:%M').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
  except ValueError: pass
log=Path(__file__).with_name('resources.jsonl')
paths=['stage4_full_01/A_seed1','stage4_zero_01/A_zero_seed1','stage4_zero_01/A_zero_seed2','stage4_full_01/analysis_A_seed1']
def progress(folder):
 p=root/folder;trial=None
 for f in p.glob('side/*/seed*.jsonl'):
  if f.name.count('.')!=1:continue
  with f.open('rb') as stream:
   size=f.stat().st_size;stream.seek(max(0,size-262144));raw=stream.read()
  lines=raw.splitlines();lines=lines[1:] if size>262144 else lines
  for line in lines:
   try:d=json.loads(line)
   except ValueError:continue
   if isinstance(d.get('trial'),int):trial=max(trial if trial is not None else -1,d['trial'])
 return {'run':folder,'last_trial':trial,'manifest':(p/'manifest.jsonl').exists()}
while True:
 now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
 facts=[progress(f) for f in paths]
 thermal=subprocess.check_output(['pmset','-g','therm'],text=True).strip()
 swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True).strip()
 proc=subprocess.check_output(['ps','-axo','pid,ppid,%cpu,rss,command'],text=True)
 heavy=[];processes={}
 for line in proc.splitlines()[1:]:
  bits=line.split(None,4)
  if len(bits)==5:
   processes[int(bits[0])]={'pid':int(bits[0]),'ppid':int(bits[1]),'cpu':float(bits[2]),'rss_kb':int(bits[3]),'command':bits[4]}
 serial={pid for pid,p in processes.items() if p['command'].split()[0].split('/')[-1] in ('Python','python3.12','python3') and '--v311c-serial' in p['command'] and 'tools/v3_run.py' in p['command']}
 def group(pid):
  visited=set()
  while pid in processes and processes[pid]['ppid'] in serial and pid not in visited:
   visited.add(pid);pid=processes[pid]['ppid']
  return pid
 serial_roots={group(pid) for pid in serial}
 for pid,p in processes.items():
  if p['cpu']>20:
   heavy.append({k:p[k] for k in ('pid','ppid','cpu','rss_kb')} | {'name':p['command'].split()[0].split('/')[-1]})
 heavy_units=len(serial_roots)+sum(p['pid'] not in serial for p in heavy)
 row={'time':now.isoformat(),'progress':facts,'free_bytes':shutil.disk_usage(root).free,'swap':swap,'thermal':thermal,'heavy':heavy,'heavy_units':heavy_units,'serial_groups':sorted(serial_roots)}
 with log.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(json.dumps(row,ensure_ascii=False),flush=True)
 if (now-last_report).total_seconds()>=1800:
  line=now.strftime('%Y-%m-%d %H:%M JST')+' SME段4：'+ '、'.join(f["run"].split('/')[-1]+f" 試行{f['last_trial']}" for f in facts if f['last_trial'] is not None)+f"。空き{row['free_bytes']/2**30:.1f}GiB、同時計算{heavy_units}本、CPU20%超{len(heavy)}プロセス。本番160本は未開始。"
  for dest in (root/'source/control/2026-09-30_Codex_進み具合.md',root.parent/'codex_worldv4_2026-10-01/results/control/2026-09-30_Codex_進み具合.md'):
   with dest.open('a') as f:f.write('\n'+line+'\n')
  last_report=now
 if (root/'stage4_gate_stop.json').exists():break
 if (root/'stage4_full_01/analysis_compare.json').exists() and (root/'stage4_zero_01/audits.json').exists():
  if len(json.loads((root/'stage4_zero_01/audits.json').read_text()))==2:break
 time.sleep(60)
