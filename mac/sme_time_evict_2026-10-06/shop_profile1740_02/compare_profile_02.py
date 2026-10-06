"""計測で模型の記録が変わらないことを、元の一本と独立に比較する。"""
from pathlib import Path
import csv,gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parent
CASE=next(x for x in json.loads((ROOT/'profile_plan_02.json').read_text()) if x['name']==sys.argv[1])
FOLDER=Path(CASE['folder']);REFERENCE=Path(CASE['original_reference']);OUTPUT=FOLDER/'output';LIMIT=CASE['measured_trials']
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while part:=f.read(2**20):h.update(part)
 return h.hexdigest()
def opener(path):return gzip.open(path,'rb') if path.suffix=='.gz' else path.open('rb')
def trial_number(line,rel):
 if rel.suffix=='.csv':
  s=next(csv.reader([line.decode()]))
  return int(s[0]) if s and s[0].isdigit() else None
 row=json.loads(line)
 for key in ('trial','prediction_order','t'):
  if key in row and isinstance(row[key],int):return row[key]
 return None
def prefix_lines(path,rel):
 with opener(path) as f:
  if str(rel).startswith('ledgers/'):next(f)
  for i,line in enumerate(f):
   if str(rel).endswith('.csv') and i==0:yield line;continue
   try:
    row=json.loads(line) if rel.suffix!='.csv' else None
   except Exception as e:raise AssertionError((rel,i,str(e)))
   if row is not None and row.get('kind')=='final':break
   t=trial_number(line,rel)
   if t is not None and (t>LIMIT if str(rel).endswith('.probe.jsonl') else t>=LIMIT):break
   yield line

def prefix_compare(left,right,rel):
 lh=hashlib.sha256();rh=hashlib.sha256();a_count=b_count=0;a_bytes=b_bytes=0;first=None
 a=prefix_lines(left,rel);b=prefix_lines(right,rel) if right is not None else iter(())
 while True:
  la=next(a,None);lb=next(b,None)
  if la is None and lb is None:break
  # 必要なイベントが一つも無く、後の試行で初めて作られたCSVの見出しは、1000試行の欠落ではない。
  if right is None and rel.suffix=='.csv' and a_count==0 and lb is None and la is not None:
   nextline=next(a,None)
   if nextline is None:return {'equal':True,'rows':0,'reference_event_rows':0,'case_file_absent_before_first_event':True,'reference_file_sha256':sha(left)}
   raise AssertionError((str(rel),'先頭1000のCSVが無い'))
  if la is not None:lh.update(la);a_count+=1;a_bytes+=len(la)
  if lb is not None:rh.update(lb);b_count+=1;b_bytes+=len(lb)
  if la!=lb and first is None:
   first={'line':max(a_count,b_count),'reference_trial':trial_number(la,rel) if la else None,'case_trial':trial_number(lb,rel) if lb else None,'reference_line_sha256':hashlib.sha256(la).hexdigest() if la else None,'case_line_sha256':hashlib.sha256(lb).hexdigest() if lb else None}
   if rel.suffix!='.csv' and la and lb:
    ra,rb=json.loads(la),json.loads(lb);first['different_fields']=[k for k in sorted(ra.keys()|rb.keys()) if ra.get(k)!=rb.get(k)]
  if first:break
 return {'equal':first is None and lh.hexdigest()==rh.hexdigest(),'reference_lines':a_count,'case_lines':b_count,'reference_bytes':a_bytes,'case_bytes':b_bytes,'reference_prefix_sha256':lh.hexdigest(),'case_prefix_sha256':rh.hexdigest(),'first_difference':first}
if CASE['kind']=='shop':
 import compare_native_01
 result=compare_native_01.compare(REFERENCE,FOLDER)
else:
 left={p.relative_to(REFERENCE):p for pattern in ('ledgers/**/*.jsonl.gz','side/**/*','evictions/**/*.jsonl.gz') for p in REFERENCE.glob(pattern) if p.is_file()}
 right={p.relative_to(OUTPUT):p for pattern in ('ledgers/**/*.jsonl.gz','side/**/*','evictions/**/*.jsonl.gz') for p in OUTPUT.glob(pattern) if p.is_file()}
 assert not right.keys()-left.keys(),('元に無いファイル',right.keys()-left.keys())
 records=[]
 for rel in sorted(left):
  row={'file':str(rel),**prefix_compare(left[rel],right.get(rel),rel)};records.append(row)
  if not row['equal']:break
 states=next(OUTPUT.glob('side/**/*.sme.states.jsonl.gz'));state_counts={}
 with gzip.open(states,'rt') as f:
  for line in f:
   row=json.loads(line);assert 0<=row['trial']<LIMIT
   key=row['kind'];state_counts[key]=state_counts.get(key,0)+1
 assert state_counts=={'pre':1000,'prediction':1000,'post':1000},state_counts
 ledger=next(OUTPUT.glob('ledgers/**/*.jsonl.gz'))
 with gzip.open(ledger,'rt') as f:
  next(f);trial_rows=sum(1 for _ in f)
 assert trial_rows==1000,trial_rows
 result={'passed':all(r['equal'] for r in records),'records':records,'state_counts':state_counts,'ledger_trial_rows':trial_rows,'reference':str(REFERENCE),'case':str(FOLDER),'configured_trial_count':5000,'horizon':5000,'measured_trials':1000,'comparison':'gzipを展開して先頭1000の記録を行の順・文字列そのままで比較。JSONの並び替えと数値の丸めはしない。','excluded':['台帳の見出し一行','各ファイルの1000試行より後の記録','走行終了時のfinal（1000で計測を終え、5000の完了処理をしない）'],'compressed_footer_not_compared_because_prefix':True,'next_trial_not_evaluated':json.loads((FOLDER/'prefix_complete.json').read_text())['next_trial_not_evaluated']}
 (FOLDER/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 assert result['passed'],'先頭1000の記録が不一致。変更せず停止'
index=[]
for p in sorted(FOLDER.rglob('*')):
 if not p.is_file() or p.name=='all_files_sha256.csv' or any(part in ('compare_02','analyze_02') for part in p.relative_to(FOLDER).parts):continue
 index.append({'file':str(p.relative_to(FOLDER)),'bytes':p.stat().st_size,'sha256':sha(p)})
with (FOLDER/'all_files_sha256.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['file','bytes','sha256']);w.writeheader();w.writerows(index)
print(CASE['name'],'計測の記録の一致',result['passed'],flush=True)
