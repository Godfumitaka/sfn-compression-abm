"""記録の欄だけを調べる。模型は動かさない。"""
import gzip
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
W = ROOT.parent
SRC = W / 'codex_explore3_2026-10-04/source'
sys.path.insert(0, str(SRC))
from abm.loop import _apply

arms = [W / 'codex_explore3_2026-10-04/runs/L-B_w2_A_lam0.01873710622997919',
        W / 'codex_attn_2026-10-03/material_rebuild_2026-10-04/n3_w2_A_L50']

def op(p):
    return gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()

out = []
start = time.time()
for arm in arms:
    led = next((arm / 'ledgers/cells').glob('*/seed001.jsonl.gz'))
    side = arm / 'side' / led.parent.name / 'seed001.jsonl'
    if not side.exists():
        side = side.with_suffix('.jsonl.gz')
    births = []
    with op(side) as f:
        for line in f:
            row = json.loads(line)
            if row.get('kind') == 'v39' and (row.get('m1') or {}).get('reg') and not row['m1']['reg'][1]:
                births.append(row)
                if len(births) == 8:
                    break
    wanted = {b['trial']: b for b in births}
    states = {}
    state = None
    with op(led) as f:
        header = json.loads(next(f))
        for line in f:
            r = json.loads(line)
            if r.get('record_type', 'trial') != 'trial':
                continue
            ss = r['state_snapshot']
            state = ss['value'] if ss['kind'] == 'full' else _apply(state, ss['changes'])
            t = r['prediction_order']
            if t in wanted:
                name = wanted[t]['m1']['reg'][0]
                states[t] = {'row_keys': list(r), 'm1': wanted[t]['m1'],
                             'v39_keys': list(wanted[t]), 'events': wanted[t].get('events'),
                             'definition': state.get('definitions', {}).get(name),
                             'slot_history': {k:v for k,v in state.get('slot_history', {}).items() if name in k},
                             'v39_seats': {k:v for k,v in state.get('v39_seats', {}).items() if name in k}}
            if len(states) == len(wanted):
                break
    out.append({'arm': str(arm), 'header_keys': list(header), 'state_keys': list(state), 'births': states})
dest = ROOT / 'inspection.json'
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'output': str(dest), 'seconds': time.time()-start,
                  'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'births': [len(o['births']) for o in out]}))
