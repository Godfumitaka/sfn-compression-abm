"""集団の番号・名札長を保った一個体だけの独立走行。COLL8_SOLO_AGENTで対象を指定する。"""
import json
import os
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[2])]
import v3_run


def one_agent(args, tasks, out_root, manifest):
    agent = int(os.environ['COLL8_SOLO_AGENT'])
    fs = [float(x) for x in args.v311c_f.split(',')]
    groups = [int(x) for x in args.v311c_groups.split(',')]
    runs = [int(x) for x in args.v311c_runs.split(',')]
    assert len(runs)==1 and runs[0] in (1,2,3)
    run = runs[0]
    assert args.v311c_q==0 and 0<=agent<len(fs)
    task = dict(tasks[0],seed=run+1000*agent,f=fs[agent],compare=False,
                v311c={'run':run,'agent':agent,'n':len(fs),'q':0,'m':args.v311c_m,'recv':args.v311c_recv,
                       'groups':groups,'tags':not args.v311c_no_tags,'b_n':args.v311c_b_n})
    save = out_root/'solo-task.json'
    save.write_text(json.dumps(task,ensure_ascii=False,default=str)+'\n')
    rec = v3_run.worker(task)
    with manifest.open('a') as f:f.write(json.dumps(rec,ensure_ascii=False,default=str)+'\n')
    if rec.get('error'):raise RuntimeError(rec['error'])

v3_run._run_collective = one_agent
if __name__=='__main__':v3_run.main()
