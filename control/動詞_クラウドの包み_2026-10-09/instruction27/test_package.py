"""模型を起動せず、命令・記録の読取境界・開始条件を確認する。"""
from pathlib import Path
import ast
import gzip
import hashlib
import json
import sys
import zlib
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from checkpoint_digest import chunks, digest, compare_file, compare_streams, normalized
from run_registered import start_counts


def test_all_40_only_seed_B_price_and_birth_children_change():
    flags = json.loads((HERE/'mac_flags.json').read_text())['flags']
    plan = json.loads((HERE/'plan.json').read_text())
    assert len(plan['commands']) == 40
    groups = {'#19':(range(1, 11), '0.00035129738499384776'),
              '#19L25':(range(1, 6), '0.00010926774617357411'),
              '#19L90':(range(1, 6), '0.00699330963316462')}
    for arm, (seeds, price) in groups.items():
        specs = [s for s in plan['commands'].values() if s['arm'] == arm]
        assert [(s['seed'], s['birth_worker_count']) for s in specs] == [(seed, n) for seed in seeds for n in (4,20)]
        for s in specs:
            expected = list(flags)
            expected[expected.index('--seeds')+1] = str(s['seed'])
            expected[expected.index('--v39-price')+1] = price
            children = s['birth_worker_count']
            expected[expected.index('--stage2-birth-workers')+1] = str(children)
            assert s['flags'] == expected and s['command'][5:] == expected
            assert not s['ready_to_start'] and not s['cloud_start_authorized']
            assert s['cpu_start_slots'] == children+2 and s['model_start_slots'] == children+1
            assert s['memory_reservation_gb'] == 2*(children+1)
            assert s['hold_for_Astra_model_cap_approval'] == (children==20) and s['model_cap']==8


def test_prefix_ignores_only_future_rows_and_plain_old_gz_name(tmp_path):
    data = b'{"trial":0,"value":1}\n'*90000
    old, new = tmp_path/'old.gz', tmp_path/'new.gz'
    old.write_bytes(data)
    new.write_bytes(gzip.compress(data+b'{"trial":500,"future":true}\n'))
    proof = digest(chunks(old))
    result = compare_file('side/x.gz', old, new, proof, proof)
    assert result['equal'] and result['mismatching_bytes'] == 0
    assert new.read_bytes().startswith(b'\x1f\x8b') and old.read_bytes() == data


def test_partial_gzip_flush_and_concatenated_members(tmp_path):
    compressor = zlib.compressobj(wbits=31)
    data = b'first\n'*120000
    raw = compressor.compress(data)+compressor.flush(zlib.Z_SYNC_FLUSH)
    path = tmp_path/'part.gz';path.write_bytes(raw)
    assert digest(chunks(path, compressed=True, limit=len(data)))['sha256'] == hashlib.sha256(data).hexdigest()
    with pytest.raises(AssertionError):
        list(chunks(path, compressed=True))
    path.write_bytes(gzip.compress(data)+gzip.compress(b'last\n'))
    assert digest(chunks(path, compressed=True))['lines'] == 120001


def test_payload_mismatch_retained_with_exact_example_and_count(tmp_path):
    a, b = tmp_path/'a.gz', tmp_path/'b.gz'
    a.write_bytes(b'{"trial":99,"kind":"post"}\n')
    b.write_bytes(gzip.compress(b'{"trial":99,"kind":"pre"}\n'))
    x, y = digest(chunks(a)), digest(chunks(b, compressed=True))
    result = compare_file('side/states.gz', a, b, x, y)
    assert not result['equal'] and result['mismatching_bytes'] > 0
    assert 'post' in result['example']['left'] and 'pre' in result['example']['right']


