"""保存済み時間の算術換算のみ。模型開始なし。"""
from pathlib import Path
from datetime import datetime
import json,hashlib,math,resource,time
H=Path(__file__).resolve().parent
T=H.parent
W=T.parent
start=time.perf_counter()
files=[H/'existing_times_analysis_02.json',T/'instruction9/D_q/status.json',T/'instruction9/D_attention/status.json']
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):digest(p) for p in files}
x=json.loads(files[0].read_text())
assert x['input_unchanged'] and x['new_model_starts']==0
out={'at_jst':datetime.now().astimezone().isoformat(),'new_model_starts':0,'projections':{},'schedule_assumptions':{'start_jst':'2026-10-11T09:00:00+09:00','deadlines_jst':['2026-10-12T09:00:00+09:00','2026-10-13T09:00:00+09:00'],'hours':[24,48],'available_hosts':1,'cpu_per_host':8,'one_eight_agent_group_per_host':True,'gates_and_receipt_required':True,'admission_gate_preparation_seconds':'未測定、控除していない','number_of_free_eligible_hosts':'未測定','eta':'同時に八体を動かした際の一体あたり速度/一体のみの速度。未測定。同期・通信・I/Oの増分は別。','full_window':'1740','draft_price_B':'{L50_ref} unresolved','selected_seeds':None},'human_D_reference_only':{},'counts_sensitivity_only':{}}
for key,c in x['cases'].items():
 if c['records']!=200: continue
 a,b=(v['elapsed_delta'] for v in c['blocks'])
 model=c['status']['model_seconds']
 tail=model-c['last']['elapsed_seconds']
 # 17 full hundred-blocks + .4 of the eighteenth; slopes b-a.
 linear_blocks=17*a+(17*16/2)*(b-a)+.4*(a+17*(b-a))+tail
 out['projections'][key]={'observed_model_hours':model/3600,'first100_hours':a/3600,'second100_hours':b/3600,'second_over_first':b/a,'observed_last_snapshot_tail_seconds':tail,'constant_200_average_full_hours':model*8.7/3600,'constant_second100_after_200_full_hours':(model+15.4*b)/3600,'linear_100_block_growth_full_hours':linear_blocks/3600,'quadratic_cumulative_stress_hours':model*8.7**2/3600,'formula_linear':'17.4*a+142.8*(b-a)+observed_tail','checkpoint_trial100_seconds':c['blocks'][0]['checkpoint_seconds_including_trial'],'checkpoint_trial200_seconds':c['blocks'][1]['checkpoint_seconds_including_trial'],'probe_only_seconds':'未測定：上記は実試行と試験を合わせた値','actual_8_agent_1740':'未測定','source_root':c['root']}
for path in files[1:]:
 s=json.loads(path.read_text()); sec=s['model_seconds']
 out['human_D_reference_only'][path.parent.name]={'model_seconds_200':sec,'constant_average_1740_seconds':sec*8.7,'quadratic_stress_1740_seconds':sec*8.7**2,'collective_8_agent_prediction':None,'reason':'旧お店一体f0.5、通信なしのD診断。新版八体f0.1/f0.9 q0.2 m0.1の実測へ代用しない。'}
# rounded planning assumptions deliberately wider than the exact local arithmetic;
# not measured speedups or bounds; communication and efficiency penalties NOT included.
for name,fast,slow in [('full_current_assumed',40,120),('full_if_measured_speed2',20,60),('full_if_measured_speed4_2',40/4.2,120/4.2),('prefix200_eta1',16659.087912125047/3600,19128.811994708027/3600),('prefix200_eta0_5',2*16659.087912125047/3600,2*19128.811994708027/3600)]:
 out['counts_sensitivity_only'][name]={'hours_fast':fast,'hours_slow':slow,'by_deadline':[{'available_hours':h,'completed_slow':math.floor(h/slow),'completed_fast':math.floor(h/fast)} for h in (24,48)],'conditions':'関門と取得が完了し10/11 09:00開始、八体CPU8専有の一台。準備/受付待ち/新たな通信費用を未控除。速度倍率とetaは未測定、保証しない。'}
out['human_actual_collective_counts_by_deadline']='未測定'
out['fewer_runs_option']={'original_total':20,'hypothetical_total':6,'each_family_runs':3,'changes_first_run_duration':False,'relative_total_work_if_same_mixture':.3,'seed_and_f_allocation':'Astra判断待ち。選択・命令変更なし。'}
out['input_sha256']=before
out['input_unchanged']=before=={str(p):digest(p) for p in files}
out['seconds']=time.perf_counter()-start
out['max_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(H/'estimate_cases_01.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert out['input_unchanged']
print(json.dumps({'input_unchanged':out['input_unchanged'],'new_model_starts':0,'seconds':out['seconds'],'max_rss_bytes':out['max_rss_bytes']}))
