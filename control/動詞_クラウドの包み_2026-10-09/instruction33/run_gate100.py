"""指示33。実構造検査・通常送信と全資源条件後の、一度の先頭100関門。"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib,json,os,platform,re,shutil,subprocess,sys,time
from run_structural import SERIAL, BIRTH
from run_extra_structural import EXTRA
from birth_census import count_models
from prerequisites37 import gc_off, accepted_structure_scope, priority19_complete
HERE=Path(__file__).resolve().parent

def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def start_counts(raw):
    rows = {}
    for line in raw.splitlines():
        v = line.split(None, 5)
        if len(v) == 6:
            pid, parent, pgid, rss, state, command = v
            rows[int(pid)] = dict(pid=int(pid), ppid=int(parent), pgid=int(pgid),
                rss_bytes=int(rss)*1024, state=state, command=command)
    models, unknown, paused, paused_models = count_models(rows)
    heavy = lambda r: (not r['state'].startswith(('T', 'Z'))
        and any(x in r['command'].split(None, 1)[0].lower() for x in ('python', 'pypy'))
        and 'resource_tracker' not in r['command'] and 'jobs.py' not in r['command']
        and (r['rss_bytes'] >= 100*1024**2 or 'spawn_main' in r['command']))
    return dict(model_process_count=len(models), unknown_active_spawn=len(unknown),
        models=models, paused_models=paused_models, unknown=unknown,
        outside_heavy=sum(heavy(r) for pid, r in rows.items() if pid != os.getpid()),
        counting_rule='実spawn workerとその同命令を継承する出生fork子を一個体ずつ。親/監督/time/tracker/T/Zは稼働模型に加えない。未知spawnは保留。')


def registered(case, clearance=None):
    case=Path(case).resolve();spec=read(case/'spec.json');plan=read(HERE/'plan.json')['commands']
    assert spec['instruction']==33 and spec['ready_to_start'] is True and case.name in plan
    expected=plan[case.name];HEAD=expected['source_commit'];TREE=expected['source_tree']
    assigned=read(HERE/'machine_assignment36.json')
    assert spec['machine']==expected['machine']==assigned['machine']=='Google Cloud d3'
    assert spec['machine_type']==assigned['machine_type']=='c2d-standard-16'
    children=4;measurement_limit=100;partial=True
    assert spec['seed']==1 and spec['flags']==expected['flags'] and spec['source_commit']==HEAD
    assert spec['cpu_start_slots']==6 and spec['model_start_slots']==5 and spec['memory_reservation_gb']>=10
    assert spec['birth_worker_count']==4 and spec['measurement_limit']==100
    assert Path(spec['command'][1])==HERE/'tools/production/prefix_measurement_driver.py'
    assert spec['command'][2]==spec['cwd'] and spec['command'][3]=='100' and spec['command'][6:]==spec['flags']
    assert '--score-logp-e' not in spec['flags']
    gc_off(spec['flags'])
    assert datetime.now(timezone.utc)<datetime.fromisoformat(spec['start_deadline_jst'])
    for name in ('status.json','result.json','pid.json','run.log','resources.jsonl'):
        assert not (case/name).exists(), '同じ過程へ二重起動しない'
    assert not Path(spec['output']).exists()
    claim=read(case/'gate_claim_published.json')
    assert claim['normal_push_succeeded'] and len(claim['commit'])==40 and claim['case_label']==case.name
    assert claim['instruction']==33 and claim['spec_sha256']==sha(case/'spec.json')
    if spec['machine']!='Mac':
        assert claim['Claude_machine_assigned'] is True and len(claim['machine_assignment_commit'])==40
        assert claim['machine_assignment_commit']==assigned['receipt_commit'] and assigned['normal_receipt_push_succeeded'] is True
    assert sha(__file__)==spec['runner_sha256']
    for file,digest in spec['observer_files'].items(): assert sha(file)==digest
    for file,digest in read(HERE/'fixed_tools.json').items(): assert sha(HERE/file)==digest
    structures=read(claim['structural_checks_path'])
    assert structures['source_commit']==read(HERE/'versions.json')['source_commit'] and structures['model_starts']==0
    assert sha(claim['structural_checks_path'])==claim['structural_checks_sha256']
    assert len(claim['structural_checks_published_commit'])==40
    if structures.get('instruction') == 37:
        accepted_structure_scope(claim['structural_checks_path'], structures['source_commit'], SERIAL+EXTRA+BIRTH)
    else:
        assert structures['passed'] is True
        checked_files=[]
        for label in ('serial','extra','birth'):
            entry=structures[label];raw=Path(entry['result_path']);proof=read(raw)
            assert proof['exit_code']==0 and proof['source_commit']==structures['source_commit']
            assert sha(raw)==entry['result_sha256'];checked_files+=proof['files']
        assert set(SERIAL+EXTRA+BIRTH).issubset(checked_files)
        assert any(Path(f).name=='test_compare100.py' for f in checked_files)
    if case.name=='speed_on':
        gate_a=read(claim['comparison_a_path'])
        assert gate_a['mode']=='a' and gate_a['passed'] is True and gate_a['mismatching_files']==0
        assert gate_a['left_spec']['source_commit']==read(HERE/'versions.json')['base_commit']
        assert gate_a['right_spec']['source_commit']==read(HERE/'versions.json')['source_commit']
        assert gate_a['completed_trials']==100 and gate_a['configured_trial_count']==gate_a['horizon']==5000
        assert gate_a['actual_files_excluded']==gate_a['probe_rows_excluded']==0
        assert gate_a['manifest_counts_comparison']['passed']
        assert sha(claim['comparison_a_path'])==claim['comparison_a_sha256'] and len(claim['comparison_a_published_commit'])==40
    source = Path(spec['cwd'])
    for revision, expected in (('HEAD', HEAD), ('HEAD^{tree}', TREE)):
        assert subprocess.check_output(['git', 'rev-parse', revision], cwd=source, text=True).strip() == expected
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source)
    linux = sys.platform.startswith('linux')
    if linux:
        assert sys.version_info[:2] == (3, 12) and platform.machine() in ('x86_64', 'AMD64')
        proof = read(clearance)
        assert 0 <= time.time()-proof['checked_epoch'] <= 60
        assert proof['spec_sha256'] == sha(case/'spec.json') and proof['memory_reservation_gb'] == spec['memory_reservation_gb']
        assert proof['memory_admission_ok'] and proof['swap_stable_10min'] and proof['thermal_ok'] and proof['warning'] is False
        limit = proof['cpu_budget']
        assert limit == proof['physical_cpu_count']-2 and len(os.sched_getaffinity(0)) >= children+2
        boot = hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        assert proof['machine_boot_sha256'] == boot
        if not partial:
            assert comparison['machine_boot_sha256'] == prefix_gate['machine_boot_sha256'] == boot
        thermal, swap = '既存受付の最新確認', proof
        time_args = ['/usr/bin/time', '-v', '-o', str(case/'time.log')]
    else:
        assert sys.platform == 'darwin'
        limit = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'], text=True))-2
        boot = hashlib.sha256(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'kern.boottime'])).hexdigest()
        thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True)
        assert 'No thermal warning level has been recorded' in thermal
        import re
        assert not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+', thermal)
        swap = (Path.home()/'jobs/swap.tsv').read_text().splitlines()[-11:]
        time_args = ['/usr/bin/time', '-l']
    if case.name=='speed_on':
        assert gate_a['machine_boot_sha256']==boot
    assert sha(claim['priority19_complete_path']) == claim['priority19_complete_sha256']
    priority19_complete(claim['priority19_complete_path'], spec['machine'], boot)
    # ここだけが開始直前の全機械ps。開始後の常駐停止/再開機構は作らない。
    raw = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=,stat=,args='], text=True)
    counts = start_counts(raw)
    # 指示32の直接承認。専用Google Cloud機械だけを既存受付の確認で特定する。
    dedicated_gcp = linux and proof.get('dedicated_google_cloud_gate_and_production_machine') is True
    model_limit = limit if dedicated_gcp else 8
    assert counts['model_process_count']+children+1 <= model_limit and counts['unknown_active_spawn'] == 0
    assert counts['outside_heavy']+children+2 <= limit
    free = shutil.disk_usage(case).free
    assert free >= 20*2**30
    machine = dict(at=datetime.now().astimezone().isoformat(), machine_boot_sha256=boot,
        cpu_limit=limit, reserved_cpu_slots=children+2, reserved_model_slots=children+1, memory_reservation_gb=spec['memory_reservation_gb'],
        thermal=thermal, swap=swap, free_disk_bytes=free, processes=raw, **counts)
    (case/'machine_before_start.json').write_text(json.dumps(machine, ensure_ascii=False, indent=2)+'\n')
    start, epoch, peak = time.perf_counter(), time.time(), 0
    env = dict(os.environ, PYTHONHASHSEED='0')
    for key in ('LC_ALL', 'LANG', 'LC_CTYPE'):
        env.pop(key, None)
    with (case/'run.log').open('x') as log, (case/'resources.jsonl').open('x') as samples:
        child = subprocess.Popen([*time_args, *spec['command']], cwd=source, env=env,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (case/'pid.json').write_text(json.dumps(dict(pid=child.pid, pgid=child.pid))+'\n')
        (case/'status.json').write_text(json.dumps(dict(state='running', production_started=True,
            at=datetime.now().astimezone().isoformat(), runner_pid=os.getpid(), model_group=child.pid))+'\n')
        warnings = set()
        while child.poll() is None:
            # Linuxではこの模型のsession、Macでは同じ群だけを読む。
            selection = '-s' if linux else '-g'
            own = subprocess.run(['/bin/ps', selection, str(child.pid), '-o', 'pid=,ppid=,rss=,stat=,args='], capture_output=True, text=True)
            rss = sum(int(line.split()[2])*1024 for line in own.stdout.splitlines() if len(line.split()) >= 4)
            peak = max(peak, rss)
            row = dict(at=datetime.now().astimezone().isoformat(), own_group=child.pid,
                       own_ps=own.stdout, own_rss_bytes=rss, free_disk_bytes=shutil.disk_usage(case).free)
            samples.write(json.dumps(row)+'\n'); samples.flush()
            for condition, reason in ((rss > spec['memory_reservation_gb']*2**30, '群RSSが受付見込みを超えた'),
                (row['free_disk_bytes'] < 18.5*2**30, '原容量警告線を下回った')):
                if condition and reason not in warnings:
                    with (case/'resource_warnings.jsonl').open('a') as f:
                        f.write(json.dumps(dict(reason=reason, **row, production_stopped=False), ensure_ascii=False)+'\n')
                    warnings.add(reason)
            time.sleep(10)
        rc = child.wait()
    result = dict(exit_code=rc, started_epoch=epoch, finished_epoch=time.time(),
        wall_seconds=time.perf_counter()-start, rss_group_peak_bytes=peak,
        configured_trial_count=5000, horizon=5000, source_commit=HEAD,
        output_bytes=sum(p.stat().st_size for p in Path(spec['output']).rglob('*') if p.is_file()),
        warnings=sorted(warnings), new_stop_resume_monitor=False,
        measurement_maxrss_raw_unit='KiB' if linux else 'B')
    (case/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    assert rc == 0, ('原終了コード', rc)
    manifest = [json.loads(x) for x in (Path(spec['output'])/'manifest.jsonl').read_text().splitlines()]
    assert len(manifest) == 1 and not manifest[0].get('error')
    assert manifest[0]['trial_count'] == measurement_limit
    marker = read(Path(spec['output'])/'measurement/partial_done.json')
    assert marker['completed_trials'] == manifest[0]['completed_trials'] == measurement_limit
    assert marker['configured_trial_count'] == marker['horizon'] == 5000
    assert marker['full_5000_completed'] is False
    probe = manifest[0]['probeworld']
    checks = measurement_limit//100
    assert probe['probes'] == 48 and probe['rows'] == 48*checks and probe['fingerprint_checks'] == checks
    assert len(probe['attention_checks']) == checks
    assert all(x['passed'] and x['attention_before'] == x['attention_after']
               and x['questions_before'] == x['questions_after'] for x in probe['attention_checks'])
    times = [json.loads(x) for x in (Path(spec['output'])/'timing100.jsonl').read_text().splitlines()]
    assert [x['completed_trials'] for x in times] == list(range(100, measurement_limit+1, 100))
    (case/'status.json').write_text(json.dumps(dict(state=f'completed_partial{measurement_limit}',
        completed_trials=measurement_limit, configured_trial_count=5000, horizon=5000,
        full_5000_completed=False, flagged_result_provisional=True, runner_pid=os.getpid()))+'\n')
    return 0


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case'); p.add_argument('--clearance')
    a = p.parse_args()
    raise SystemExit(registered(a.case, a.clearance))