def test_proof_corruption_stops_instead_of_equal(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.write_bytes(b'keep\n'); b.write_bytes(b'keep\n')
    proof = digest(chunks(a)); bad = {**proof, 'sha256':'0'*64}
    with pytest.raises(AssertionError):
        compare_file('side/a', a, b, proof, bad)
    with pytest.raises(AssertionError):
        digest(chunks(b, limit=100))


def test_time_only_and_original_order_and_whitespace_retained():
    a = b'{"trial":1,"TIME":{"seconds":1.25},"count":7}\n'
    b = b'{"trial":1,"TIME":{"seconds":9.75},"count":7}\n'
    result = compare_streams(normalized(iter([a]), 'stage2/a.jsonl'), normalized(iter([b]), 'stage2/a.jsonl'))
    assert result['equal']
    assert not compare_streams(iter([a]), iter([b]))['equal']
    changed = b.replace(b'"count":7', b'"count":8')
    assert not compare_streams(normalized(iter([a]), 'stage2/a.jsonl'), normalized(iter([changed]), 'stage2/a.jsonl'))['equal']
    reordered = b'{"count":7,"trial":1,"TIME":{"seconds":9.75}}\n'
    assert not compare_streams(normalized(iter([a]), 'stage2/a.jsonl'), normalized(iter([reordered]), 'stage2/a.jsonl'))['equal']


def test_chunk_alignment_and_trailing_bytes():
    assert compare_streams(iter([b'abc', b'def\n']), iter([b'ab', b'cdef\n']))['equal']
    x = compare_streams(iter([b'abcd\n']), iter([b'abxd\n']))
    assert x['mismatching_bytes'] == 1 and x['first_mismatch_byte'] == 2
    assert compare_streams(iter([b'ab\n']), iter([b'ab\nxx\n']))['mismatching_bytes'] == 3


def test_real_worker_census_does_not_add_parent_supervisor_tracker_T_Z():
    raw = '''100 1 100 1000 S python3 /x/measurement_driver.py
101 100 100 1000 S python3 -c resource_tracker
102 100 100 1000 R python3 -c spawn_main
103 102 100 1000 R python3 -c spawn_main
104 102 100 1000 T python3 -c spawn_main
105 102 100 1000 Z python3 -c spawn_main
106 1 100 1000 R python3 -c spawn_main
107 1 100 1000 S /usr/bin/time -l python3 driver.py
'''
    value = start_counts(raw)
    assert value['model_process_count'] == 2 and value['unknown_active_spawn'] == 1
    assert {r['pid'] for r in value['paused_models']} == {104, 105}


def test_observer_is_fixed_instruction26_bytes():
    original = HERE.parent/'instruction26_production/tools'
    for p in (HERE/'tools').rglob('*.py'):
        assert p.read_bytes() == (original/p.relative_to(HERE/'tools')).read_bytes()


def test_runner_never_stops_or_resumes_running_production_and_guards_before_launch():
    source = (HERE/'run_registered.py').read_text()
    assert 'SIGSTOP' not in source and 'SIGCONT' not in source and 'killpg' not in source
    assert source.index("assert counts['model_process_count']+children+1 <= 8") < source.index('child = subprocess.Popen')
    assert source.index("assert counts['outside_heavy']+children+2 <= limit") < source.index('child = subprocess.Popen')
    assert source.index("assert spec['ready_to_start'] is True") < source.index('child = subprocess.Popen')
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in ('signal', 'kill', 'killpg', 'terminate') for node in ast.walk(tree))


def test_manifest_same_original_function_structure():
    old = (HERE.parent/'instruction22_birth/compare_probe100.py').read_text()
    new = (HERE/'manifest_counts.py').read_text()
    fn = lambda s: next(n for n in ast.parse(s).body if isinstance(n, ast.FunctionDef) and n.name == 'manifest_counts')
    assert ast.dump(fn(old)) == ast.dump(fn(new))


