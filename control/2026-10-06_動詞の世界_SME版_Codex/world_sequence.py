"""模型を呼ばず、種1の全場面・問い・試験をそのまま記録する。"""
import json
import sys
from pathlib import Path
source, output = map(Path, sys.argv[1:3])
sys.path[:0] = [str(source / 'tools'), str(source)]
import verbworld
import sweep
import abm.world as w
import abm.loop as loop
verbworld.install()
sd = sweep.load_seed(source / 'tools/verb/U-011_seed_verb.json')
world = w.generate_world(1, 5000, ('agent',), seed=sd, holdout_include_second_order=False)
output.parent.mkdir(parents=True, exist_ok=True)
with output.open('x') as out:
    def record(value):
        out.write(json.dumps(loop._canonical(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n')
    record({'kind': 'world', 'seed': 1, 'trial_count': 5000, 'world_hash': world.world_hash})
    for t, wt in enumerate(world.trials):
        record({'kind': 'trial', 't': t, 'full': wt.G_star.to_dict(), 'partial': wt.target_graph_partial.to_dict(),
                'held': wt.held_out_edge.to_dict(), 'u_coins': wt.u_coins,
                'verb': verbworld.INFO[wt.G_star.graph_id], 'motif': wt.motif})
    pst = {'sd': sd, 'probes': []}
    verbworld.add_probes(pst, run_seed=1, agent_ids=('agent',), holdout_second=False)
    for i, q in enumerate(pst['probes']):
        record({'kind': 'probe', 'i': i, 'question': q})
print(json.dumps({'world_hash': world.world_hash, 'trials': 5000, 'probes': len(pst['probes'])}), flush=True)
