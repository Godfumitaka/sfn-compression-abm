"""指示10・11の個別時間。既存の内訳の測定の後、別の出力で関門を通す。"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import json, os, signal, subprocess, sys, time, hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE/'match_times_instruction10_01'
BASE=HERE.parent/'codex_cstar_2026-10-07'
SOURCE=BASE/'source'
PY='/opt/homebrew/opt/python@3.12/bin/python3.12'
sys.path[:0]=[str(BASE),str(HERE.parent/'codex_sme_time_evict_2026-10-06'),str(HERE.parent/'codex_logp_main_2026-10-06')]
from common_01 import conditions, now, save, ps, descendants
from cpu_guard_05 import cpu_reading
from compare_gate_01 import compare

def before_deadline():
 assert datetime.now().astimezone().isoformat()<'2026-10-09T09:00:00+09:00','期限以後に新しい模型を始めない'

def run(name,baseline):
 before_deadline()
 observer_sha256=hashlib.sha256((HERE/'observe_match_times_01.py').read_bytes()).hexdigest()
 assert observer_sha256==json.loads((ROOT/'started.json').read_text())['observer_sha256'],'開始した観測台本のまま進める'
 folder=ROOT/name
 assert not folder.exists(),'完成・途中の処理を二重に始めない'
 folder.mkdir()
 command=list(json.loads((baseline.parent/(baseline.name+'.json')).read_text())['command'])
 command[3]=str(folder/'output')
 configured=int(command[command.index('--trial-count')+1])
 assert command[command.index('--seeds')+1]=='1'
 save(folder/'native_command.json',command)
 safe=conditions()
 assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
 while cpu_reading([])['total_compute_count']>=8:
  save(folder/'waiting_for_machine_cap.json',dict(at=now(),cpu=cpu_reading([])))
  time.sleep(10);before_deadline();safe=conditions()
  assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
 env=dict(os.environ,PYTHONHASHSEED='0',SME_EXACT_SOURCE=str(SOURCE))
 for key in ('LC_ALL','LANG','LC_CTYPE'):env.pop(key,None)
 args=[PY,str(HERE/'observe_match_times_01.py'),str(folder/'native_command.json')]
 start=time.monotonic();held=None;paused=0.;peak=0
 with (folder/'run.log').open('x') as log:
  proc=subprocess.Popen(args,cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  save(folder/'started.json',dict(at=now(),runner_pid=proc.pid,command=args,native_command=command,
       env={'PYTHONHASHSEED':'0'},memory_claim_gb=11,resources=safe,observer_sha256=observer_sha256))
  while proc.poll() is None:
   time.sleep(2)
   safe=conditions();cpu=cpu_reading([{'child':SimpleNamespace(pid=proc.pid)}]);rows=ps()
   rss=sum(rows[p]['rss'] for p in descendants(proc.pid,rows) if p in rows);peak=max(peak,rss)
   bad=safe['free_bytes']<18.5*2**30 or safe['swap_grew'] or safe['thermal_warning'] or cpu['external_count']+max(1,cpu['own_compute_count'])>8
   with (folder/'resources.jsonl').open('a') as f:
    f.write(json.dumps({**safe,'at':now(),'rss_bytes':rss,'own_model_count':cpu['own_compute_count'],
         'external_model_count':cpu['external_count'],'held':held is not None})+'\n')
   if bad and held is None:
    assert os.getpgid(proc.pid)==proc.pid
    os.killpg(proc.pid,signal.SIGSTOP);held=time.monotonic()
    save(folder/'resource_hold.json',dict(at=now(),resources=safe,cpu=cpu,reason='機械全体8本と資源の条件'))
   elif held is not None and not bad and safe['free_bytes']>=20*2**30:
    assert os.getpgid(proc.pid)==proc.pid
    os.killpg(proc.pid,signal.SIGCONT);paused+=time.monotonic()-held;held=None
  code=proc.returncode
 save(folder/'finished.json',dict(at=now(),exit=code,wall_seconds=time.monotonic()-start,paused_seconds=paused,
      maximum_observed_model_tree_rss_bytes=peak,sampling_seconds=2))
 if code:raise RuntimeError(name+'：計測の不通\n'+(folder/'run.log').read_text()[-4000:])
 assert hashlib.sha256((HERE/'observe_match_times_01.py').read_bytes()).hexdigest()==observer_sha256,'計測中に観測台本が変わった'
 obs=json.loads((folder/'observations_complete.json').read_text());assert obs['passed'] and obs['configured_trials']==configured
 manifest=json.loads((folder/'output/manifest.jsonl').read_text().splitlines()[-1])
 assert manifest['trial_count']==configured and manifest['smereplay']['predictions']==manifest['smereplay']['updates']==configured
 compare(baseline/'output',folder/'output',folder/'comparison.json',stop_first=True)
 save(folder/'complete.json',dict(at=now(),passed=True,configured_trials=configured,
      model_bytes_identical=True,peak_rss_mb=manifest['peak_rss_mb']))

try:
 before_deadline()
 assert json.loads((HERE/'complete.json').read_text())['passed'],'既存のCPU内訳の測定と関門が先'
 assert (HERE/'profile1740_01/analysis.json').exists(),'既存のCPU内訳の集計が先'
 assert not (ROOT/'started.json').exists()
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip().startswith('7774b60')
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE).strip()
 ROOT.mkdir(exist_ok=True)
 save(ROOT/'started.json',dict(at=now(),pid=os.getpid(),source='7774b60',memory_claim_gb=11,
      instructions=[10,11,12],own_other_models_not_concurrent=True,other_agents_allowed=True,
      observer_sha256=hashlib.sha256((HERE/'observe_match_times_01.py').read_bytes()).hexdigest()))
 run('preflight20_01',BASE/'native_preflight_02/on_own')
 run('full1740_01',BASE/'native_full_01/on_own')
 save(ROOT/'complete.json',dict(at=now(),passed=True,configured_trials=1740,model_bytes_identical=True))
except Exception as e:
 ROOT.mkdir(exist_ok=True)
 save(ROOT/'STOP.json',dict(at=now(),passed=False,reason=str(e),remaining_not_started=True))
 raise
