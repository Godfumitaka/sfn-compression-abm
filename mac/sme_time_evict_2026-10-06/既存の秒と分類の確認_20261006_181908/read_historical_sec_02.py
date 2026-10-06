"""既存三本の一試行の秒の有無だけを読む。模型と再生を走らせない。"""
from pathlib import Path
import csv,gzip,hashlib,json
R=Path(__file__).resolve().parent
rows=[('intern_A_benchmark',R.parent/'codex_sme_amemory_2026-10-05/vanilla_01/A',1),('baseline_s02',R.parent/'codex_sme_logp_2026-10-05/runs_01/baseline_s02',2),('baseline_s03',R.parent/'codex_sme_logp_2026-10-05/runs_01/baseline_s03',3)]
proof=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
with (R/'historical_sec_trial.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['run','seed','trial','sec_trial','status','source']);w.writeheader()
 for name,folder,seed in rows:
  cmd=json.loads((folder/'command.json').read_text());assert cmd[cmd.index('--seeds')+1]==str(seed)
  ps=list((folder/'output/ledgers').glob('**/seed*.jsonl.gz'));assert len(ps)==1 and ps[0].name==f'seed{seed:03d}.jsonl.gz'
  p=ps[0];n=0;timed=0
  with gzip.open(p,'rt') as g:
   next(g)
   for line in g:
    row=json.loads(line);assert row['record_type']=='trial' and row['prediction_order']==n
    v=row.get('sec_trial');timed+=v is not None
    w.writerow({'run':name,'seed':seed,'trial':n,'sec_trial':'' if v is None else v,'status':'not_recorded' if v is None else 'measured','source':str(p)})
    n+=1
  assert n==1740
  proof.append({'run':name,'seed':seed,'trials':n,'measured_sec_trial_rows':timed,'missing_sec_trial_rows':n-timed,'source':str(p),'sha256':sha(p),'command_sha256':sha(folder/'command.json'),'model_rerun':False,'replay_classification':False,'values_not_estimated':True})
(R/'historical_sec_trial_proof.json').write_text(json.dumps({'records':proof,'passed':True},ensure_ascii=False,indent=2)+'\n')
print('既存三本の秒の有無',[(x['run'],x['measured_sec_trial_rows']) for x in proof],flush=True)
