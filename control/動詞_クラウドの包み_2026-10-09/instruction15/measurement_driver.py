"""測定専用：設定と時間幅5000を保ち、先頭100又は300試行だけで正常終了。"""
from dataclasses import replace
from contextlib import contextmanager
from itertools import islice
from pathlib import Path
from types import SimpleNamespace
import json,os,resource,sys,time

class PrefixTrials:
    def __init__(self, trials, limit):
        self.trials,self.limit=trials,limit
        assert len(trials)==5000 and limit in (20,100,300)
    def __len__(self):return len(self.trials)
    def __iter__(self):return islice(iter(self.trials),self.limit)

@contextmanager
def observe_written_rows(ledger, observe):
    """世界と記録の接続後の追記を、一度だけ呼んだ後で数える。"""
    native_append = ledger.append
    absent = object()
    previous = vars(ledger).get('append', absent)
    def append(record):
        result = native_append(record)
        observe(record)
        return result
    ledger.append = append
    try:
        yield
    finally:
        if previous is absent:
            del ledger.append
        else:
            ledger.append = previous

@contextmanager
def observe_log_fallbacks(shared):
    """書き出しのfallbackだけを外側で数え、模型のSTATSや乱数を変えない。"""
    native = shared._log_string_keys
    counts = {"fallback_calls": 0}
    depth = 0
    def wrapped(value):
        nonlocal depth
        if depth == 0:
            counts["fallback_calls"] += 1
        depth += 1
        try:
            return native(value)
        finally:
            depth -= 1
    shared._log_string_keys = wrapped
    try:
        yield counts
    finally:
        shared._log_string_keys = native

if __name__ in ('__main__','__mp_main__'):
    if __name__=='__main__':
        os.environ['VERB_MEASUREMENT_SOURCE']=sys.argv[1]
        os.environ['VERB_MEASUREMENT_LIMIT']=sys.argv[2]
    source=Path(os.environ['VERB_MEASUREMENT_SOURCE']).resolve()
    limit=int(os.environ['VERB_MEASUREMENT_LIMIT'])
    sys.path[:0]=[str(source/'tools'),str(source)]
    import sweep
    import v3_run
    original_worker=v3_run.worker
    original_longitudinal=sweep.run_longitudinal
    sweep.code_commit=lambda:'4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'

    def measurement_worker(task):
        assert task['cfg']['trial_count']==5000 and task['seed']==1 and task['cfg']['agent_ids']==['agent']
        out=Path(task['out_root']);dest=out/'measurement'
        dest.mkdir(parents=True,exist_ok=True)
        completed=0;began=time.perf_counter();previous=began
        def observed(record):
            nonlocal completed,previous
            completed+=1
            assert completed<=limit
            if completed%100==0 or completed==limit:
                now=time.perf_counter();u=resource.getrusage(resource.RUSAGE_SELF)
                with (dest/'checkpoints.jsonl').open('a') as f:
                    f.write(json.dumps(dict(completed_trials=completed,configured_trial_count=5000,
                        horizon=5000,wall_seconds=now-began,interval_seconds=now-previous,
                        user_cpu_seconds=u.ru_utime,system_cpu_seconds=u.ru_stime,
                        max_worker_rss_bytes=u.ru_maxrss,epoch_seconds=time.time()))+'\n')
                previous=now
        def longitudinal(world,*args,**kwargs):
            assert len(world.trials)==5000
            prefix=SimpleNamespace(trials=PrefixTrials(world.trials,limit),world_hash=world.world_hash)
            active_ledger = kwargs["ledger"] if "ledger" in kwargs else args[2]
            with observe_written_rows(active_ledger, observed):
                result=original_longitudinal(prefix,*args,**kwargs)
            assert completed==limit
            return replace(result,trial_count=limit)
        sweep.run_longitudinal=longitudinal
        try:
            import smeshared
            with observe_log_fallbacks(smeshared) as fallback:
                record=original_worker(task)
        except Exception:
            # 模型を変えず、失敗した呼び出しの箇所だけを保存する。
            __import__("traceback").print_exc()
            raise
        finally:
            sweep.run_longitudinal=original_longitudinal
        assert record['trial_count']==completed==limit and not record.get('error')
        marker=dict(measurement_only=True,configured_trial_count=5000,horizon=5000,
            completed_trials=limit,source_commit=__import__('subprocess').check_output(
                ['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
            boundary='301又は101の学習試行を実行せず、通常の終了処理で全出力を閉じる',
            full_5000_completed=False,wall_seconds=time.perf_counter()-began)
        marker['json_log_fallback_calls']=fallback['fallback_calls']
        (dest/'log_fallback_counts.json').write_text(json.dumps(dict(completed_trials=completed,fallback_calls=fallback['fallback_calls'],model_stats_modified=False,source_commit=marker['source_commit']),indent=2)+'\n')
        (dest/'partial_done.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2)+'\n')
        return {**record,**marker}

    v3_run.worker=measurement_worker
    if __name__=='__main__':
        sys.argv=[str(source/'tools/v3_run.py'),*sys.argv[3:]]
        v3_run.main()
