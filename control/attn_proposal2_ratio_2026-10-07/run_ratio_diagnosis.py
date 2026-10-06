"""段1の保存記録診断だけを、種ごとの受付で最大4件進める。"""
import importlib.util,json,subprocess,time
from pathlib import Path
JOB=Path(__file__).resolve().parent;BASE=JOB.parent;SOURCE=BASE/'source';SUP=JOB/'ratio_diagnostics/diagnosis_supervision'
SUP.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('resource_supervisor',BASE/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
M.JOB,M.OUTPUT,M.MAX_WORKERS=SUP,JOB/'ratio_diagnostics/diagnosis',4
M.OUTPUT.mkdir(parents=True,exist_ok=True)
M.state={'status':'diagnosis_preparing','completed':{'1':[],'2':[]},'mem_gb':.3,'stage1_record_only':True,'phase3_started':False}
def check(w,s):return M.OUTPUT/f'n3_w{w}_A_L50'/f'seed{s:03d}.diagnosis.check.json'
def start(w,s):
 M.machine(f'案2比の記録診断・世界{w}種{s}の開始前')
 cmd=[M.PYTHON,M.JOBS,'run','--wait','--owner',f'Codex2 案2比 記録診断 W{w} s{s:03d}','--mem','0.3','--disk-path',str(M.OUTPUT),'--',M.PYTHON,str(SOURCE/'tools/attnratio_diagnosis.py'),'--base',str(BASE),'--old-job',str(JOB),'--world',str(w),'--seed',str(s),'--output',str(M.OUTPUT)]
 log=(SUP/f'w{w}_s{s:03d}.log').open('x');p=subprocess.Popen(cmd,cwd=SOURCE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 M.active.append({'world':w,'seed':s,'pid':p.pid,'process':p,'log':log,'adopted':False});M.append('commands.jsonl',{'pid':p.pid,'command':cmd});M.status(status='diagnosing_or_waiting_for_claim')
def main():
 if (SUP/'status.json').exists():raise RuntimeError('記録診断の監督を重複しない')
 assert json.loads((JOB/'comparison_supervision/status.json').read_text())['status']=='complete_comparison_ready_for_aggregation'
 M.machine('案2比の記録診断の開始前')
 order=[(w,s) for s in range(1,21) for w in (1,2)]
 for w,s in order:
  if check(w,s).exists():
   d=json.loads(check(w,s).read_text());assert d['passed'] and d['trials']==1740
   M.state['completed'][str(w)].append(s);M.append('checks.jsonl',d)
 while sum(len(v) for v in M.state['completed'].values())<40:
  for item in list(M.active):
   p=item['process']
   if p.poll() is not None:
    assert p.returncode==0,(item['world'],item['seed'],p.returncode)
    d=json.loads(check(item['world'],item['seed']).read_text());assert d['passed'] and d['trials']==1740
    M.state['completed'][str(item['world'])].append(item['seed']);M.state['completed'][str(item['world'])].sort();M.append('checks.jsonl',d)
    M.active.remove(item);item['log'].close();M.status(status='diagnosis_seed_complete')
  active={(r['world'],r['seed']) for r in M.active}
  pending=[(w,s) for w,s in order if s not in M.state['completed'][str(w)] and (w,s) not in active]
  for w,s in pending[:max(0,4-len(M.active))]:start(w,s)
  M.machine('案2比の記録診断の実行中');time.sleep(5)
 M.machine('段1の40種・69600試行の記録診断の完了');M.status(status='complete_diagnosis_ready_for_aggregation')
if __name__=='__main__':
 try:main()
 except BaseException as e:M.stop_own_jobs();M.status(status='stopped_diagnosis',error=repr(e));raise
