"""二つの関門が通ったときだけ、承認済みの種1を一本実行する。再走行はしない。"""
from pathlib import Path
import json
import subprocess
import time

root = Path(__file__).resolve().parent
py = '/opt/homebrew/opt/python@3.12/bin/python3.12'
jobs = Path.home()/'jobs/jobs.py'

def status(value):
    (root/'status.json').write_text(json.dumps({'epoch_seconds':time.time(),**value},ensure_ascii=False,indent=2)+'\n')

def registered(label, mem):
    folder=root/label
    output=json.loads((folder/'spec.json').read_text())['output']
    cmd=['/usr/bin/python3',str(jobs),'run','--wait','--owner','Codex 動詞SME '+label,
         '--mem',str(mem),'--disk-path',output,'--',py,str(root/'run_case.py'),str(folder)]
    status({'state':'running_or_waiting','label':label,'command':cmd})
    with (folder/'jobs.log').open('x') as out:
        result=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
    assert result.returncode==0,(label,result.returncode)
    assert json.loads((folder/'result.json').read_text())['exit_code']==0

try:
    status({'state':'waiting_shop_port'})
    while not (root/'gates/shop_port/result.json').exists():
        time.sleep(5)
    assert json.loads((root/'gates/shop_port/result.json').read_text())['exit_code']==0
    # 比較も読み取りとして受付を通す。
    for kind in ('shop','verb'):
        if kind=='verb':
            for name in ('verb_old','verb_port'):
                registered('gates/'+name,0.6)
        folder=root/'gates'/('compare_'+kind);folder.mkdir(exist_ok=True)
        status({'state':'comparing','gate':kind})
        cmd=['/usr/bin/python3',str(jobs),'run','--wait','--owner','Codex 動詞SME '+kind+'一致',
             '--mem','0.2','--disk-path',str(folder),'--',py,str(root/'compare_gates.py'),kind]
        with (folder/'jobs.log').open('x') as out:
            result=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
        assert result.returncode==0,(kind,'一致関門不通')
        assert json.loads((root/'gates'/f'{kind}_comparison.json').read_text())['passed']
    status({'state':'gates_passed'})
    registered('pilot_A_global_s01',1.3)
    manifest=[json.loads(x) for x in (root/'pilot_A_global_s01/output/manifest.jsonl').read_text().splitlines()]
    assert len(manifest)==1 and manifest[0].get('trial_count')==5000 and not manifest[0].get('error') and not manifest[0].get('v39_unfit'),manifest
    status({'state':'pilot_complete','trial_count':5000,'seed':1})
except Exception as e:
    status({'state':'stopped','reason':repr(e)})
    raise
