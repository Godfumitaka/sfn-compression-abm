"""全長の全バイト関門後、小さい観測だけを一度集計する。模型を起動しない。"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import csv, hashlib, json

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'full1740_01'
OUTPUTS=('analysis.json','memory_points_01.csv','memory_groups_01.csv','memory_types_01.csv')
EXPECTED={('after_prediction',99),('after_prediction',999),('after_prediction',1739),
          ('first_engine_return_at_fixed_trial',1399),('first_snapshot_at_fixed_trial',1399),('completion',1739)}
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):
    with p.open('x') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
def csv_file(name,columns,rows):
    with (WORK/name).open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns); writer.writeheader(); writer.writerows(rows)

try:
    assert not any((WORK/name).exists() for name in OUTPUTS), '途中・完成の集計を重複しない'
    assert not (WORK/'STOP.json').exists(), '観測の不通・不一致の後は集計しない'
    complete=read(WORK/'complete.json'); comparison=read(WORK/'comparison.json')
    check=read(WORK/'observation_check.json'); manifest=read(WORK/'observations_complete.json')
    assert complete['passed'] and complete['configured_trials']==1740 and complete['model_bytes_identical']
    assert complete['observation_complete'] and complete['samples']==6
    assert complete['source_commit']=='7774b60709656446a352f3b43e25b67f4b6fc2fa'
    assert complete['observer_sha256']=='14e49a1d3d7b0a364026f907b00e447a2e6dd1b944a6aa69c7b16c98a56c207a'
    assert comparison['passed'] and len(comparison['files'])==7 and all(x['equal'] for x in comparison['files'])
    assert check['complete'] and check['samples']==6 and check['incomplete_count']==0
    assert manifest['observer_completed'] and manifest['predictions']==1740 and manifest['samples']==6
    samples=[json.loads(line) for line in (WORK/'memory_observations.jsonl').read_text().splitlines()]
    assert len(samples)==6 and {(o['kind'],o['trial_index']) for o in samples}==EXPECTED
    points=[]; groups=[]; types=[]
    for o in samples:
        assert o['complete'] and o['observer_bitmap_limit_bytes']==256*2**20
        assert sum(g['newly_reached_objects'] for g in o['groups'])==o['unique_objects']
        assert sum(g['newly_reached_bytes'] for g in o['groups'])==o['unique_sys_getsizeof_bytes']
        point=dict(kind=o['kind'],trial_index=o['trial_index'],trial_number=o['trial_index']+1,
                   unique_objects=o['unique_objects'],unique_sys_getsizeof_bytes=o['unique_sys_getsizeof_bytes'],
                   current_rss_before_bytes=o['current_rss_before_bytes'],current_rss_after_bytes=o['current_rss_after_bytes'],
                   past_maximum_rss_bytes=o['past_maximum_rss_bytes'],observer_bitmap_bytes=o['observer_bitmap_bytes'],
                   counts=o['counts'],groups=[])
        type_counts=Counter(); type_bytes=Counter()
        for g in o['groups']:
            assert sum(t['objects'] for t in g['types'])==g['newly_reached_objects']
            assert sum(t['bytes'] for t in g['types'])==g['newly_reached_bytes']
            entry=dict(label=g['label'],newly_reached_objects=g['newly_reached_objects'],newly_reached_bytes=g['newly_reached_bytes'])
            point['groups'].append(entry)
            groups.append(dict(kind=o['kind'],trial_number=o['trial_index']+1,**entry))
            for t in g['types']:
                type_counts[t['type']]+=t['objects']; type_bytes[t['type']]+=t['bytes']
                types.append(dict(kind=o['kind'],trial_number=o['trial_index']+1,root=g['label'],**t))
        point['types_across_roots']=[dict(type=name,objects=type_counts[name],bytes=type_bytes[name]) for name in sorted(type_counts)]
        points.append(point)
    resource=dict(samples=0,external_model_counts=Counter(),held_samples=0,swap_growth_samples=0,
                  thermal_warning_samples=0,maximum_sampled_model_tree_rss_bytes=0,minimum_disk_free_bytes=None)
    with (WORK/'resources.jsonl').open() as f:
        for line in f:
            r=json.loads(line); resource['samples']+=1
            resource['external_model_counts'][str(r['cpu']['external_count'])]+=1
            resource['held_samples']+=int(r['held'])
            resource['swap_growth_samples']+=int(bool(r['resources']['swap_grew']))
            resource['thermal_warning_samples']+=int(bool(r['resources']['thermal_warning']))
            resource['maximum_sampled_model_tree_rss_bytes']=max(resource['maximum_sampled_model_tree_rss_bytes'],r['rss_bytes'])
            free=r['resources']['free_bytes']; current=resource['minimum_disk_free_bytes']
            resource['minimum_disk_free_bytes']=free if current is None else min(current,free)
    resource['external_model_counts']=dict(resource['external_model_counts'])
    predictions=[p for p in points if p['kind']=='after_prediction']
    final=next(p for p in points if p['kind']=='completion')
    result=dict(at=datetime.now().astimezone().isoformat(),complete=complete,points=points,resources=resource,
                finished=read(WORK/'finished.json'),observation_manifest=manifest,
                prediction_retained_growth_bytes=predictions[-1]['unique_sys_getsizeof_bytes']-predictions[0]['unique_sys_getsizeof_bytes'],
                prediction_Cstar_cache_counts=[p['counts']['Cstar.cache'] for p in predictions],
                final_Cstar_cache_count=final['counts']['Cstar.cache'],
                interpretation='固定した根から届くPython実体のsys.getsizeof合計。共通実体は根の順で先に計上し、独立した所有量としない。型・関数・module等の実行環境、割り当て器の余白、getsizeofとgcに出ないCの領域は含まない。現在常駐・過去最大・番地の控えを分ける。差を候補の量としない。型の本体の大きさをその型が持つ全データの量としない。固定6点のみであり未観測の山を排除しない。速度の比較に使わない。',
                input_sha256={name:sha(WORK/name) for name in ('complete.json','comparison.json','observation_check.json','observations_complete.json','memory_observations.jsonl','resources.jsonl','finished.json')})
    point_columns=('kind','trial_number','unique_objects','unique_sys_getsizeof_bytes','current_rss_before_bytes','current_rss_after_bytes','past_maximum_rss_bytes','observer_bitmap_bytes')
    csv_file('memory_points_01.csv',point_columns,[{k:p[k] for k in point_columns} for p in points])
    csv_file('memory_groups_01.csv',('kind','trial_number','label','newly_reached_objects','newly_reached_bytes'),groups)
    csv_file('memory_types_01.csv',('kind','trial_number','root','type','objects','bytes'),types)
    save(WORK/'analysis.json',result)
    print(json.dumps(dict(analysis=str(WORK/'analysis.json'),samples=len(points),full_gate_passed=True),ensure_ascii=False),flush=True)
except Exception as e:
    p=ROOT/'analysis_STOP_01.json'
    if not p.exists(): save(p,dict(at=datetime.now().astimezone().isoformat(),reason=str(e),repair_not_attempted=True))
    raise
