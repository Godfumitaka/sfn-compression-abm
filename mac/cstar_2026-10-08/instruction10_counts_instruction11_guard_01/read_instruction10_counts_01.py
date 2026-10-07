"""保存済み種1の定義数と門の数だけを読む。成績・答えの値を集計しない。"""
from pathlib import Path
from collections import defaultdict
import csv,gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'codex_cstar_2026-10-07/native_full_01/on_own/output'
sys.path.insert(0,str(ROOT.parent/'codex_logp_main_2026-10-06'))
from common_01 import conditions,now,save
OUT=ROOT/'instruction10_counts_01.json'
assert not OUT.exists(),'集計を重複して作らない'
assert json.loads((BASE.parent/'complete.json').read_text())['passed'] if (BASE.parent/'complete.json').exists() else json.loads((BASE.parent.parent/'complete.json').read_text())['passed']
safe=conditions();assert safe['free_bytes']>=20*2**30 and not safe['swap_grew'] and not safe['thermal_warning']
def fields(value):
 assert value['tag']=='mapping'
 return dict(value['items'])
def guard():
 safe=conditions()
 if safe['free_bytes']<18.5*2**30 or safe['swap_grew'] or safe['thermal_warning']:
  save(ROOT/'instruction10_counts_STOP.json',dict(at=now(),resources=safe))
  raise RuntimeError('読み取りの資源条件で停止')
state_path=next((BASE/'side').rglob('seed001.sme.states.jsonl.gz'))
match_path=next((BASE/'side').rglob('seed001.sme.jsonl.gz'))
rows={}
with gzip.open(state_path,'rt') as f:
 for line in f:
  r=json.loads(line);t=r['trial']
  if r['kind']=='pre':
   definitions=r['state']['fields']['definitions'];assert definitions['tag']=='mapping'
   rows[t]=dict(trial_index=t,trial_number=t+1,memory_definitions=len(definitions['items']),gate_passed_definitions=None)
  elif r['kind']=='prediction':
   trace=fields(r['output']['fields']['trace'])
   passed=trace['tau_passed_defs'];assert passed['tag']=='list'
   rows[t]['gate_passed_definitions']=len(passed['items'])
  if r['kind']=='post' and t%100==99:guard()
assert set(rows)==set(range(1740)) and all(r['gate_passed_definitions'] is not None for r in rows.values())
result_trials={};actual=defaultdict(set);references=defaultdict(int)
with gzip.open(match_path,'rt') as f:
 for n,line in enumerate(f,1):
  r=json.loads(line)
  if r.get('kind')=='sme_result' and r.get('version')=='sme-cstar-expectation-1':result_trials[r['result']]=r['trial']
  elif r.get('kind')=='sme_n3' and r.get('version')=='sme-cstar-expectation-1':
   t=result_trials[r['result']];actual[t].add(r['R']);references[t]+=1
  if n%10000==0:guard()
for t,r in rows.items():
 r.update(cstar_matched_definitions=len(actual[t]),prediction_n3_records=references[t])
 assert r['cstar_matched_definitions']<=r['memory_definitions']
 assert r['gate_passed_definitions']<=r['cstar_matched_definitions']
ordered=[rows[t] for t in range(1740)]
keys=('memory_definitions','cstar_matched_definitions','gate_passed_definitions','prediction_n3_records')
def summary(values):return dict(first_trial=values[0]['trial_number'],last_trial=values[-1]['trial_number'],trials=len(values),total={k:sum(r[k] for r in values) for k in keys},mean={k:sum(r[k] for r in values)/len(values) for k in keys})
with (ROOT/'instruction10_counts_by_trial_01.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(ordered[0]));w.writeheader();w.writerows(ordered)
hashes={}
for p in (state_path,match_path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while block:=f.read(2**20):h.update(block)
 hashes[str(p)]=h.hexdigest()
 guard()
save(OUT,dict(at=now(),passed=True,model_not_run=True,performance_not_read=True,source_commit='7774b60',source_sha256=hashes,
 all_trials=summary(ordered),late_from_trial_number_1400=summary(ordered[1399:]),late_from_trial_index_1400=summary(ordered[1400:]),
 by_100_trials=[summary(ordered[i:i+100]) for i in range(0,1740,100)],
 definition='memory_definitionsは予測前の保存状態の定義の数。cstar_matched_definitionsは予測のN3候補の記録に出た異なるRの数。gate_passed_definitionsは予測のtrace.tau_passed_defsの数。対応の上位3の本数とは区別する。閾値を通らず選びを行わない試行は照合数・門の数が0になる。後半の主表は1始まりの試行1400〜1740（341試行）、0始まりの1400〜1739（340試行）も別表で示す。成績・誕生の正解を集計しない。'))
print(json.dumps(dict(passed=True,all=summary(ordered),late=summary(ordered[1399:])),ensure_ascii=False))
