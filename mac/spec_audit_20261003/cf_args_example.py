import runpy, json, hashlib
from pathlib import Path
r=runpy.run_path(str(Path(__file__).with_name('role_args_example.py')))
import cflearn, probeworld
st=r['st']; snap=probeworld._snapshot_modules()
fp=hashlib.sha256(repr(st).encode()).hexdigest()
try:
 result=cflearn.variants_correct(st,r['AgentInput'](r['sc'],r['sc'],frozenset(x.relation_id for x in r['sc'].relations)),r['cfg'],'D',1,r['held'],r['out'].prediction,r['v39'].predict,1)
finally: probeworld._restore_modules(snap)
bits={k:{state:(0.0 if hit else r['expected']) for state,hit in flags.items()} for k,(_st,flags) in result.items()}
out={'correct_by_thinned_state':result,'rewrite_bits_by_state':bits,'actual_argument_mismatch_detected':all(v['F']==r['expected'] for v in bits.values()),'memory_unchanged':fp==hashlib.sha256(repr(st).encode()).hexdigest()}
Path(__file__).with_name('analysis').joinpath('cf_args_example.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert out['actual_argument_mismatch_detected'] and out['memory_unchanged']
print(json.dumps(out,ensure_ascii=False,indent=2))