def test_start_waiter_resources_must_allow_five_models_and_six_cpu(monkeypatch):
    import wait_for_start as waiter
    import types
    table = {'models':4, 'thermal':'No thermal warning level has been recorded\n'}
    def output(argv, **kw):
        if argv[0] == '/bin/ps':
            return ''.join(f'{100+i*2} 1 {100+i*2} 1000 S python3 /x/measurement_driver.py\n'
                 f'{101+i*2} {100+i*2} {100+i*2} 110000 R python3 -c spawn_main\n' for i in range(table['models']))
        if 'hw.physicalcpu' in argv:
            return '10\n'
        return table['thermal']
    monkeypatch.setattr(waiter.subprocess, 'check_output', output)
    monkeypatch.setattr(waiter.shutil, 'disk_usage', lambda p:types.SimpleNamespace(free=25*2**30))
    assert not waiter.available_snapshot()['ready']
    table['models'] = 2
    assert waiter.available_snapshot()['ready']
    table['thermal'] += 'CPU_Speed_Limit = 50\n'
    assert not waiter.available_snapshot()['ready']


def test_waiter_never_claims_before_new_inbox_queue_and_real_resource_checks():
    s = (HERE/'wait_for_start.py').read_text()
    assert s.index("night.fetch_report()") < s.index("spec['ready_to_start'] = True")
    assert s.index("max(instructions) not in (27, 28)") < s.index("spec['ready_to_start'] = True")
    assert s.index("eligible[0]['row'] != '19p'") < s.index("spec['ready_to_start'] = True")
    assert s.index("if not value['ready']") < s.index("spec['ready_to_start'] = True")
    assert s.index('assert pushed.returncode == 0') < s.index("save('launcher_pid.json'")
    assert 'SIGSTOP' not in s and 'SIGCONT' not in s and 'killpg' not in s


def test_three_gate_commands_keep5000_prefix100_same_fixed_observer():
    plan = json.loads((HERE/'plan.json').read_text())
    base = json.loads((HERE/'mac_flags.json').read_text())['flags']
    assert list(plan['gate_commands']) == ['gate100_birth0','gate100_birth4','gate100_birth20']
    assert hashlib.sha256((HERE/'gate/measurement_driver.py').read_bytes()).hexdigest() == '6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4'
    for d in plan['gate_commands'].values():
        expected = list(base); expected[expected.index('--stage2-birth-workers')+1] = str(d['birth_worker_count'])
        assert d['flags'] == expected and d['command'][6:] == expected
        assert d['command'][3] == '100' and d['measurement_limit'] == 100
        assert d['configured_trial_count'] == d['horizon'] == 5000 and not d['full_5000_requested']
        assert not d['ready_to_start'] and not d['cloud_start_authorized']


def synthetic_gate_case(tmp_path, children):
    from gate_compare import CELL
    case = tmp_path/f'birth{children}'; out=case/'output'; out.mkdir(parents=True)
    flags=json.loads((HERE/'mac_flags.json').read_text())['flags']
    flags[flags.index('--stage2-birth-workers')+1]=str(children)
    head='6e4bcba94874a4f49c5a1bae11d385534504e2e5'
    spec=dict(source_commit=head,measurement_limit=100,seed=1,flags=flags,output=str(out))
    result=dict(exit_code=0,source_commit=head,measurement_maxrss_raw_unit='KiB',wall_seconds=10)
    marker=dict(completed_trials=100,configured_trial_count=5000,horizon=5000,full_5000_completed=False,source_commit=head)
    manifest={**marker,'probeworld':dict(probes=48,rows=48,fingerprint_checks=1,attention_checks=[dict(passed=True,attention_before=1,attention_after=1,questions_before=1,questions_after=1)]),
        'strictpc':{'use_calls':{'試験':48}},'v39':{'L_unseen_name':8},'stage2':{'TIME':{'seconds':10}}}
    for name,value in [('spec.json',spec),('result.json',result),('machine_before_start.json',{'machine_boot_sha256':'same'})]:
        (case/name).write_text(json.dumps(value,ensure_ascii=False))
    (out/'measurement').mkdir();(out/'measurement/partial_done.json').write_text(json.dumps(marker))
    (out/'manifest.jsonl').write_text(json.dumps(manifest,ensure_ascii=False)+'\n');(case/'time.log').write_text('原GNU time\n')
    required=[f'attention/{CELL}/seed001.jsonl.gz',f'evictions/{CELL}/seed001.keys.jsonl.gz',f'ledgers/cells/{CELL}/seed001.jsonl.gz']
    required += [f'side/{CELL}/seed001'+suffix for suffix in ('.answers.csv','.jsonl','.routing.jsonl','.sme.jsonl.gz','.sme.states.jsonl.gz','.probe.jsonl')]
    for name in required:
        f=out/name;f.parent.mkdir(parents=True,exist_ok=True)
        payload=b'{"trial":99,"kind":"post"}\n'*(48 if f.name.endswith('.probe.jsonl') else 1)
        f.write_bytes(gzip.compress(payload) if f.suffix=='.gz' else payload)
    return case


