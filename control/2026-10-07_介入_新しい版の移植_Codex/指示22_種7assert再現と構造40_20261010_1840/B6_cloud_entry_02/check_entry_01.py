"""B6の別受付入口の構造だけを通常受付内で検査する。"""
from pathlib import Path
import datetime,hashlib,json,resource,subprocess,sys,time
here=Path(__file__).resolve().parent
original=json.loads((here/'protected_entry_sources_01.json').read_text())
def current():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original}
assert current()==original
began=time.perf_counter()
with (here/'test_entry_01.log').open('xb') as log:
    code=subprocess.call([sys.executable,str(here/'test_entry.py')],cwd=here,stdout=log,stderr=subprocess.STDOUT)
after=current()
result=dict(passed=code==0 and after==original,exit_code=code,
    protected_unchanged=after==original,seconds=time.perf_counter()-began,
    max_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ended_at_jst=datetime.datetime.now().astimezone().isoformat(),model_started=False,
    synthetic_only=True,test_count=11)
(here/'structure_status_01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
sys.exit(code or (0 if after==original else 1))
