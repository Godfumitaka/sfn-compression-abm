"""保存記憶に既存の分類手続きを適用。新しい走行・学習は作らない。"""
import json
import sys
import time
import resource
import os
from concurrent.futures import ProcessPoolExecutor
from stage1 import ROOT,SRC,ARMS,arm_root,input_paths,sha

sys.path.insert(0,str(SRC/'tools'))

def work(job):
    arm,seed,targets=job
    os.chdir(SRC)
    start=time.monotonic(); paths=input_paths(arm,seed)
    old=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.json').read_text())['input_sha256']
    assert old=={str(p):sha(p) for p in paths.values()}
    import selcands
    result=selcands.one((str(arm_root(arm)),paths['ledger'].parent.name,seed,targets,str(ROOT/'silent_cands')))
    assert result['予測が本物と違う']==0,result
    assert result['対象']==result['作った試行']==len(targets),result
    assert old=={str(p):sha(p) for p in paths.values()}
    result.update(seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  input_unchanged=True,notes='黙りではR_usedがないため、発話した定義の一位一致の検査は適用しない。')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    assert json.loads((ROOT/'stage1_summary.json').read_text())['stage1_pass']
    jobs=[]
    for arm in ARMS[:3]:
        for seed in range(1,21):
            rows=json.loads((ROOT/'stage1_full'/arm/f'seed{seed:03d}.door_records.json').read_text())
            targets={r['trial']:0 for r in rows if r['day']=='e' and r['outcome']=='黙り'}
            if targets:jobs.append((arm,seed,targets))
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool: results=list(pool.map(work,jobs,chunksize=1))
    (ROOT/'silent_candidates_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
