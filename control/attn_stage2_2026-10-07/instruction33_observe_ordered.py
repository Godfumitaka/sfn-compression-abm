"""計測と順つき照合器の状態を記録する。模型の式と実更新は差し替えない。"""
from pathlib import Path
import hashlib,json,os,resource,sys,time
SOURCE=Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE)]
import v3_run
REAL_WORKER=v3_run.worker


def worker(task):
    import sweep
    real=sweep.run_one
    root=Path(task['out_root']).parent
    (root/'worker_pid.json').write_text(json.dumps(dict(pid=os.getpid(),ppid=os.getppid()))+'\n')
    def one(task):
        import abm.loop as loop
        import attnsme,smeshared as S,cstar_runtime as C,smereplay as R
        real_record=loop._ledger_record
        usage_begin=resource.getrusage(resource.RUSAGE_SELF)
        begin=time.perf_counter();last=begin;count=0;max_candidates=max_definitions=0
        with (root/'performance.jsonl').open('x') as perf, (root/'tie_state.jsonl').open('x') as tie:
            def record(agent,trial,*args,**kw):
                nonlocal last,count,max_candidates,max_definitions
                result=real_record(agent,trial,*args,**kw)
                state=args[4] if len(args)>4 else kw['state']
                now=time.perf_counter();usage=resource.getrusage(resource.RUSAGE_SELF)
                count+=1;max_candidates=max(max_candidates,len(attnsme.ST['scored']))
                max_definitions=max(max_definitions,len(state.definitions))
                perf.write(json.dumps(dict(trial=trial.trial,seconds=now-last,elapsed_seconds=now-begin,
                    peak_rss_bytes=usage.ru_maxrss,candidates=len(attnsme.ST['scored']),definitions=len(state.definitions)))+'\n')
                perf.flush();last=now
                engines={}
                for label,engine in [('sme',S.ENGINE),('cstar',C.ENGINE)]:
                    digest=hashlib.sha256()
                    for key,value in engine.cache_rng.items():
                        digest.update(json.dumps([R.encode(key),R.encode(value)],ensure_ascii=False,separators=(',',':')).encode())
                    engines[label]=dict(rng=engine.rng.getstate(),cache_count=len(engine.cache),
                        self_cache_count=len(engine.self_cache),cache_rng_count=len(engine.cache_rng),cache_rng_sha256=digest.hexdigest())
                tie.write(json.dumps(dict(trial=trial.trial,call_context=R.encode(S.CTX),engines=engines),ensure_ascii=False)+'\n');tie.flush()
                return result
            loop._ledger_record=record
            try: result=real(task)
            finally: loop._ledger_record=real_record
        # 巨大な連結列を作らず、元の挿入順で一行ずつ保存する。
        with S._text_gzip(root/'saved_matcher.jsonl.gz') as out:
            for label,engine in [('sme',S.ENGINE),('cstar',C.ENGINE)]:
                out.write(json.dumps(dict(section=label+'_rng',value=R.encode(engine.rng.getstate())),ensure_ascii=False)+'\n')
                for name,table in [('cache',engine.cache),('self_cache',engine.self_cache),('cache_rng',engine.cache_rng)]:
                    for key,value in table.items():
                        out.write(json.dumps(dict(section=label+'_'+name,key=R.encode(key),value=R.encode(value)),ensure_ascii=False,separators=(',',':'))+'\n')
            for label,table in [('results',S.RESULTS),('graphs',S.GRAPHS),('choices',S.CHOICES),('stats',S.STATS)]:
                for key,value in table.items():
                    out.write(json.dumps(dict(section=label,key=R.encode(key),value=R.encode(value)),ensure_ascii=False,separators=(',',':'))+'\n')
        usage_end=resource.getrusage(resource.RUSAGE_SELF)
        cpu_user=usage_end.ru_utime-usage_begin.ru_utime
        cpu_system=usage_end.ru_stime-usage_begin.ru_stime
        (root/'measurement.json').write_text(json.dumps(dict(pid=os.getpid(),trials=count,
            wall_seconds=time.perf_counter()-begin,cpu_user_seconds=cpu_user,cpu_system_seconds=cpu_system,
            cpu_seconds=cpu_user+cpu_system,cpu_scope='worker_model_observer_state_save',peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            max_candidates=max_candidates,max_definitions=max_definitions,ru_maxrss_unit='macOS_bytes'),indent=2)+'\n')
        return result
    sweep.run_one=one
    try: return REAL_WORKER(task)
    finally: sweep.run_one=real


if __name__=='__main__':
    command=json.loads(Path(sys.argv[1]).read_text())
    assert not Path(command[3]).exists(),'既存出力を上書きしない'
    v3_run.worker=worker;sys.argv=command[1:];os.chdir(SOURCE);v3_run.main()
