"""計測と全バイトの関門の後、CPU秒・100試行の表・出力量を集計する。"""
from pathlib import Path
from collections import defaultdict
import csv,json,pstats
ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'profile1740_01'
CATEGORIES=('cstar_generation','cstar_expectation','birth_scoring','engine','preparation','retention','prediction','reference_match','nonlearning_tests','writing','garbage_collection','other')
assert json.loads((ROOT/'complete.json').read_text())['passed'],'全長の関門が先'
assert json.loads((FOLDER/'comparison.json').read_text())['passed']
assert not (FOLDER/'analysis.json').exists(),'集計を二重に作らない'
data=json.loads((FOLDER/'timing_complete.json').read_text());rows=data['rows']
assert [r['trial'] for r in rows]==list(range(300))+list(range(1400,1600))
def summarize(block):
 seconds={k:sum(r[k] for r in block) for k in CATEGORIES};total=sum(seconds.values())
 return dict(first_trial=block[0]['trial'],last_trial=block[-1]['trial'],trials=len(block),seconds=seconds,
  fraction={k:v/total if total else None for k,v in seconds.items()},accounted_seconds=total,
  sec_trial_sum=sum(r['sec_trial'] for r in block),process_cpu_seconds=sum(r['process_cpu_seconds'] for r in block),
  trace_callback_seconds=sum(r['trace_callback_seconds'] for r in block),max_rss_bytes=max(r['rss_max_bytes'] for r in block),
  root_calls={k:sum(r['root_calls'].get(k,0) for r in block) for k in CATEGORIES})
def prof_summary(paths):
 stats=pstats.Stats(str(paths[0]))
 if len(paths)>1:stats.add(*(str(p) for p in paths[1:]))
 functions=[dict(file=k[0],line=k[1],function=k[2],primitive_calls=v[0],calls=v[1],self_seconds=v[2],cumulative_seconds=v[3]) for k,v in stats.stats.items()]
 pipeline=[]
 for key,value in stats.stats.items():
  if Path(key[0]).name=='smeshared.py' and key[2]=='map_graphs':
   total=value[3]
   for caller,times in value[4].items():
    pipeline.append(dict(caller=Path(caller[0]).stem+':'+caller[2],calls=times[1],
        cumulative_cpu_seconds=times[3],fraction_of_profiled_pipeline=times[3]/total if total else None))
 return dict(self_top50=sorted(functions,key=lambda x:x['self_seconds'],reverse=True)[:50],
  cumulative_top50=sorted(functions,key=lambda x:x['cumulative_seconds'],reverse=True)[:50],
  total_self_seconds=stats.total_tt,matching_pipeline_callers=pipeline,
  note='自身の秒は重ならない。累積秒は入れ子で重なる。cProfileの累積秒には同時に動くtraceの負荷も含まれるため、callbackを除いた区分別CPU秒とは混ぜない。呼び出し元の割合はsmeshared.map_graphs内だけを分母にする。')
def type_name(rel):
 if rel.parts[0]=='ledgers':return '台帳 gzip' if rel.name.endswith('.gz') else '台帳の完了印'
 if rel.parts[0]=='side':
  for suffix,label in (('.sme.states.jsonl.gz','side 保存状態 gzip'),('.sme.jsonl.gz','side 照合 gzip'),('.answers.csv','side 答え csv'),('.routing.jsonl','side 届け先 jsonl'),('.shop.jsonl','side お店 jsonl'),('.jsonl.gz','side その他 gzip'),('.jsonl','side その他 jsonl')):
   if rel.name.endswith(suffix):return label
  return 'side その他'
 if rel.parts[0]=='evictions':return '捨てた鍵'
 return '管理ファイル'
bins=[summarize(rows[i:i+100]) for i in range(0,500,100)]
fields=['first_trial','last_trial','trials','sec_trial_sum','process_cpu_seconds','accounted_seconds','trace_callback_seconds','max_rss_bytes',*CATEGORIES]
with (FOLDER/'time_100_trials.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for b in bins:w.writerow({k:b[k] for k in fields if k not in CATEGORIES}|b['seconds'])
groups=defaultdict(lambda:dict(files=0,bytes=0));files=[]
for p in sorted((FOLDER/'output').rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(FOLDER/'output');kind=type_name(rel);size=p.stat().st_size
 groups[kind]['files']+=1;groups[kind]['bytes']+=size;files.append(dict(file=str(rel),type=kind,bytes=size))
with (FOLDER/'output_sizes.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['file','type','bytes']);w.writeheader();w.writerows(files)
profiles=sorted(FOLDER.glob('trials_*.prof'));assert len(profiles)==5
guard_path=ROOT/'guard_instruction11_complete.json'
guard=json.loads(guard_path.read_text()) if guard_path.exists() else None
resource_rows=[json.loads(line) for line in (FOLDER/'resources.jsonl').open()]
last_legacy_held=resource_rows[-1]['held'] if resource_rows else None
result=dict(passed=True,source='7774b60',material_choice=2,configured_trials=1740,measured_trials=500,
 method=data['method'],boundary=data['boundary'],all_selected=summarize(rows),early_300=summarize(rows[:300]),
 late_200=summarize(rows[300:]),bins=bins,selected_profile=prof_summary(profiles),
 early_profile=prof_summary(profiles[:3]),late_profile=prof_summary(profiles[3:]),
 run=json.loads((FOLDER/'finished.json').read_text()),comparison=json.loads((FOLDER/'comparison.json').read_text()),
 instruction11_guard=guard,last_legacy_controller_held=last_legacy_held,
 legacy_pause_note='旧監督のpaused_secondsは論理上の保留で、補助監督の再開中を含みうる。最後の未清算の保留は含まないため、実際の停止秒の上限と断定しない。実際のT状態の2秒標本を別記。',
 external_model_count_range=[min(x['external_model_count'] for x in resource_rows),max(x['external_model_count'] for x in resource_rows)],
 output_sizes=dict(groups),output_total_bytes=sum(v['bytes'] for v in groups.values()),
 native_reference=json.loads((ROOT.parent/'codex_cstar_2026-10-07/native_full_01/on_own.json').read_text()),
 category_note='旧版の照合の比較記録は今回のコードではfixorder2.map_graphsを経由し、準備の区分に含む。reference_matchの区分はabm.sme.map_graphsだけを別計上するため0になりうる。旧照合が無いという意味ではない。直接の累積秒は上位関数とprofで確認する。',
 note='CPU内訳は500試行だけ。途中の1100試行と末尾140試行は計測外。CPU秒からtrace callbackを除くがcProfileの負荷は含む。全長の実時間は別の列で、速度倍率に使わない。分類は排他的。誕生の採点と学習しない試験の内側は、その区分を保つ。')
(FOLDER/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=True,measured_trials=500,early_cpu=result['early_300']['accounted_seconds'],late_cpu=result['late_200']['accounted_seconds']),ensure_ascii=False))
