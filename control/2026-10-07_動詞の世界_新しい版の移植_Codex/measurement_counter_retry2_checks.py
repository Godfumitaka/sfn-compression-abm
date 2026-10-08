"""実際の動詞台帳入口と測定入口を確認。学習模型は起動しない。"""
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace
import copy, hashlib, importlib.util, json, os, runpy, sys
root=Path(__file__).resolve().parent
out=root/'measurement_counter_retry2_checks/output'
assert not out.exists(), '同じ検査の出力を重ねない'
out.mkdir(parents=True)
source=root/'source'
sys.path[:0]=[str(source/'tools'),str(source)]
spec=importlib.util.spec_from_file_location('measurement_observer',root/'measurement_driver_retry2.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import abm.ledger as ledger, verbworld, verbtiming, sweep, v3_run
checks=[]
def check(name, condition):
    assert condition,name
    checks.append(name)
# 実際の動詞入口では、研究者の追加欄がある行は前のappendを呼ばない。
old_append=ledger.Ledger.append
before_count=[0]
def old_counter(self,row):
    before_count[0]+=1
    return old_append(self,row)
ledger.Ledger.append=old_counter
verbworld.install()
verbtiming.install(out/'native_timing.jsonl')
installed=ledger.Ledger.append
header=SimpleNamespace(to_dict=lambda:{'trial_count':5000,'world_hash':'fixture'})
records=[]
for i in range(100):
    row=ledger.empty_record()
    for key in ledger.NON_NULL_FIELDS:row[key]=0
    row['prediction_order']=i
    row.update({key:False for key in verbworld.EXTRA_KEYS})
    records.append(row)
original_records=copy.deepcopy(records)
base=out/'baseline.jsonl';candidate=out/'observed.jsonl'
with ledger.Ledger(base,header) as stream:
    for row in records:stream.append(row)
check('old_counter_bypassed_by_actual_verb_entry',before_count[0]==0)
seen=[]
with ledger.Ledger(candidate,header) as stream:
    with mod.observe_written_rows(stream,lambda row:seen.append(row['prediction_order'])):
        for row in records:stream.append(row)
    check('restored_instance_method_after_success','append' not in vars(stream))
check('final_installed_class_method_unchanged',ledger.Ledger.append is installed)
check('each_written_row_counted_once',seen==list(range(100)))
check('actual_verb_ledger_full_bytes_equal',base.read_bytes()==candidate.read_bytes())
check('records_not_mutated',records==original_records)
verbtiming.close()
# 記録失敗時には完了数を増やさず、元の個体の入口を復元する。
called=[]
class Failing:
    def append(self,row):raise ValueError('fixture')
f=Failing();previous=lambda row:(_ for _ in ()).throw(ValueError('fixture'))
f.append=previous
try:
    with mod.observe_written_rows(f,lambda row:called.append(row)):
        f.append({})
except ValueError:pass
else:raise AssertionError('error must propagate')
check('native_error_propagates_and_not_counted',not called)
check('previous_instance_entry_restored_on_error',f.append is previous)
# 実際の測定worker入口を、世界5000を保つ非模型のfixtureで100/300ずつ確認。
@dataclass
class Result:
    trial_count:int
native_worker=v3_run.worker;native_long=sweep.run_longitudinal
for limit in (100,300):
    folder=out/str(limit);folder.mkdir()
    world=SimpleNamespace(trials=list(range(5000)),world_hash='fixture')
    fixture_events=[]
    class FinalLedger:
        def append(self,row):raise AssertionError('install before loop')
    def fake_long(world,states,configs,stream,**kwargs):
        assert len(world.trials)==5000 and world.world_hash=='fixture'
        for i in world.trials:stream.append({'prediction_order':i})
        return Result(trial_count=len(world.trials))
    def fake_worker(task):
        # 元のworkerが後から入口を置く順序を再現する。
        def append(self,row):fixture_events.append(row['prediction_order'])
        FinalLedger.append=append
        result=sweep.run_longitudinal(world,{}, {},FinalLedger())
        return {'trial_count':result.trial_count}
    sweep.run_longitudinal=fake_long;v3_run.worker=fake_worker
    os.environ['VERB_MEASUREMENT_SOURCE']=str(source)
    os.environ['VERB_MEASUREMENT_LIMIT']=str(limit)
    namespace=runpy.run_path(str(root/'measurement_driver_retry2.py'),run_name='__mp_main__')
    task={'cfg':{'trial_count':5000,'agent_ids':['agent']},'seed':1,'out_root':str(folder)}
    record=namespace['measurement_worker'](task)
    check(f'worker_prefix_{limit}_only',fixture_events==list(range(limit)))
    check(f'worker_completion_{limit}_and_horizon_5000',record['completed_trials']==limit and record['configured_trial_count']==record['horizon']==5000 and not record['full_5000_completed'])
    checkpoints=[json.loads(l) for l in (folder/'measurement/checkpoints.jsonl').read_text().splitlines()]
    check(f'worker_checkpoints_{limit}',[x['completed_trials'] for x in checkpoints]==list(range(100,limit+1,100)))
    check(f'world_{limit}_unchanged',world.trials==list(range(5000)) and world.world_hash=='fixture')
    sweep.run_longitudinal=native_long;v3_run.worker=native_worker
result={'passed':True,'learning_models_started':0,'checks':checks,'check_count':len(checks),'ledger_content_bytes':base.stat().st_size,'ledger_content_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'source_commit':'40e87b2e1fbd8348141dd447ac49c3aaadd7d914'}
(out/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
