"""指示20のB6構造関門を通常受付で一回だけ実行する。"""
from pathlib import Path
import json,os,subprocess,sys,hashlib,time,resource,datetime
port=Path(__file__).resolve().parents[2];source=port/'source_coll_D_instruction20';here=Path(__file__).resolve().parent
before=json.loads((here/'protected_sources_01.json').read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()
def fingerprints():return {root:{name:sha(Path(root)/name) for name in files} for root,files in before.items()}
assert fingerprints()==before
argv=[sys.executable,'-m','pytest','-q','tools/test_useforget_instruction9.py','tools/test_useforget_instruction12.py','tools/test_useforget_instruction13.py','tools/test_useforget_instruction20.py','-p','no:cacheprovider','--basetemp',str(here/'structure_01')]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH=str(port/'instruction3/test_dependencies_01')+':'+str(source/'tools')+':'+str(source))
began=time.perf_counter();started=time.time()
with (here/'hand_01.log').open('x') as log:code=subprocess.call(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
after=fingerprints();(here/'protected_after_01.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
value=dict(exit_code=code,seconds=time.perf_counter()-began,argv=argv,protected_unchanged=after==before,ended_at_jst=datetime.datetime.now().astimezone().isoformat(),admission_to_entry_seconds=started-float(os.environ['INTERVENTION_TEST_SUBMITTED_EPOCH']),independent_cpu_wait_seconds=None,model_started=False,max_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
(here/'hand_gate_01.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print((here/'hand_01.log').read_text(),flush=True);sys.exit(code or int(after!=before))
