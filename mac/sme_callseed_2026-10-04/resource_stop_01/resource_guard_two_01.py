"""自分の二走行だけを監視。18GiBの下限に近づいたら個々の子を保存したまま停止。"""
from pathlib import Path
from datetime import datetime
import json,os,shutil,signal,subprocess,time
ROOT=Path(__file__).resolve().parent
# 起動済みの専用の観察器・計算する子。この一覧以外へ信号を送らない。
EXPECTED={17224:17221,17334:17331}
PAUSE_AT=(18+.5)*2**30
OUT=ROOT/'resource_guard_two_01.jsonl'

def own(pid,parent):
    lines=subprocess.check_output(['/bin/ps','-p',str(pid),'-o','ppid=,command='],text=True).strip()
    parts=lines.split(None,1)
    return len(parts)==2 and int(parts[0])==parent and 'multiprocessing.spawn' in parts[1]

def tail(folder):
    p=ROOT/folder/'performance.jsonl'
    if not p.exists():return None
    with p.open('rb') as f:f.seek(max(0,p.stat().st_size-4096));rows=f.read().splitlines()
    try:return json.loads(rows[-1])['trial']+1
    except (ValueError,KeyError,IndexError):return None

def recent_swap():
    p=Path('/Users/tatsu-admin/jobs/swap.tsv');rows=[]
    for line in p.read_text().splitlines():
        a=line.split('\t')
        if len(a)>=4 and a[1]!='None' and float(a[0])>=time.time()-600:rows.append(a)
    grew=bool(rows) and max(float(a[1]) for a in rows)>float(rows[0][1])
    warning=next((a[3] for a in rows[-2:] if a[3]!='ok'),None)
    return grew,warning,float(rows[-1][1]) if rows else None
while True:
    if all((ROOT/name/'run_result.json').exists() for name in ('full_baseline_01','full_repeat_01')):break
    free=shutil.disk_usage(ROOT).free;grew,warning,swap=recent_swap()
    row={'time':datetime.now().astimezone().isoformat(),'free_bytes':free,'trials':[tail(n) for n in ('full_baseline_01','full_repeat_01')],'swap_mb':swap,'swap_grew':grew,'thermal_warning':warning}
    stop=free<PAUSE_AT or grew or warning is not None
    if stop:
        row['action']='pause';row['reason']='空き18GiBの下限に近づいた' if free<PAUSE_AT else 'スワップ増加' if grew else '熱・性能の警告';row['stopped']=[]
        for pid,parent in EXPECTED.items():
            if own(pid,parent):os.kill(pid,signal.SIGSTOP);row['stopped'].append(pid)
        (ROOT/'resource_pause_two_01.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
    with OUT.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    if stop:print(json.dumps(row,ensure_ascii=False),flush=True);break
    time.sleep(30)
