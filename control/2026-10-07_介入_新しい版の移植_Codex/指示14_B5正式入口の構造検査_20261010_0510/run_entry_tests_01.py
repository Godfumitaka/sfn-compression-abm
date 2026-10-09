from pathlib import Path
import datetime,json,shutil,subprocess,sys
port=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(port))
from admission_guard import census
rows,active,paused=census();parents=set()
for pid in active|paused:
    parent=rows[pid]['parent'];seen=set()
    while parent in rows and parent not in seen:
        seen.add(parent)
        if parent in active|paused:parents.add(parent)
        parent=rows[parent]['parent']
active-=parents;paused-=parents
folder=port/'instruction14/cloud_gate_entry_01'
assert len(active)<8 and shutil.disk_usage(folder).free>=20*2**30
before=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
 excluded_parents=sorted(parents),processes=[dict(pid=p,**rows[p]) for p in sorted(active|paused)],free_disk_bytes=shutil.disk_usage(folder).free)
with (folder/'tests_before_start_01.json').open('x') as f:json.dump(before,f,ensure_ascii=False,indent=2)
command=[sys.executable,'-B',str(folder/'test_entry.py')]
with (folder/'test_entry_01.log').open('x') as f:r=subprocess.run(command,cwd=folder,stdout=f,stderr=subprocess.STDOUT)
with (folder/'structural_tests_01.json').open('x') as f:
 json.dump(dict(at_jst=datetime.datetime.now().astimezone().isoformat(),exitcode=r.returncode,passed=r.returncode==0,
 command=command,scope='受付・停止・8体全記録の構造の小例のみ。模型やクラウドの実関門ではない。',production_started=False),f,ensure_ascii=False,indent=2)
print((folder/'test_entry_01.log').read_text());sys.exit(r.returncode)
