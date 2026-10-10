"""B6受付入口の構造検査の投入記録。模型は始めない。"""
from pathlib import Path
import datetime,json,os,subprocess,sys
here=Path(__file__).resolve().parent
sys.path.insert(0,str(here.parents[1]/'instruction22'))
from resource_census_01 import census
assert not (here/'launch_request_01.json').exists()
rows,active,paused=census()
record=dict(at_jst=datetime.datetime.now().astimezone().isoformat(),active=len(active),paused=len(paused),
    active_pids=sorted(active),paused_pids=sorted(paused),ps=rows)
(here/'before_check_01.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
assert len(active)<8
cmd=[sys.executable,str(Path.home()/'jobs/jobs.py'),'run','--wait','--owner','intervention-instruction21-B6-cloud-entry-structure01',
    '--mem','0.3','--disk-path',str(here),'--',sys.executable,str(here/'check_entry_01.py')]
(here/'launch_request_01.json').write_text(json.dumps(dict(at_jst=record['at_jst'],argv=cmd),ensure_ascii=False,indent=2)+'\n')
with (here/'admission_01.log').open('xb') as log:
    code=subprocess.call(cmd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
sys.exit(code)
