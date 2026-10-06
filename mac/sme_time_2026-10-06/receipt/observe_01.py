"""外付けのcProfileと呼び出しのtraceで、模型の関数を置き換えず時間を分ける。"""
from collections import Counter
from pathlib import Path
import cProfile
import csv
import gc
import json
import os
import resource
import sys
import time

SOURCE=Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import v3_run
REAL_WORKER=v3_run.worker


class Meter:
    """同じ範囲を二重に足さず、入口の種類を内側の入口で上書きして数える。"""
    categories=('engine','preparation','retention','prediction','writing','other')

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
        self.writer=csv.DictWriter(self.csv_stream,fieldnames=['trial','sec_trial','accounted_seconds',
            *self.categories,'garbage_collection','trace_callback_seconds','rss_max_bytes'])
        self.writer.writeheader()

    def root_category(self,code):
        at=id(code)
        if at in self.code_roots:
            return self.code_roots[at][1]
        filename,name=code.co_filename,code.co_name
        leaf=Path(filename).stem
        category=None
        if leaf=='sme2017':
            if name=='run':category='engine'
            elif name in ('_key','_canonical','match','match_key','self_score','snapshot','restore','fingerprint'):
                category='preparation'
        elif leaf=='smeintern':
            category='engine' if name=='run' else 'preparation'
        elif leaf=='smeshared':
            if name in ('_log','close'):category='writing'
            elif name in ('typed_graph','graph_data','freeze','canonical_identity','structural_key',
                         'call_seed','_match_seed','_old_on_new','snapshot','restore'):
                category='preparation'
            elif name in ('_definition_choice','choose_trace','select_definition'):category='prediction'
        elif leaf=='v39':
            if name=='v39_graph':category='preparation'
            elif name in ('predict','predict_wrapped','select_definition','fill_v39','fill_decision',
                         'h_answer','u_answer','three_answers','amb_blocks'):
                category='prediction'
            elif name in ('code_lengths','global_table_bits','definition_bits','total_bits','_init_rec',
                         'reconcile','run_conversions','score_answers','rec_add','rec_means'):
                category='retention'
        elif leaf in ('smereplay','ledger','answerlog','routelog'):
            category='writing'
        elif leaf=='sme' and name.startswith('graph_of_'):
            category='preparation'
        elif leaf=='v32' and name=='commons_graph':
            category='preparation'
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
        assert self.trial is None or trial==self.trial+1
        self.trial=trial
        self.seconds=Counter();self.calls=Counter();self.gc_seconds=Counter();self.aux_seconds=0.0
        self.active=True
        if self.profiler is None:
            self.profiler=cProfile.Profile()
        self.profiler.enable()
        self.last=time.perf_counter()
        self.started_perf=self.last

    def finish_trial(self,now):
        self.charge(now)
        self.active=False
        self.profiler.disable()
        assert self.gc_start is None, '測定の境目でGCが進行中'
        row={'trial':self.trial,'sec_trial':now-self.started_perf,
            'accounted_seconds':sum(self.seconds.values()),
            **{name:self.seconds[name]-self.gc_seconds[name] for name in self.categories},
            'garbage_collection':sum(self.gc_seconds.values()),'trace_callback_seconds':self.aux_seconds,
            'rss_max_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        assert all(row[name]>=-1e-6 for name in self.categories),row
        assert abs(sum(row[name] for name in self.categories)+row['garbage_collection']-row['accounted_seconds'])<1e-6
        assert abs(row['accounted_seconds']+row['trace_callback_seconds']-row['sec_trial'])<1e-5,row
        self.writer.writerow(row);self.csv_stream.flush()
        detail={**row,'root_calls':dict(self.calls)}
        self.block.append(detail);self.all_rows.append(detail)
        if self.trial%100==99 or self.trial==1739:
            begin=self.block[0]['trial']
            self.profiler.dump_stats(str(self.root/f'trials_{begin:04d}_{self.trial:04d}.prof'))
            (self.root/f'trials_{begin:04d}_{self.trial:04d}.json').write_text(json.dumps(self.block,indent=2)+'\n')
            self.block=[];self.profiler=None

    def trace(self,frame,event,arg):
        entered=time.perf_counter()
        self.in_trace=True
        if event=='call':
            frame.f_trace_lines=False
            frame.f_trace_opcodes=False
            if frame.f_code is self.input_code:
                trial=frame.f_locals['trial'].trial
                if self.trial is not None:
                    self.finish_trial(entered)
                self.start(trial)
                entered=time.perf_counter()
            self.charge(entered)
            root=self.root_category(frame.f_code)
            inherited=self.current()
            self.stack.append((id(frame),root or inherited))
            if root and self.active:self.calls[root]+=1
        elif event=='return':
            self.charge(entered)
            if self.stack:
                assert self.stack[-1][0]==id(frame), 'traceの呼び出しと戻りの組が違う'
                self.stack.pop()
        else:
            self.charge(entered)
        self.in_trace=False
        done=time.perf_counter()
        if self.active:self.aux_seconds+=done-entered
        self.last=done
        return self.trace

    def gc_event(self,phase,info):
        # trace自身が作る小さな入れ物によるGCは観測の秒へ入り、模型の秒から二重に引かない。
        if not self.active or self.in_trace:return
        if phase=='start':
            self.gc_start=(time.perf_counter(),self.current(),self.aux_seconds)
        elif phase=='stop' and self.gc_start is not None:
            started,category,aux=self.gc_start
            self.gc_seconds[category]+=time.perf_counter()-started-(self.aux_seconds-aux)
            self.gc_start=None

    def close(self):
        sys.settrace(None)
        if self.active:self.finish_trial(time.perf_counter())
        if self.gc_event in gc.callbacks:gc.callbacks.remove(self.gc_event)
        self.csv_stream.close()
        assert len(self.all_rows)==1740 and not self.block
        (self.root/'timing_complete.json').write_text(json.dumps({'trials':1740,'rows':self.all_rows,
            'method':'cProfile + call/return trace（line/opcodeのtraceなし）。模型の関数の置換なし。',
            'boundary':'_agent_inputの入口から次の入口。最後はworkerの終了。観測CSV/prof書き出しは区間外。',
            'source':str(SOURCE)},ensure_ascii=False,indent=2)+'\n')


def worker(task):
    import sweep
    root=Path(task['out_root']).parent
    real_run=sweep.run_one
    holder=[]
    def run_one(task):
        import abm.loop as loop
        meter=Meter(root,loop._agent_input.__code__)
        holder.append(meter)
        gc.callbacks.append(meter.gc_event)
        sys.settrace(meter.trace)
        return real_run(task)
    sweep.run_one=run_one
    try:
        result=REAL_WORKER(task)
        assert len(holder)==1
        holder[0].close()
        return result
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
