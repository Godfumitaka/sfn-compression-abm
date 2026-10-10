"""指示22：別候補の構造検査。原版・観察器・停止と候補を前後照合する。"""
from pathlib import Path
import datetime, hashlib, json, os, resource, subprocess, sys, time
from resource_census_02 import census
here = Path(__file__).resolve().parent
source = here.parent/'source_verb_probe_names_instruction22'
protected = json.loads((here/'candidate_protected_01.json').read_text())
def current():
    return {root:{name:hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()
                  for name in files} for root,files in protected.items()}
assert current() == protected
rows, active, paused = census()
assert len(active) < 8
began = time.perf_counter()
argv = [sys.executable, '-m', 'pytest', '-q', 'tools/test_useforget_instruction9.py',
        'tools/test_useforget_instruction12.py', 'tools/test_useforget_instruction13.py',
        'tools/test_attn_probe_names_instruction22.py', '-p', 'no:cacheprovider',
        '--basetemp', str(here/'structure_01')]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
           PYTHONPATH=str(here.parent/'instruction3/test_dependencies_01')+':'+str(source/'tools')+':'+str(source))
with (here/'structure_01.log').open('xb') as log:
    code = subprocess.call(argv, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
after = current()
result = dict(exit_code=code, passed=code==0 and after==protected,
              protected_unchanged=after==protected, seconds=time.perf_counter()-began,
              max_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              ended_at_jst=datetime.datetime.now().astimezone().isoformat(),
              argv=argv, model_started=False, synthetic_only=True)
(here/'structure_status_01.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
sys.exit(code or int(after != protected))
