from pathlib import Path
import os,re,subprocess,json,shutil,datetime
def census():
    # 受付後にも低RSSを含む全psの親子を読む。待つ親・受付・trackerは二重計数しない。
    text=subprocess.check_output(['ps','-axo','pid=,ppid=,stat=,rss=,command='],text=True)
    raw={}
    for line in text.splitlines():
        values=line.strip().split(None,4)
        if len(values)==5:
            pid,parent,state,rss,command=values
            raw[int(pid)]=dict(parent=int(parent),state=state,rss_kib=int(rss),command=command)
    selected={p for p,r in raw.items() if p!=os.getpid() and re.search(r'(^|/)python[^/]*$', r['command'].split()[0], re.I)
              and 'jobs.py' not in r['command'] and 'resource_tracker' not in r['command'] and 'ps -axo' not in r['command']}
    ancestors=set()
    for pid in selected:
        parent=raw[pid]['parent'];seen=set()
        while parent in raw and parent not in seen:
            seen.add(parent)
            if parent in selected:ancestors.add(parent)
            parent=raw[parent]['parent']
    leaves=selected-ancestors
    active={p for p in leaves if 'T' not in raw[p]['state'] and not raw[p]['state'].startswith('Z')}
    paused={p for p in leaves if 'T' in raw[p]['state']}
    return raw,active,paused
T=Path(__file__).resolve().parents[2]
here=Path(__file__).resolve().parent
rows,active,paused=census()
value=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),method='全ps親子・低RSSも含む、待つ祖先/jobs/resource_trackerは二重計数しない',active_model_count_conservative=len(active),paused_model_count=len(paused),active=[dict(pid=p,**rows[p]) for p in sorted(active)],paused=[dict(pid=p,**rows[p]) for p in sorted(paused)],all_ps=rows,free_disk_bytes=shutil.disk_usage(T/'instruction12/B5/B5_on200_after/output').free,model_limit=8,disk_minimum_bytes=20*2**30,analysis_only=True)
assert len(active)<=8 and value['free_disk_bytes']>=20*2**30
(here/'before_comparison_start_01.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in value.items() if k not in ('active','paused','all_ps')},ensure_ascii=False))
