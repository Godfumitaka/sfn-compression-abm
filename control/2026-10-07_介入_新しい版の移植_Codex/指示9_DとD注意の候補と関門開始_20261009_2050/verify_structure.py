"""指示9の手例だけを受付内で検査する。"""
from pathlib import Path
import subprocess,sys,os,json,time,datetime,resource
port=Path(__file__).resolve().parents[1]
source=port/'source_c792_D_instruction9'
dest=port/'instruction9'/sys.argv[1]
dest.mkdir(exist_ok=False)
command=[sys.executable,'-m','pytest','-q',str(source/'tools/test_useforget_instruction9.py'),'--junitxml='+str(dest/'pytest.xml')]
env=dict(os.environ,PYTHONPATH=os.pathsep.join(map(str,(source/'tools',source,port/'instruction3/test_dependencies_01'))),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
status=dict(status='running',pid=os.getpid(),command=command,model_run_called=False)
def save(): (dest/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
save();start=time.perf_counter()
p=subprocess.run(command,cwd=source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(dest/'pytest.log').write_text(p.stdout)
print(p.stdout)
status.update(status='passed' if p.returncode==0 else 'stopped',exit_code=p.returncode,seconds=time.perf_counter()-start,peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,at_jst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'))
save();sys.exit(p.returncode)
