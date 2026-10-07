"""外付けのcProfileと呼び出しのtraceで、模型の関数を置き換えず時間を分ける。"""
from collections import Counter
from pathlib import Path
import cProfile
import csv
import gc
import io
import json
import os
import resource
import sys
import time

SOURCE=Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import v3_run
REAL_WORKER=v3_run.worker
LIMIT=int(os.environ.get('SME_PROFILE_TRIAL_LIMIT','1740'))
RANGES=json.loads(os.environ.get('SME_PROFILE_TRIAL_RANGES', '[[0,1740]]'))
PROFILE_TRIALS=[i for begin,end in RANGES for i in range(begin,min(end,LIMIT))]
assert len(PROFILE_TRIALS)==len(set(PROFILE_TRIALS)) and PROFILE_TRIALS==sorted(PROFILE_TRIALS)
class PrefixComplete(Exception):
    pass


class Meter:
    """同じ範囲を二重に足さず、入口の種類を内側の入口で上書きして数える。"""
    categories=('cstar_generation','cstar_expectation','birth_scoring','engine','preparation','retention','prediction','reference_match','nonlearning_tests','writing','other')

    def __init__(self,root,input_code):
        self.root=root
        self.input_code=input_code
        self.code_roots={}
        self.stack=[]
        self.trial=None
        self.active=False
        self.last=None
        self.seconds=Counter()
        self.calls=Counter()
        self.gc_seconds=Counter()
        self.gc_start=None
        self.in_trace=False
        self.aux_seconds=0.0
        self.block=[]
        self.all_rows=[]
        self.profiler=None
        self.csv_stream=(root/'sec_trial.csv').open('x',newline='')
        self.writer=csv.DictWriter(self.csv_stream,fieldnames=['trial','sec_trial','process_cpu_seconds','accounted_seconds',
            *self.categories,'garbage_collection','trace_callback_seconds','rss_max_bytes'])
        self.writer.writeheader()

    def root_category(self,code):
        at=id(code)
        if at in self.code_roots:
            return self.code_roots[at][1]
        filename,name=code.co_filename,code.co_name
        leaf=Path(filename).stem
        category=None
        if leaf=='cstar_matcher':
            if name in ('_grow','_add'):category='cstar_generation'
            elif name in ('_scores','_probability'):category='cstar_expectation'
            elif name in ('run','validate'):category='engine'
            elif name in ('match','match_key','self_score','snapshot','restore','probability_key'):category='preparation'
        elif leaf=='cstar_score':
            category='engine' if name=='_checked_mapping' else 'cstar_expectation'
        elif leaf=='cstar_runtime':
            if name=='initialize':category='birth_scoring'
            elif name in ('probabilities_for_graph','distributions','snapshot','restore'):category='preparation'
            elif name=='support':category='prediction'
        elif leaf=='cstar_probability':
            category='preparation'
        elif leaf=='sme' and name=='map_graphs':
            category='reference_match'
        elif leaf=='sme2017':
            if name=='run':category='engine'
            elif name in ('_key','_canonical','match','match_key','self_score','snapshot','restore','fingerprint'):
                category='preparation'
        elif leaf=='smeintern':
            category='engine' if name=='run' else 'preparation'
        elif leaf=='smeshared':
            if name in ('_log','close'):category='writing'
            elif name in ('typed_graph','graph_data','freeze','canonical_identity','structural_key',
                         'call_seed','_match_seed','_old_on_new','snapshot','restore','map_graphs'):
                category='preparation'
            elif name in ('_definition_choice','choose_trace','select_definition'):category='prediction'
        elif leaf=='probeworld' and name=='_probe':
            category='nonlearning_tests'
        elif leaf=='smeevict':
            category='preparation'
        elif leaf=='v39':
            if name=='v39_graph':category='preparation'
            elif name in ('predict','predict_wrapped','select_definition','fill_v39','fill_decision',
                         'h_answer','u_answer','three_answers','amb_blocks'):
                category='prediction'
            elif name in ('code_lengths','global_table_bits','definition_bits','total_bits','structure_bits','seat_content_bits','hcost','fixed_spec_bits','_init_rec',
                         'reconcile','run_conversions','score_answers','rec_add','rec_means','update_accounting'):
                category='retention'
        elif leaf=='v310be' and name in ('score_answers','score_answers_role','init_rec','candidates'):
            category='retention'
        elif leaf=='accounting':
            category='retention'
        elif leaf=='agent_runtime' and name=='predict':
            category='prediction'
        elif leaf in ('smereplay','ledger','answerlog','routelog'):
            category='writing'
        elif leaf=='sme' and name.startswith('graph_of_'):
            category='preparation'
        elif leaf=='v32' and name=='commons_graph':
            category='preparation'
        # 記録の包みが本来の学習を呼ぶ時間を、JSON/書き出しへ混ぜない。
        if (name=='m1' or name.startswith('m1_')) and leaf not in ('routelog','smereplay'):
            category='other'
        if leaf in ('v39','v310be') and name in ('_init_rec','init_rec'):
            category='birth_scoring'
        if name in ('ledger_record','_ledger_record'):
            category='writing'
        # Codeも保持し、番号が後で別のCodeへ使われることを防ぐ。
        self.code_roots[at]=(code,category)
        return category

    def current(self):
        return self.stack[-1][1] if self.stack else 'other'

    def charge(self,now):
        if self.active and self.last is not None:
            self.seconds[self.current()]+=now-self.last

    def start(self,trial):
        assert trial==PROFILE_TRIALS[len(self.all_rows)]
        self.trial=trial
        self.seconds=Counter();self.calls=Counter();self.gc_seconds=Counter();self.aux_seconds=0.0
        self.active=True
        if self.profiler is None:
            self.profiler=cProfile.Profile(timer=time.process_time)
        self.profiler.enable()
        self.last=time.process_time()
        self.started_cpu=self.last
        self.started_perf=time.perf_counter()

    def finish_trial(self,now):
        self.charge(now)
        self.active=False
        self.profiler.disable()
        assert self.gc_start is None, '測定の境目でGCが進行中'
        row={'trial':self.trial,'sec_trial':time.perf_counter()-self.started_perf,'process_cpu_seconds':now-self.started_cpu,
            'accounted_seconds':sum(self.seconds.values()),
            **{name:self.seconds[name]-self.gc_seconds[name] for name in self.categories},
            'garbage_collection':sum(self.gc_seconds.values()),'trace_callback_seconds':self.aux_seconds,
            'rss_max_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        assert all(row[name]>=-1e-6 for name in self.categories),row
        assert abs(sum(row[name] for name in self.categories)+row['garbage_collection']-row['accounted_seconds'])<1e-6
        assert abs(row['accounted_seconds']+row['trace_callback_seconds']-row['process_cpu_seconds'])<1e-5,row
        self.writer.writerow(row);self.csv_stream.flush()
        detail={**row,'root_calls':dict(self.calls)}
        self.block.append(detail);self.all_rows.append(detail)
        if self.trial%100==99 or self.trial==LIMIT-1:
            begin=self.block[0]['trial']
            self.profiler.dump_stats(str(self.root/f'trials_{begin:04d}_{self.trial:04d}.prof'))
            (self.root/f'trials_{begin:04d}_{self.trial:04d}.json').write_text(json.dumps(self.block,indent=2)+'\n')
            self.block=[];self.profiler=None

    def trace(self,frame,event,arg):
        entered=time.process_time()
        self.in_trace=True
        if event=='call':
            frame.f_trace_lines=False
            frame.f_trace_opcodes=False
            if frame.f_code is self.input_code:
                trial=frame.f_locals['trial'].trial
                if self.active:
                    self.finish_trial(entered)
                if trial>=LIMIT:
                    assert trial==LIMIT
                    raise PrefixComplete()
                self.start(trial)
                entered=time.process_time()
            self.charge(entered)
            root=self.root_category(frame.f_code)
            inherited=self.current()
            self.stack.append((id(frame),inherited if inherited in ('nonlearning_tests','birth_scoring') else (root or inherited)))
            if root and self.active:self.calls[root]+=1
        elif event=='return':
            self.charge(entered)
            if self.stack:
                assert self.stack[-1][0]==id(frame), 'traceの呼び出しと戻りの組が違う'
                self.stack.pop()
        else:
            self.charge(entered)
        self.in_trace=False
        done=time.process_time()
        if self.active:self.aux_seconds+=done-entered
        self.last=done
        return self.trace

    def gc_event(self,phase,info):
        # trace自身が作る小さな入れ物によるGCは観測の秒へ入り、模型の秒から二重に引かない。
        if not self.active or self.in_trace:return
        if phase=='start':
            self.gc_start=(time.process_time(),self.current(),self.aux_seconds)
        elif phase=='stop' and self.gc_start is not None:
            started,category,aux=self.gc_start
            self.gc_seconds[category]+=time.process_time()-started-(self.aux_seconds-aux)
            self.gc_start=None

    def close(self):
        sys.settrace(None)
        if self.active:self.finish_trial(time.process_time())
        if self.gc_event in gc.callbacks:gc.callbacks.remove(self.gc_event)
        self.csv_stream.close()
        assert len(self.all_rows)==len(PROFILE_TRIALS) and not self.block
        (self.root/'timing_complete.json').write_text(json.dumps({'trials':len(PROFILE_TRIALS),'configured_trial_count':LIMIT,'ranges':RANGES,'rows':self.all_rows,
            'method':'cProfile + call/return trace。内訳はtime.process_timeのCPU秒、sec_trialはperf_counterの実時間。line/opcodeのtraceなし。外付けの_agent_inputの境目の包みは元の関数を一回呼び、入力を変えずに返す。模型の式・選択・乱数は変更なし。',
            'boundary':'_agent_inputの入口から次の入口。選ばれた区間だけtraceとcProfileを有効にし、区間の外では無効。最後はworkerの終了。観測CSV/prof書き出しは区間外。',
            'source':str(SOURCE),'timing_basis':'CPUの内訳には実行を止めた待ちを含めず、実時間との差を別記する。trace_callback_secondsもCPU秒。'},ensure_ascii=False,indent=2)+'\n')


def worker(task):
    import sweep
    root=Path(task['out_root']).parent
    real_run=sweep.run_one
    holder=[]
    def run_one(task):
        import abm.loop as loop
        real_input=loop._agent_input
        meter=Meter(root,real_input.__code__)
        holder.append(meter)
        def measured_input(trial,before):
            if trial.trial not in PROFILE_TRIALS:
                if meter.active:
                    meter.finish_trial(time.process_time())
                    sys.settrace(None)
                    meter.stack=[]
            elif not meter.active:
                meter.stack=[]
                sys.settrace(meter.trace)
            return real_input(trial,before)
        loop._agent_input=measured_input
        gc.callbacks.append(meter.gc_event)
        try:
            return real_run(task)
        finally:
            loop._agent_input=real_input
    sweep.run_one=run_one
    try:
        result=REAL_WORKER(task)
        assert len(holder)==1
        holder[0].close()
        return result
    except PrefixComplete:
        assert task.get('verb_world') and LIMIT==1000 and task['cfg']['trial_count']==5000
        assert len(holder)==1 and len(holder[0].all_rows)==LIMIT
        holder[0].close()
        # Ledgerのwithは例外で閉じる。sideの既存のcloseだけを実行して末尾の圧縮を閉じる。
        closures={}
        for name in ('smeshared','smereplay','smeevict','answerlog','routelog','probeworld','verbtiming'):
            module=sys.modules.get(name)
            if module is not None and hasattr(module,'close'):
                closures[name]=module.close()
        # v3_runのsideのfoなど、閉じる所まで戻らない既存の書き手も自分の出力先だけ閉じる。
        output=Path(task['out_root']).resolve()
        streams=[]
        for obj in gc.get_objects():
            if not isinstance(obj,io.IOBase) or obj.closed:continue
            name=getattr(obj,'name',None)
            if isinstance(name,(str,os.PathLike)):
                try:Path(name).resolve().relative_to(output)
                except ValueError:continue
                streams.append(obj)
        streams.sort(key=lambda x:0 if isinstance(x,io.TextIOBase) else 1)
        for obj in streams:
            if not obj.closed:obj.close()
        usage=resource.getrusage(resource.RUSAGE_SELF)
        evidence={'measurement_only':True,'completed_trials':LIMIT,'configured_trial_count':5000,
                  'horizon':task.get('horizon'),'next_trial_not_evaluated':True,'closed_modules':closures,
                  'completed_at':time.time(),'peak_rss_bytes':usage.ru_maxrss}
        (root/'prefix_complete.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        return {'cell':task['cell'],'seed':task['seed'],'trial_count':5000,'measured_trials':LIMIT,
                'measurement_only':True,'elapsed_sec':sum(r['sec_trial'] for r in holder[0].all_rows),
                'peak_rss_mb':round(usage.ru_maxrss/1e6,1),'stop_reason':'承認された先頭1000試行の計測完了'}
    except BaseException:
        sys.settrace(None)
        for meter in holder:
            if meter.profiler is not None:meter.profiler.disable()
            if meter.gc_event in gc.callbacks:gc.callbacks.remove(meter.gc_event)
        raise


def main():
    command=json.loads(Path(sys.argv[1]).read_text())
    assert command[command.index('--seeds')+1]=='1'
    assert not Path(command[3]).exists(), '出力を上書きしない'
    v3_run.worker=worker
    sys.argv=command[1:]
    os.chdir(SOURCE)
    v3_run.main()


if __name__=='__main__':main()
