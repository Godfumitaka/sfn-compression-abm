"""全対象の誕生記録に、その試行で消えた定義があるか調べる。"""
import json
import resource
import time
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

spec=spec_from_file_location('logp_seal_records',Path(__file__).with_name('logp_seals_stage1_2026-10-05.py'))
records=module_from_spec(spec)
spec.loader.exec_module(records)
ARMS,ROOT,input_paths,op=records.ARMS,records.ROOT,records.input_paths,records.op

start=time.monotonic(); counts={}; missing=[]
for arm in ARMS:
    births=retire=0
    for seed in range(1,21):
        with op(input_paths(arm,seed)['side']) as f:
            for line in f:
                r=json.loads(line)
                m=r.get('m1') or {}; reg=m.get('reg')
                if r.get('kind')=='v39' and reg and not reg[1]:
                    births+=1
                    if reg[0] in r.get('retire',[]):
                        retire+=1
                        missing.append({'arm':arm,'seed':seed,'trial':r['trial'],'R':reg[0],
                                        'births_rec':m.get('births_rec')})
    counts[arm]={'births':births,'same_trial_retire':retire}
summary={'counts':counts,'missing_candidates':missing,'seconds':time.monotonic()-start,
         'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(ROOT/'preflight.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='missing_candidates'},ensure_ascii=False))
