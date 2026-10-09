"""指示12Aの自然停止を保存する。再走行や候補修正はしない。"""
from pathlib import Path
import datetime, hashlib, json, platform, shutil, subprocess, sys, time
root=Path(__file__).resolve().parent
port=root.parent
sys.path.insert(0,str(port))
from admission_guard import census
started=time.perf_counter()
def now(): return datetime.datetime.now().astimezone().isoformat()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()
rows,active,paused=census();parents=set()
for pid in active|paused:
 parent=rows[pid]['parent'];seen=set()
 while parent in rows and parent not in seen:
  seen.add(parent)
  if parent in active|paused: parents.add(parent)
  parent=rows[parent]['parent']
active-=parents;paused-=parents
machine=dict(at_jst=now(),active=len(active),paused=len(paused),processes=[dict(pid=p,**rows[p]) for p in sorted(active|paused)],excluded_parents=sorted(parents),free_disk_bytes=shutil.disk_usage(root).free,thermal=subprocess.check_output(['pmset','-g','therm'],text=True),swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True))
(root/'A_stop_record_before_start_01.json').write_text(json.dumps(machine,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8 and machine['free_disk_bytes']>=20*2**30
out=root/'A_D_stop_evidence_01.json';assert not out.exists()
result=dict(status='recorded_stop',A_passed=False,source_accepted=False,formal_3b_material=False,runs={},no_model_rerun=True,no_source_correction=True)
for label in ('A_D_attention_04_retry01','A_D_attention_015_retry01'):
 folder=root/label
 s=json.loads((folder/'status.json').read_text());assert s['state']=='stopped' and s['exit_code']==3
 assert s['protected_unchanged']
 assert json.loads((folder/'protected_before.json').read_text())==json.loads((folder/'protected_after.json').read_text())
 lines=(folder/'model.log').read_text().splitlines();needle='RuntimeError: 指示12：試験がDの状態又は記録を変えた（試行 100）'
 hits=[i+1 for i,line in enumerate(lines) if line==needle];assert hits
 manifest=[json.loads(line) for line in (folder/'output/manifest.jsonl').read_text().splitlines()];assert len(manifest)==1 and '試行 100' in manifest[0]['error']
 details=[]
 for pattern in ('retention/**/seed001.jsonl','side/**/seed001.useforget.jsonl'):
  found=list((folder/'output').glob(pattern));assert len(found)==1
  records=[json.loads(line) for line in found[0].read_text().splitlines()]
  details.append(dict(path=str(found[0]),rows=len(records),trial_first=records[0]['trial'] if records else None,trial_last=records[-1]['trial'] if records else None))
 result['runs'][label]=dict(state=s['state'],exit_code=s['exit_code'],started_at_jst=s['started_at_jst'],ended_at_jst=s['ended_at_jst'],admission_wait_seconds=s['admission_wait_seconds'],cpu_wait_seconds=s['cpu_wait_seconds'],model_seconds=s['model_seconds'],peak_children_rss_bytes=s['peak_children_rss_bytes'],first_error_log=str(folder/'model.log'),first_error_line=hits[0],first_probe_boundary=100,guard_source=str(port/'source_verb_instruction12/tools/useforget_cstar.py'),guard_source_line=42,manifest=manifest,partial_D_records=details,protected_unchanged=True,completion_marker_present=(folder/'output/measurement/partial_done.json').exists(),probe_checks_saved=any((folder/'output').rglob('*.probe_checks.json')),files_sha256={str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()})
source=port/'source_verb_instruction12'
result.update(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),source_status=subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True),source_files_sha256={str(p.relative_to(source)):sha(p) for p in [source/'tools/v3_run.py',source/'tools/useforget_cstar.py',source/'tools/useforget.py',source/'tools/test_useforget_instruction9.py',source/'tools/test_useforget_instruction12.py']},scope_note='ST/AUDITと開いているD記録口の位置・原字節を一緒に照合する検査が失敗。個別の最初の変化箇所は保存されておらず特定しない。',at_jst=now(),seconds=time.perf_counter()-started)
assert result['source_commit']=='54f0a412201bc5c67efdfa6689fed07fa3250e31' and not result['source_status']
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status=result['status'],runs={k:dict(first_error_line=v['first_error_line'],partial_D_records=v['partial_D_records']) for k,v in result['runs'].items()}),ensure_ascii=False))
