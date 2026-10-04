"""模型の外で各試行の同点専用乱数の状態を記録する。"""
from pathlib import Path
import json
import os
import sys
import resource,time

SOURCE = Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker


def worker(task):
    import sweep
    real_run_one = sweep.run_one
    out = Path(task['out_root']).parent
    stream = (out / 'tie_rng.jsonl').open('w')
    timing = (out / 'performance.jsonl').open('w')
    (out/'worker_pid.json').write_text(json.dumps({'pid':os.getpid(),'ppid':os.getppid()})+'\n')

    def run_one(task):
        import abm.loop as loop
        import smeshared
        real_record,real_input = loop._ledger_record,loop._agent_input
        current={}
        def agent_input(trial,before):
            current["began"]=time.perf_counter();return real_input(trial,before)

        def record(agent_id, trial, *args, **kwargs):
            result = real_record(agent_id, trial, *args, **kwargs)
            elapsed=time.perf_counter()-current["began"]
            stream.write(json.dumps({'trial': trial.trial, 'rng': smeshared.ENGINE.rng.getstate(),
                                     'cache_count': len(smeshared.ENGINE.cache),
                                     'self_cache_count': len(smeshared.ENGINE.self_cache),
                                     'cache_rng_count': len(smeshared.ENGINE.cache_rng)},
                                    ensure_ascii=False) + '\n')
            stream.flush()
            timing.write(json.dumps({"trial":trial.trial,"seconds":elapsed,"peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"sme_log_end":smeshared.LOG["f"].tell() if smeshared.LOG.get("f") is not None else 0,"diagnostic_log_end":smeshared.LOG["diagnostic_f"].tell() if smeshared.LOG.get("diagnostic_f") is not None else 0})+"\n");timing.flush()
            return result

        loop._ledger_record,loop._agent_input = record,agent_input
        return real_run_one(task)

    sweep.run_one = run_one
    try:
        return REAL_WORKER(task)
    finally:
        stream.close()
        timing.close()


def main():
    command = json.loads(Path(sys.argv[1]).read_text())
    output = Path(command[3])
    if output.exists():
        raise SystemExit('出力を上書きしない')
    output.parent.mkdir(parents=True, exist_ok=True)
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()


if __name__ == '__main__':
    main()
