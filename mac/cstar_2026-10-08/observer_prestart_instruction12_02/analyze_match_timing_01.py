"""全バイトの関門の後、指示10・11の個別時間を集計する。"""
from pathlib import Path
from collections import defaultdict
from math import ceil
import csv, json

HERE=Path(__file__).resolve().parent
ROOT=HERE/'match_times_instruction10_01'
CASE=ROOT/'full1740_01'
assert json.loads((ROOT/'complete.json').read_text())['passed']
assert json.loads((CASE/'comparison.json').read_text())['passed']
assert not (CASE/'analysis.json').exists(),'集計も二重に行わない'
obs=json.loads((CASE/'observations_complete.json').read_text())
defs=[];pipeline=defaultdict(lambda:dict(calls=0,cpu_seconds=0.));core=defaultdict(lambda:dict(calls=0,cpu_seconds=0.))
bytrial=defaultdict(lambda:dict(prediction_definitions=0,definition_cpu_seconds=0.,pipeline_cpu_seconds=0.,core_cpu_seconds=0.))
prediction_counts={}
with (CASE/'match_times.jsonl').open() as stream:
 for line in stream:
  x=json.loads(line);i=x['trial_index'];kind=x['kind']
  if kind=='definition_mapping' and x['prediction']:
   defs.append(x['inclusive_cpu_seconds'])
   bytrial[i]['prediction_definitions']+=1
   bytrial[i]['definition_cpu_seconds']+=x['inclusive_cpu_seconds']
  elif kind=='matching_pipeline_call':
   p=pipeline[x['caller']];p['calls']+=1;p['cpu_seconds']+=x['inclusive_cpu_seconds']
   bytrial[i]['pipeline_cpu_seconds']+=x['inclusive_cpu_seconds']
  elif kind=='cstar_matcher_call':
   p=core[x['caller']];p['calls']+=1;p['cpu_seconds']+=x['cpu_seconds']
   bytrial[i]['core_cpu_seconds']+=x['cpu_seconds']
  elif kind=='prediction_counts':
   assert i not in prediction_counts
   prediction_counts[i]=x
assert len(prediction_counts)==1740
counts=list(csv.DictReader((HERE/'instruction10_counts_by_trial_01.csv').open()))
assert len(counts)==1740
for row in counts:
 i=int(row['trial_index'])
 assert bytrial[i]['prediction_definitions']==int(row['cstar_matched_definitions']),('定義の照合数の観測不一致',i)
 assert prediction_counts[i]['memory_definitions']==int(row['memory_definitions'])
 assert prediction_counts[i]['gate_passed_definitions']==int(row['gate_passed_definitions'])
assert len(defs)==40878
ordered=sorted(defs);heavy=ordered[-ceil(len(ordered)*.1):]
process_cpu=obs['process_cpu_seconds'];cpu=process_cpu-obs['observer_cpu']
pipeline_cpu=sum(x['cpu_seconds'] for x in pipeline.values());core_cpu=sum(x['cpu_seconds'] for x in core.values())
assert cpu>0 and pipeline_cpu<=cpu+1e-3
for table in (pipeline,core):
 total=sum(x['cpu_seconds'] for x in table.values())
 for x in table.values():
  x['mean_cpu_seconds']=x['cpu_seconds']/x['calls']
  x['fraction_of_matching_cpu']=x['cpu_seconds']/total if total else 0.
  x['fraction_of_model_cpu']=x['cpu_seconds']/cpu
with (CASE/'time_by_trial.csv').open('x',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=['trial_index','trial_number','prediction_definitions','definition_cpu_seconds','pipeline_cpu_seconds','core_cpu_seconds'])
 writer.writeheader()
 for i in range(1740):writer.writerow(dict(trial_index=i,trial_number=i+1,**bytrial[i]))
result=dict(passed=True,source='7774b60',material_choice=2,configured_trials=1740,
    model_bytes_identical=True,definition_prediction_calls=len(defs),
    definition_mean_cpu_seconds=sum(defs)/len(defs),definition_p90_cpu_seconds=ordered[ceil(len(ordered)*.9)-1],
    definition_heavy_top10_percent_calls=len(heavy),definition_heavy_top10_percent_mean_cpu_seconds=sum(heavy)/len(heavy),
    model_cpu_seconds=cpu,observed_process_cpu_seconds=process_cpu,observer_cpu_seconds=obs['observer_cpu'],
    pipeline_cpu_seconds=pipeline_cpu,core_cpu_seconds=core_cpu,
    outside_matching_pipeline_fraction=(cpu-pipeline_cpu)/cpu,outside_matcher_core_fraction=(cpu-core_cpu)/cpu,
    matching_pipeline_callers=dict(pipeline),matcher_core_callers=dict(core),
    quantile='一回の観測を等重みとし、p90は昇順のceil(0.9*n)番目。重い10%は大きいceil(0.1*n)件。',
    measurement=obs['timing'],run=json.loads((CASE/'finished.json').read_text()),
    note='図の作成を含む定義のmap_v39、配管のsmeshared.map_graphs、CstarMatcher.matchは入れ子。秒を足さない。配管には分布・控え・旧照合の診断・照合記録の書き出しを含む。模型のCPU秒から観測の書き出し・付加記録の計測済み負荷を除く。time関数の入口などの微小な観測負荷は残る。速度の倍率の測定とは別。')
(CASE/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('passed','definition_prediction_calls','definition_mean_cpu_seconds','definition_p90_cpu_seconds','outside_matching_pipeline_fraction')},ensure_ascii=False))
