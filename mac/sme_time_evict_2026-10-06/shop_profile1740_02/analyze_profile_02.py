"""二本の計測の秒とファイルの大きさを、100試行と種類ごとに数える。"""
from pathlib import Path
from collections import defaultdict
import csv,hashlib,json,pstats,sys
ROOT=Path(__file__).resolve().parent
CASE=next(x for x in json.loads((ROOT/'profile_plan_02.json').read_text()) if x['name']==sys.argv[1]);FOLDER=Path(CASE['folder'])
CATEGORIES=('engine','preparation','retention','prediction','nonlearning_tests','writing','garbage_collection','other')
def summarize(rows):
 seconds={k:sum(x[k] for x in rows) for k in CATEGORIES};total=sum(seconds.values())
 return {'first_trial':rows[0]['trial'],'last_trial':rows[-1]['trial'],'trials':len(rows),'seconds':seconds,'fraction':{k:v/total if total else None for k,v in seconds.items()},'accounted_seconds':total,'sec_trial_sum':sum(r['sec_trial'] for r in rows),'process_cpu_seconds':sum(r['process_cpu_seconds'] for r in rows),'trace_callback_seconds':sum(r['trace_callback_seconds'] for r in rows),'max_rss_bytes':max(r['rss_max_bytes'] for r in rows)}
def profile_rows(paths):
 stats=pstats.Stats(str(paths[0]))
 if len(paths)>1:stats.add(*(str(p) for p in paths[1:]))
 rows=[{'file':k[0],'line':k[1],'function':k[2],'primitive_calls':v[0],'calls':v[1],'self_seconds':v[2],'cumulative_seconds':v[3]} for k,v in stats.stats.items()]
 return {'self_top40':sorted(rows,key=lambda x:x['self_seconds'],reverse=True)[:40],'cumulative_top40':sorted(rows,key=lambda x:x['cumulative_seconds'],reverse=True)[:40],'total_self_seconds':stats.total_tt,'note':'自身の秒は重ならない。累積秒は入れ子で重なる。'}
def type_name(rel):
 if rel.parts[0]=='ledgers':return '台帳 gzip'
 if rel.parts[0]=='side':
  name=rel.name
  for suffix,label in (('.sme.states.jsonl.gz','side 保存状態 gzip'),('.sme.diagnostics.jsonl.gz','side 試験の照合 gzip'),('.sme.jsonl.gz','side 本体の照合 gzip'),('.probe.jsonl','side 学習しない試験 jsonl'),('.answers.csv','side 答え csv'),('.ambig.csv','side 同点 csv'),('.routing.jsonl','side 届け先 jsonl'),('.jsonl','side その他 jsonl')):
   if name.endswith(suffix):return label
  return 'side その他'
 if rel.parts[0]=='evictions':return '捨てた鍵'
 if rel.parts[0]=='timing':return '既存の実測秒'
 return 'native管理ファイル'
data=json.loads((FOLDER/'timing_complete.json').read_text());rows=data['rows'];limit=CASE['measured_trials']
assert len(rows)==limit and [r['trial'] for r in rows]==list(range(limit))
assert json.loads((FOLDER/'comparison.json').read_text())['passed']
bins=[summarize(rows[i:i+100]) for i in range(0,limit,100)]
fields=['first_trial','last_trial','trials','sec_trial_sum','process_cpu_seconds','accounted_seconds','trace_callback_seconds','max_rss_bytes',*CATEGORIES]
with (FOLDER/'time_100_trials.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for row in bins:w.writerow({k:row[k] for k in fields if k not in CATEGORIES}|row['seconds'])
groups=defaultdict(lambda:{'files':0,'bytes':0});files=[]
for p in sorted((FOLDER/'output').rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(FOLDER/'output');kind=type_name(rel);size=p.stat().st_size
 groups[kind]['files']+=1;groups[kind]['bytes']+=size
 files.append({'file':str(rel),'type':kind,'bytes':size})
total=sum(v['bytes'] for v in groups.values());side=sum(v['bytes'] for k,v in groups.items() if k.startswith('side '))
with (FOLDER/'output_sizes.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['file','type','bytes']);w.writeheader();w.writerows(files)
profiles=sorted(FOLDER.glob('trials_*.prof'));assert len(profiles)==(limit+99)//100
late=[p for p in profiles if p.stem.startswith('trials_1500_')] if limit>=1600 else profiles[-2:]
result={'passed':True,'case':CASE,'method':data['method'],'boundary':data['boundary'],'all':summarize(rows),'bins':bins,'last_200':summarize(rows[-200:]),'late_1500_1599':summarize(rows[1500:1600]) if limit>=1600 else None,'whole_profile':profile_rows(profiles),'late_profile':profile_rows(late),'run':json.loads((FOLDER/'run_complete.json').read_text()),'comparison':json.loads((FOLDER/'comparison.json').read_text()),'output_sizes':dict(groups),'output_total_bytes':total,'output_side_bytes':side,'output_side_fraction':side/total,'profiling_overhead_note':'内訳はCPU秒。traceのcallback自身を分母から除く。cProfileの負荷は含む。CPUの空き待ち・一時停止・I/O待ちは実時間とCPU秒の差へ含む。非計測の速度倍率とはしない。','test_category_note':'probeworld._probe以下の全体を学習しない試験へ入れる（照合・写し・復元・その試験の書き出しを含む）。他の七区分と重ねない。','category_function_file':str(ROOT/'observe_02.py')}
(FOLDER/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(CASE['name'],'内訳の集計',limit,'試行',flush=True)
