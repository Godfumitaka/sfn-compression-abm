"""指示21の低RSSを含む親子計数と同じ読み口。"""
import os,re,subprocess
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
    # 子の模型がまだ無い受付待ちでも、jobs run --waitのPython祖先は待つ親。
    for pid, row in raw.items():
        if 'jobs.py run --wait' in row['command']:
            parent = row['parent']; seen = set()
            while parent in raw and parent not in seen:
                seen.add(parent)
                if parent in selected:
                    ancestors.add(parent)
                parent = raw[parent]['parent']
    leaves=selected-ancestors
    active={p for p in leaves if 'T' not in raw[p]['state'] and not raw[p]['state'].startswith('Z')}
    paused={p for p in leaves if 'T' in raw[p]['state']}
    return raw,active,paused
