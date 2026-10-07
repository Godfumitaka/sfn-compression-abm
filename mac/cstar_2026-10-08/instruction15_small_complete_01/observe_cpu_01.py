"""全長のCPUとGCを外側で測る。模型の関数は元を一回だけ呼ぶ。"""
from pathlib import Path
import gc, json, os, sys, time
SOURCE = Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker

def worker(task):
    root = Path(task['out_root']).parent
    assert not (root/'whole_cpu.json').exists()
    total_start = time.process_time()
    wall_start = time.perf_counter()
    record = dict(gc_seconds=0.0, gc_calls=[0,0,0], observer_callback_cpu_seconds=0.0)
    started = None
    def gc_event(phase, information):
        nonlocal started
        begin = time.process_time()
        if phase == 'start':
            started = begin
        elif phase == 'stop' and started is not None:
            record['gc_seconds'] += begin-started
            record['gc_calls'][information['generation']] += 1
            started = None
        record['observer_callback_cpu_seconds'] += time.process_time()-begin
    gc.callbacks.append(gc_event)
    try:
        result = REAL_WORKER(task)
    finally:
        gc.callbacks.remove(gc_event)
    total = time.process_time()-total_start
    record.update(whole_worker_process_cpu_seconds=total,
                  callback_adjusted_worker_cpu_seconds=total-record['observer_callback_cpu_seconds'],
                  worker_wall_seconds=time.perf_counter()-wall_start,
                  configured_trials=task['cfg']['trial_count'],
                  scope='workerの初期化から模型・記録のcloseまで。cProfile・関数traceは使用しない。GC区間は入れ子で総CPUへ足さない。callback自体の計測済みCPUを総CPUから除くがtime関数等の微小な負荷は残る。',
                  source=str(SOURCE), input_output_rng_unchanged=True)
    (root/'whole_cpu.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    return result

v3_run.worker = worker
if __name__ == '__main__':
    command = json.loads(Path(sys.argv[1]).read_text())
    sys.argv = command[1:]
    v3_run.main()