def test_gate_streams_all_files_and_probe_rows_keeps_first_failure(tmp_path):
    from gate_compare import compare,CELL
    off=synthetic_gate_case(tmp_path,0); four=synthetic_gate_case(tmp_path,4); twenty=synthetic_gate_case(tmp_path,20)
    folder=tmp_path/'comparisons'; dest=folder/'gate_off_vs_4.json'
    target=four/f'output/side/{CELL}/seed001.probe.jsonl'; raw=target.read_bytes()
    target.write_bytes(raw.replace(b'"post"',b'"pre"',1))
    assert compare(off,four,dest) == 1
    evidence=json.loads(dest.read_text());assert evidence['mismatching_files']==1 and evidence['probe_rows_excluded']==0
    bad=next(r for r in evidence['files'] if not r['equal'])
    assert 'post' in bad['example']['left'] and 'pre' in bad['example']['right']
    assert compare(off,twenty,folder/'gate_off_vs_20.json')==1
    assert json.loads((folder/'gate_off_vs_20.json').read_text())['prior_mismatch']
    with pytest.raises(AssertionError):compare(off,four,dest)


def test_gate_manifest_researcher_mismatch_is_not_ignored(tmp_path):
    from gate_compare import compare
    off=synthetic_gate_case(tmp_path,0); on=synthetic_gate_case(tmp_path,4)
    path=on/'output/manifest.jsonl';value=json.loads(path.read_text());value['strictpc']['use_calls']['試験']=49
    path.write_text(json.dumps(value,ensure_ascii=False)+'\n')
    dest=tmp_path/'gate_off_vs_4.json';assert compare(off,on,dest)==1
    assert not json.loads(dest.read_text())['manifest_counts_comparison']['passed']


def test_m1_reads_existing301_original_record_without_applicable_field(tmp_path):
    from m1_at501 import extract
    cases=[]
    for seed in (1,2):
        case=tmp_path/f'seed{seed}';out=case/'output';folder=out/'comparison_checkpoints';folder.mkdir(parents=True)
        (case/'spec.json').write_text(json.dumps(dict(source_commit='same',output=str(out),flags=['--seeds',str(seed)])))
        cases.append(case)
    destination=tmp_path/'m1.json'
    with pytest.raises(FileNotFoundError):extract(*cases,destination)
    assert not destination.exists()
    for case in cases:
        (case/'output/comparison_checkpoints/m1_at_trial500.json').write_text(json.dumps(dict(zero_based=True,first_trial=200,last_trial=500,trials=301,stop_criterion=False)))
    result=extract(*cases,destination)
    assert result['no_stop_criterion'] and result['claude_confirmation_required'] and not result['seeds3_to10_may_start']
    assert not result['automatic_stop']


def test_cloud_pilot_after_same_machine_gate_before_M1_for_seeds3_to10():
    text=(HERE/'run_registered.py').read_text()
    launch=text.index('child = subprocess.Popen')
    for guard in ("claim['cloud_gate_comparison_path']", "comparison['passed']", "comparison['machine_boot_sha256'] == boot",
                  "claim['cloud_pilot_authorized'] if spec['seed'] in (1, 2) else claim['Claude_M1_confirmed']"):
        assert text.index(guard)<launch
