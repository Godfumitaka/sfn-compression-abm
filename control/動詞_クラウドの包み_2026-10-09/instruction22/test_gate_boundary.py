"""新しい並列の模型数とmanifestの数えの比較。学習模型は起動しない。"""
from pathlib import Path
import json
import pytest
from birth_census import count_models
from compare_probe100 import manifest_counts
from pair_common import read, ROOT, validate_spec


def row(pid,ppid,command,state='R'):
    return dict(pid=pid,ppid=ppid,command=command,state=state,rss_bytes=123)


def test_nested_fork_workers_are_actual_models_unknown_not_ignored():
    spawn='python3 -c from multiprocessing.spawn import spawn_main; spawn_main()'
    rows={1:row(1,0,'python3 /path/measurement_driver.py source'),2:row(2,1,spawn),
          3:row(3,2,spawn),4:row(4,3,spawn),5:row(5,0,spawn),6:row(6,2,spawn,'T')}
    models,unknown,paused,paused_models=count_models(rows)
    assert {r['pid'] for r in models}=={2,3,4}
    assert {r['pid'] for r in unknown}=={5}
    assert {r['pid'] for r in paused_models}=={6}
    assert {r['pid'] for r in paused}=={6}


def manifests(tmp_path,change):
    paths=[tmp_path/'left',tmp_path/'right']
    base=dict(strictpc=dict(reasons={'a':1},use_calls={'birth':7},use_dropped={'birth':3}),
              v39=dict(L_unseen_name=9),stage2=dict(seconds=1,scored_seats=2),
              verbtiming=dict(checkpoints=0,elapsed_seconds=1),histrole=dict(births=1))
    for i,p in enumerate(paths):
        p.mkdir();value=json.loads(json.dumps(base));
        if i:change(value)
        (p/'manifest.jsonl').write_text(json.dumps(value,ensure_ascii=False)+'\n')
    return paths


def test_only_allowed_time_differs(tmp_path):
    def change(x):x['stage2']['seconds']=123.;x['verbtiming']['elapsed_seconds']=321.
    result=manifest_counts(*manifests(tmp_path,change))
    assert result['passed'] and result['mismatching_files']==0


@pytest.mark.parametrize('field', ['reasons','use_calls','use_dropped'])
def test_strictpc_research_counter_difference_stops(tmp_path,field):
    def change(x):x['strictpc'][field][next(iter(x['strictpc'][field]))]+=1
    result=manifest_counts(*manifests(tmp_path,change))
    assert not result['passed']
    assert result['mismatching_files']==1
    assert next(r for r in result['files'] if not r['equal'])['path']=='manifest:strictpc'


def test_unseen_name_difference_stops(tmp_path):
    def change(x):x['v39']['L_unseen_name']+=1
    assert not manifest_counts(*manifests(tmp_path,change))['passed']


def test_other_diagnostic_not_dropped(tmp_path):
    def change(x):x['histrole']['births']+=1
    assert not manifest_counts(*manifests(tmp_path,change))['passed']


def test_same_version_flags_and_resource_slots():
    for mode,n in (('off',0),('on',4)):
        spec=read(ROOT/('probe100_'+mode)/'spec.json')
        validate_spec(spec,mode)
        assert spec['model_start_slots']==n+1
        assert spec['cpu_start_slots']==n+2
        assert spec['flags'][-4:]==['--verb-snap-append-only','on','--stage2-birth-workers',str(n)]
        assert '--score-logp-e' in spec['flags']
