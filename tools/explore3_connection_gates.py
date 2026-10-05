"""TとL-BEの旗を実際の走行・復元に接続して確認する（種1・80試行）。"""
from pathlib import Path
import json,gzip,sys,os
import explore3_pipeline as p
p.save=lambda **changes:None
sys.path[:0]=[str(p.SOURCE/'tools'),str(p.SOURCE)]
import selcands
if len(sys.argv)>1:
    name=sys.argv[2];root=p.HERE/'gates'/name/'output'
    paths=list(root.glob('ledgers/cells/*/seed001.jsonl.gz'));assert len(paths)==1
    targets={}
    with gzip.open(paths[0],'rt') as stream:
        next(stream)
        for line in stream:
            row=json.loads(line)
            if row.get('record_type')!='trial' or not row.get('held_out_is_door') or row['prediction_kind']=='Abstain':continue
            targets[row['prediction_order']]=row['hit']
    os.chdir(p.SOURCE)
    result=selcands.one((str(root),paths[0].parent.name,1,targets,str(p.HERE/'gates'/name/'classification')))
    for key in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'):assert result[key]==0,result
    (p.HERE/'gates'/name/'connection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(name,json.dumps(result,ensure_ascii=False),flush=True)
    sys.exit(0)
results=[]
for name,flags in (('T80',['--tie-random']),('LBE80',['--score-logp','--score-logp-e'])):
    folder=p.HERE/'gates'/name
    cmd=[p.PYTHON,'tools/v3_run.py',str(p.HERE/'gates/config80.json'),str(folder/'output'),*p.COMMON,'--workers','1','--seeds','1','--shop-world','2','--v39-price','0.01873710622997919',*flags]
    p.run(cmd,p.SOURCE,folder);p.check_done(folder/'output',[1])
    # 差し替えを種ごとに別プロセスで初期化する。
    import subprocess
    subprocess.run([p.PYTHON,str(__file__),'verify',name],cwd=p.SOURCE,check=True)
