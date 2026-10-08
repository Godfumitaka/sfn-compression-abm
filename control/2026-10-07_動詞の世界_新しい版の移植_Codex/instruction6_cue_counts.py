"""世界だけを生成し、指示boolと世界のSTATSを読む。模型は起動しない。"""
from pathlib import Path
import sys,json,time,resource,subprocess
source=Path(sys.argv[1]); output=Path(sys.argv[2])
sys.path[:0]=[str(source/'tools'),str(source)]
import abm.world as world
from abm.seed import load_seed
import verbworld
sd=load_seed(source/'tools/verb/U-011_seed_verb.json')
start=time.perf_counter(); rows=[]
for seed,expected in ((1,451),(2,462),(3,468)):
    verbworld.CFG.clear(); verbworld.CFG.update(items=verbworld.training_items(),door_p=None)
    for registry in (verbworld.INFO,verbworld.IDS,verbworld.STATS):registry.clear()
    truth_count=0
    for t in range(5000):
        trial=verbworld.verb_trial(world.generate_trial,seed,t,('agent',),seed=sd)
        instruction=verbworld.task_instruction(trial)
        assert type(instruction) is bool
        truth_count+=instruction
    stats=dict(verbworld.STATS)
    rows.append(dict(seed=seed,trials=stats['trials'],true_instructions=truth_count,
                     world_stats=stats['held_out_is_past'],existing_expected=expected,
                     passed=truth_count==stats['held_out_is_past']==expected))
result=dict(passed=all(x['passed'] for x in rows),rows=rows,
            elapsed_seconds=time.perf_counter()-start,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
            models_started=0,world_rng_added=False)
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(0 if result['passed'] else 1)
