"""模型の出力を変えず、時間・常駐・SHAの報告表を作る。成績は集計しない。"""
import argparse,csv,gzip,hashlib,json,math,re,shutil
from pathlib import Path
from cloud_run import read,save,complete

def sha(path,decoded=False):
    h=hashlib.sha256();n=0
    opener=gzip.open if decoded and path.suffix=='.gz' else open
    with opener(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b);n+=len(b)
    return h.hexdigest(),n

def table(path,rows,columns):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,columns,delimiter='\t');w.writeheader();w.writerows(rows)

def time_fields(data,prefix=''):
    if not isinstance(data,dict):return
    for k,v in data.items():
        key=prefix+k
        if isinstance(v,dict):yield from time_fields(v,key+'.')
        elif isinstance(v,(int,float)) and not isinstance(v,bool) and k.endswith('seconds'):
            assert math.isfinite(v)
            yield key,v

def export(case,destination):
    runtime=read(case/'runtime.json');limit=runtime['completed_trials'];complete(case,limit)
    destination.mkdir(parents=True,exist_ok=False)
    shutil.copy2(case/'time.log',destination/'time.log')
    raw=read(case/'result.json')['measurement_ru_maxrss_raw_unit'];assert raw=='KiB'
    points=[json.loads(x) for x in (case/'output/measurement/checkpoints.jsonl').read_text().splitlines()]
    assert [p['completed_trials'] for p in points]==list(range(100,limit+1,100))
    rows=[];previous_wall=previous_cpu=0
    for p in points:
        cpu=p['user_cpu_seconds']+p['system_cpu_seconds']
        rows.append(dict(completed_trials=p['completed_trials'],wall_seconds=p['wall_seconds'],
            interval_wall_seconds=p['wall_seconds']-previous_wall,user_cpu_seconds=p['user_cpu_seconds'],
            system_cpu_seconds=p['system_cpu_seconds'],cpu_seconds=cpu,interval_cpu_seconds=cpu-previous_cpu,
            ru_maxrss_raw=p['max_worker_rss_bytes'],ru_maxrss_raw_unit=raw,
            max_worker_rss_bytes=int(p['max_worker_rss_bytes'])*1024))
        previous_wall=p['wall_seconds'];previous_cpu=cpu
    table(destination/'checkpoints.tsv',rows,list(rows[0]))
    hashes=[]
    for p in sorted((case/'output').rglob('*')):
        if not p.is_file():continue
        raw_sha,raw_bytes=sha(p);content_sha,content_bytes=sha(p,True)
        hashes.append(dict(path=str(p.relative_to(case/'output')),raw_sha256=raw_sha,raw_bytes=raw_bytes,
                           content_sha256=content_sha,content_bytes=content_bytes))
    table(destination/'sha256.tsv',hashes,list(hashes[0]))
    totals={};file_totals=[]
    # 第二段の試行行と再照合の内訳は別表。重なる時間を足して総計にはしない。
    for p in sorted((case/'output/stage2').rglob('*')):
        if not p.is_file():continue
        if p.suffix not in ('.gz','.json'):continue
        per={}
        opener=gzip.open if p.suffix=='.gz' else open
        with opener(p,'rt') as f:
            records=[json.load(f)] if p.suffix=='.json' else (json.loads(line) for line in f)
            for record in records:
                for key,v in time_fields(record):per[key]=per.get(key,0)+v
        for key,v in per.items():file_totals.append(dict(path=str(p.relative_to(case/'output')),field=key,seconds=v))
    table(destination/'timing_breakdown.tsv',file_totals,['path','field','seconds'])
    fields=('label','source_commit','model_commit','observer_sha256','flags','completed_trials','configured_trial_count','horizon')
    save(destination/'provenance.json',{k:runtime[k] for k in fields})
    save(destination/'result.json',read(case/'result.json'))
    if limit==300:
        wall_intervals=[r['interval_wall_seconds'] for r in rows]
        cpu_intervals=[r['interval_cpu_seconds'] for r in rows]
        save(destination/'conditional_5000_estimate.json',dict(
            measured_trials=300,full_5000_completed=False,
            wall_seconds_range=[rows[-1]['wall_seconds']+47*min(wall_intervals),rows[-1]['wall_seconds']+47*max(wall_intervals)],
            cpu_seconds_range=[rows[-1]['cpu_seconds']+47*min(cpu_intervals),rows[-1]['cpu_seconds']+47*max(cpu_intervals)],
            assumption='残り4700の各100試行が実測した三つの区間の最小〜最大と同じ負荷で続く場合。増大・再照合・資源待ち・固定試験の変化を保証しない。上限保証ではない。',
            second_stage_table='timing_breakdown.tsv。試行本体・wrapper・再照合は包含があるので合算しない。'))
    print(json.dumps({'exported':str(destination),'completed_trials':limit,'model_started':False},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();export(a.case.resolve(),a.destination.resolve())
