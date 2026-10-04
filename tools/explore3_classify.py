"""e15ef19 の候補ごとの答え・分類を用いる。対象は種1〜20に固定。"""
import sys,json,gzip,os,time,csv
from pathlib import Path
from collections import Counter
from multiprocessing import get_context
W=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(W/'tools'),str(W)]
import selcands


def seed_job(job):
    root,cell,seed,targets,out=job
    os.chdir(W)
    return selcands.one((root,cell,seed,targets,out))


def main():
    root=Path(sys.argv[1]).resolve(); dest=Path(sys.argv[2]).resolve(); dest.mkdir(parents=True,exist_ok=True)
    cellpaths=list(root.glob('ledgers/cells/*'))
    assert len(cellpaths)==1,cellpaths
    cell=cellpaths[0].name
    jobs=[]; count={x:Counter() for x in ('e','n')}; misses={x:[] for x in ('e','n')}
    for seed in range(1,21):
        p=cellpaths[0]/f'seed{seed:03d}.jsonl.gz'
        assert p.is_file() and p.with_suffix('').with_suffix('.done').is_file(),p
        targets={}
        with gzip.open(p,'rt') as stream:
            header=json.loads(next(stream)); assert header['run_seed']==seed
            for line in stream:
                r=json.loads(line)
                if r.get('record_type')!='trial' or not r.get('held_out_is_door'):continue
                cue=r['shop_cue']; outcome='黙り' if r['prediction_kind']=='Abstain' else ('正解' if r['hit']==1 else '外れ')
                count[cue][outcome]+=1
                if outcome=='外れ':misses[cue].append((seed,r['prediction_order']))
                if cue=='e' and outcome!='黙り' or cue=='n' and outcome=='外れ':targets[r['prediction_order']]=r['hit']
        jobs.append((str(root),cell,seed,targets,str(dest/'候補')))
    nworkers=int(os.environ.get('SC_WORKERS','1'))
    with get_context('spawn').Pool(nworkers,maxtasksperchild=1) as pool:
        checks=pool.map(seed_job,jobs,chunksize=1)
    for ck in checks:
        for key in ('予測が本物と違う','一位が本物の選びと違う','一位でやり直した答えが本物と違う'):
            assert ck[key]==0,ck
    cases={}
    for seed in range(1,21):
        f=dest/'候補'/root.name/f'seed{seed:03d}.cases.jsonl'
        for line in f.read_text().splitlines():
            r=json.loads(line); cases[(seed,r['trial'])]=r
    result={'arm':root.name,'seeds':list(range(1,21)),'checks':checks,'tool_base':'e15ef19','days':{}}
    for cue in ('e','n'):
        cls=Counter('選び間違い' if cases[key]['正しく答える候補'] else '区別の喪失' for key in misses[cue])
        assert sum(cls.values())==count[cue]['外れ']
        result['days'][cue]={**{x:count[cue][x] for x in ('正解','外れ','黙り')},**{x:cls[x] for x in ('選び間違い','区別の喪失')}}
    (dest/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    rows=['| 腕 | 日 | 正解 | 外れ | 黙り | 選び間違い | 区別の喪失 |','|---|---|---:|---:|---:|---:|---:|']
    for cue,day in (('e','例外'),('n','通常')):
        d=result['days'][cue];rows.append('| '+root.name+' | '+day+' | '+' | '.join(str(d[x]) for x in ('正解','外れ','黙り','選び間違い','区別の喪失'))+' |')
    (dest/'表.md').write_text('\n'.join(rows)+'\n');print(json.dumps(result['days'],ensure_ascii=False),flush=True)
    import subprocess
    subprocess.run([sys.executable,str(W.parent/'report.py')],check=True)

if __name__=='__main__':main()
