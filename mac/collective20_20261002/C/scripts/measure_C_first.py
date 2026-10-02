"""最初の集団走行だけを実行し、所要時間・常駐メモリ・熱・スワップを記録。模型を編集しない。"""
from pathlib import Path
import json, os, re, subprocess, time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
OLD = ROOT / 'outputs'
OUT = ROOT / 'outputs_C'
OUT.mkdir(exist_ok=True)
# Aの監視が自然に終了してからCを始め、二つの監視が同じ処理を止めないようにする。
guard_deadline=time.monotonic()+60
while any(line.endswith(str(ROOT/'combined_parallel.py')) for line in
          subprocess.check_output(['/bin/ps','-axo','command='],text=True).splitlines()):
    assert time.monotonic()<guard_deadline,'Aの並列監視の終了を確認できないためCを開始しない'
    time.sleep(2)
NAME = 'pilot_w2_no_comm_g001'
assert not (OUT / NAME).exists()
argv = json.loads((OLD / (NAME+'.argv.json')).read_text())['argv']
argv[3] = str(OUT / NAME)
assert '--cf-learn' not in argv
argv.append('--cf-learn')
def now(): return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
def health():
    data = {'time':now(), 'disk_free_bytes': __import__('shutil').disk_usage(ROOT).free}
    for key, command in [('thermal',['/usr/bin/pmset','-g','therm']),('swap',['/usr/sbin/sysctl','vm.swapusage'])]:
        p=subprocess.run(command,capture_output=True,text=True)
        data[key]={'returncode':p.returncode,'output':p.stdout+p.stderr}
    match=re.search(r'used\s*=\s*([\d.]+)M',data['swap']['output'])
    data['swap_used_mib']=float(match[1]) if match else None
    return data
def tree(pid):
    text=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,rss=,command='],text=True)
    rows=[]
    for line in text.splitlines():
        parts=line.strip().split(None,3)
        if len(parts)==4: rows.append((int(parts[0]),int(parts[1]),int(parts[2]),parts[3]))
    descendants={pid}
    while True:
        nxt=descendants|{p for p,parent,_,_ in rows if parent in descendants}
        if nxt==descendants: break
        descendants=nxt
    group=[(p,rss,cmd) for p,_,rss,cmd in rows if p in descendants]
    return group
initial=health()
assert initial['disk_free_bytes']>15*1024**3
assert initial['thermal']['returncode']==initial['swap']['returncode']==0,initial
assert 'No thermal warning level has been recorded' in initial['thermal']['output'],initial
(OUT/(NAME+'.argv.json')).write_text(json.dumps({'argv':argv,'cwd':str(SOURCE),'start':now()},ensure_ascii=False,indent=1)+'\n')
start=time.monotonic()
max_total_kib=max_process_kib=0
samples=0
with (ROOT/'C_first.stdout.log').open('w') as fo, (ROOT/'C_first.time_and_stderr.log').open('w') as fe, (ROOT/'C_first.health.jsonl').open('w') as fh:
    fh.write(json.dumps(initial,ensure_ascii=False)+'\n');fh.flush()
    p=subprocess.Popen(['/usr/bin/time','-l',*argv],cwd=SOURCE,stdout=fo,stderr=fe,start_new_session=True)
    (ROOT/'C_first.pid.json').write_text(json.dumps({'pid':p.pid,'start':now()})+'\n')
    last_health=start
    while p.poll() is None:
        group=tree(p.pid)
        total=sum(x[1] for x in group)
        single=max([x[1] for x in group] or [0])
        max_total_kib=max(max_total_kib,total)
        max_process_kib=max(max_process_kib,single)
        samples+=1
        if time.monotonic()-last_health>=10:
            h=health();h.update(process_tree_rss_kib=total,process_count=len(group))
            fh.write(json.dumps(h,ensure_ascii=False)+'\n');fh.flush();last_health=time.monotonic()
        time.sleep(1)
    final=health();fh.write(json.dumps(final,ensure_ascii=False)+'\n')
result={'name':NAME,'exit_code':p.returncode,'elapsed_seconds':time.monotonic()-start,
        'sampled_tree_peak_rss_kib':max_total_kib,'sampled_process_peak_rss_kib':max_process_kib,
        'sample_period_seconds':1,'samples':samples,'initial':initial,'final':final,'finished':now()}
stderr=(ROOT/'C_first.time_and_stderr.log').read_text()
m=re.search(r'(\d+)\s+maximum resident set size',stderr)
result['time_maximum_resident_bytes']=int(m[1]) if m else None
(ROOT/'C_first.measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(p.returncode)
