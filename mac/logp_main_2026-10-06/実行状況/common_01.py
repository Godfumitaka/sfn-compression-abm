"""自分の出力先・資源・CPUの記録を扱う小さな補助。"""
from pathlib import Path
from datetime import datetime
import json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parent
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS='/Users/tatsu-admin/jobs/jobs.py'
def save(path,value):
    temp=Path(str(path)+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
def now():return datetime.now().astimezone().isoformat()
def conditions():
    rows=[]
    for line in Path('/Users/tatsu-admin/jobs/swap.tsv').read_text().splitlines():
        a=line.split('\t')
        if len(a)>=4 and a[1]!='None' and float(a[0])>=time.time()-600:rows.append(a)
    return {'at':now(),'free_bytes':shutil.disk_usage(ROOT).free,'swap_grew':bool(rows) and max(float(a[1]) for a in rows)>float(rows[0][1]),'thermal_warning':next((a[3] for a in rows[-2:] if a[3]!='ok'),None),'swap_mb':float(rows[-1][1]) if rows else None}
def ps():
    rows={}
    for line in subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,stat=,%cpu=,rss=,command='],text=True).splitlines():
        at=line.strip().split(None,6)
        if len(at)==7:rows[int(at[0])]={'ppid':int(at[1]),'pgid':int(at[2]),'stat':at[3],'cpu':float(at[4]),'rss':int(at[5])*1024,'command':at[6]}
    return rows
def descendants(pid,rows):
    ans={pid};changed=True
    while changed:
        changed=False
        for p,x in rows.items():
            if x['ppid'] in ans and p not in ans:ans.add(p);changed=True
    return ans
def cpu_reading(active):
    rows=ps();own=set()
    for job in active:own.update(descendants(job['child'].pid,rows))
    candidates={p:x for p,x in rows.items() if ('python' in Path(x['command'].split()[0]).name.lower()) and '/jobs/jobs.py' not in x['command'] and 'resource_tracker' not in x['command'] and 'T' not in x['stat'] and (x['rss']>=100*2**20 or 'spawn_main' in x['command'] or x['cpu']>=10)}
    # まとめ役と計算する子を二重に数えない。子がない読み取り処理は一本分。
    leaves={p:x for p,x in candidates.items() if not any(q!=p and q in descendants(p,rows) for q in candidates)}
    external={p:x for p,x in leaves.items() if p not in own}
    return {'at':now(),'cores':10,'cap':8,'external_compute_processes':external,'external_count':len(external),'own_reserved_slots':len(active),'total_reserved_slots':len(external)+len(active),'own_compute_count':sum(p in own for p in leaves),'total_compute_count':len(leaves)}
