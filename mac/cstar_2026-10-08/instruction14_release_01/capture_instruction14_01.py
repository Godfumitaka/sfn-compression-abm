"""指示14の終了前に三本の再生記録と自分の過程を読む。模型は起動しない。"""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json,subprocess
R=Path(__file__).resolve().parent;BASE=R.parent
TARGET=R/'instruction14_before_01.json'
assert not TARGET.exists(),'前の確認を上書きしない'
assert (R/'instruction14_received_01.json').exists()
raw=subprocess.check_output(['ps','-axo','pid=,ppid=,stat=,rss=,lstart=,command='],text=True)
rows={}
for line in raw.splitlines():
 s=line.strip().split(None,9)
 if len(s)==10:
  rows[int(s[0])]=dict(pid=int(s[0]),ppid=int(s[1]),stat=s[2],rss_kib=int(s[3]),start=' '.join(s[4:9]),command=s[9])
registry=Path('/Users/tatsu-admin/jobs/registry.tsv').read_text()
records=[]
for seed,claim in ((17,20806),(18,20915),(19,27521)):
 case=BASE/'codex_logp_main_2026-10-06/runs/w2_A_L50'/f'seed{seed:03d}'
 assert str(case) in rows[claim]['command'] and 'jobs.py run' in rows[claim]['command'] and ' analysis' in rows[claim]['command']
 tree={claim}
 while True:
  kids={p for p,r in rows.items() if r['ppid'] in tree}
  if kids<=tree:break
  tree|=kids
 replay=[r for p,r in rows.items() if p in tree and 'tools/selcands_sme.py' in r['command']]
 assert len(replay)==1 and 'T' in replay[0]['stat']
 files=[dict(path=str(p.relative_to(case)),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in case.rglob('*') if p.is_file() and p.parts[len(case.parts)] in ('analysis_job','analysis_output')]
 p=next((case/'analysis_output/side').rglob('*.sme.candidates.jsonl.gz'))
 count=0;first=None;last=None;maximum=None;read_error=None
 try:
  with gzip.open(p,'rt',encoding='utf-8') as f:
   for line in f:
    if not line.endswith('\n'):read_error='末尾の未完の行';break
    try:v=json.loads(line)
    except json.JSONDecodeError as e:read_error=type(e).__name__;break
    trial=v['trial'];first=trial if first is None else first;last=trial;maximum=trial if maximum is None else max(maximum,trial);count+=1
 except (EOFError,gzip.BadGzipFile,OSError) as e:read_error=type(e).__name__+': '+str(e)
 records.append(dict(seed=seed,claim_pid=claim,replay_pid=replay[0]['pid'],process_tree=[rows[p] for p in sorted(tree)],candidate_path=str(p),complete_written_candidate_rows=count,first_trial=first,last_complete_written_trial=last,maximum_complete_written_trial=maximum,read_error=read_error,progress_is_lower_bound=True,buffered_or_in_progress_trial_unknown=True,files=files))
result=dict(at=datetime.now().astimezone().isoformat(),instruction=14,registry_before=registry,registry_before_sha256=hashlib.sha256(registry.encode()).hexdigest(),records=records,production_stopped=False,files_deleted=False)
TARGET.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'}|{'records':[{k:v for k,v in r.items() if k not in ('process_tree','files')} for r in records]},ensure_ascii=False))
