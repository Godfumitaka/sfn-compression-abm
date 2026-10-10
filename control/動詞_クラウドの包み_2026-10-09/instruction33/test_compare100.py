"""人工の短い記録だけ。模型走行をせず、全内容とP10の比較の拒否境界を検査する。"""
from pathlib import Path
import json
import pytest
import compare100 as C


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,separators=(',',':'))+'\n')


def fixtures(tmp_path,mode):
    plan=json.loads((Path(C.__file__).parent/'plan.json').read_text())['commands']
    labels=('baseline6e4','speed_off') if mode=='a' else ('speed_off','speed_on')
    cases=[]
    for label in labels:
        case=tmp_path/label;out=case/'output';case.mkdir();cases.append(case)
        spec={**plan[label],'output':str(out)};put(case/'spec.json',spec)
        put(case/'result.json',dict(exit_code=0,source_commit=spec['source_commit'],wall_seconds=2))
        put(case/'machine_before_start.json',dict(machine_boot_sha256='synthetic-same-machine'))
        (case/'time.log').write_text('synthetic time fixture only\n')
        marker=dict(source_commit=spec['source_commit'],completed_trials=100,configured_trial_count=5000,horizon=5000,full_5000_completed=False)
        put(out/'measurement/partial_done.json',marker)
        probe=dict(probes=48,rows=48,fingerprint_checks=1,attention_checks=[dict(passed=True,
            attention_before=1,attention_after=1,questions_before=2,questions_after=2)])
        put(out/'manifest.jsonl',dict(**marker,trial_count=100,probeworld=probe,strictpc={'n':1},v39={'n':1},stage2={'seconds':3}))
        for root in ('ledgers','side','attention','evictions','stage2'):
            put(out/root/'record.jsonl',dict(order=[2,1],value=1))
        (out/'side/probe.probe.jsonl').write_bytes(b'{"q":1}\n'*48)
        put(out/'timing100.jsonl',dict(completed_trials=100,user_cpu_seconds=1,system_cpu_seconds=1))
        boundary=out/'comparison_checkpoints/completed_0100'
        put(boundary/'confirmed.json',dict(confirmed=True,completed_trials=100,last_trial=99,configured_trial_count=5000,
            horizon=5000,forbidden_reads=0,guard_forbidden_reads=0 if label=='speed_on' else None))
        for name in ('state.json','rng.json','cache_sme.json'):
            put(boundary/name,dict(order=[2,1]))
        put(boundary/'cache_posthoc_p10.json',{'cache':[99]})
        put(boundary/'cache_raw.json',{'cache':[99]} if label=='speed_on' else {'cache':[0,99]})
        if label=='speed_on':
            put(case/'p10_cache_guard.jsonl.gz.summary.json',dict(native_loop_returned=True,forbidden_reads=0))
    return cases


def test_old_version_and_new_off_all_bytes(tmp_path):
    a,b=fixtures(tmp_path,'a');dest=tmp_path/'results/speed100_a.json'
    assert C.compare(a,b,dest,'a')==0
    value=C.read(dest)
    assert value['passed'] and value['mismatching_files']==0 and value['probe_rows_excluded']==0


def test_p10_compares_off_posthoc_and_on_actual_cache(tmp_path):
    a,b=fixtures(tmp_path,'b');dest=tmp_path/'results/speed100_b.json'
    assert C.compare(a,b,dest,'b')==0
    assert C.read(dest)['state_rng_cache_files'][-1]['left_read']=='cache_posthoc_p10.json'


def test_one_original_byte_difference_is_failure_with_example(tmp_path):
    a,b=fixtures(tmp_path,'a');(b/'output/side/record.jsonl').write_bytes(b'{"order":[1,2],"value":1}\n')
    dest=tmp_path/'results/speed100_a.json';assert C.compare(a,b,dest,'a')==1
    row=next(x for x in C.read(dest)['files'] if x['path']=='side/record.jsonl')
    assert not row['equal'] and row['mismatching_bytes']>0 and row['example']


def test_probe_row_is_compared_and_cannot_be_excluded(tmp_path):
    a,b=fixtures(tmp_path,'a');(b/'output/side/probe.probe.jsonl').write_bytes(b'{"q":2}\n'*48)
    dest=tmp_path/'results/speed100_a.json';assert C.compare(a,b,dest,'a')==1
    assert C.read(dest)['probe_rows_excluded']==0


def test_dropped_cache_read_is_rejected(tmp_path):
    a,b=fixtures(tmp_path,'b');put(b/'p10_cache_guard.jsonl.gz.summary.json',dict(native_loop_returned=True,forbidden_reads=1))
    dest=tmp_path/'results/speed100_b.json'
    with pytest.raises(AssertionError):C.compare(a,b,dest,'b')
    assert not dest.exists()


def test_prior_failed_gate_is_never_overwritten_by_later_match(tmp_path):
    a,b=fixtures(tmp_path,'a');dest=tmp_path/'results/speed100_a.json'
    put(dest.parent/'speed100_prior.json',dict(passed=False))
    assert C.compare(a,b,dest,'a')==1
    assert C.read(dest)['prior_mismatch'] is True
    with pytest.raises(AssertionError):C.compare(a,b,dest,'a')
