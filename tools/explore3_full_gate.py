"""世界2・A・種1の1740試行で旗なしの台帳本体を確認する。"""
from pathlib import Path
import json,hashlib
import explore3_pipeline as p
p.HERE=Path(__file__).resolve().parents[2]
p.state={'phase':'full_gate'}
# 本走行のstatus.jsonと独立した記録
p.save=lambda **changes:None
pair=[]
for repo,kind in ((p.BASE,'baseline'),(p.SOURCE,'changed')):
    folder=p.HERE/'gates/full1740'/kind
    cmd=[p.PYTHON,'tools/v3_run.py',p.CONFIG,str(folder/'output'),*p.COMMON,'--workers','1','--seeds','1','--shop-world','2','--v39-price','0.01873710622997919']
    p.run(cmd,repo,folder);p.check_done(folder/'output',[1]);pair.append(folder/'output')
a,b=map(p.body,pair)
assert a==b,'旗なしの1740試行で不一致'
(p.HERE/'gates/full1740/comparison.json').write_text(json.dumps({'world':2,'mode':'A','seed':1,'trials':1740,'body_equal':True,'sha256':hashlib.sha256(a).hexdigest()},indent=2)+'\n')
print('旗なし1740試行の台帳本体が一致',flush=True)
