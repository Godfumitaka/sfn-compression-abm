"""指示34。受付の内側の一走行。開始前に確認し、開始後は自分の群を読む。"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from birth_census import count_models

HERE = Path(__file__).resolve().parent
HEAD = '6e4bcba94874a4f49c5a1bae11d385534504e2e5'
TREE = 'b4dd25d03844e81bf09de3421f444081a50d5b35'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    case = Path(case).resolve()
    spec = read(case/'spec.json')
    assert spec['ready_to_start'] is True and spec['instruction'] == 34
    children = spec['birth_worker_count']
    assert children in (0, 4, 20)
    assert spec['source_commit'] == HEAD and spec['cpu_start_slots'] == children+2
    assert spec['model_start_slots'] == children+1 and spec['memory_reservation_gb'] >= 2*(children+1)
    expected = list(read(HERE/'mac_flags.json')['flags'])
    for flag in ('--seeds', '--v39-price', '--stage2-birth-workers'):
        expected[expected.index(flag)+1] = spec['flags'][spec['flags'].index(flag)+1]
    assert spec['flags'] == expected
    measurement_limit = spec['measurement_limit']
    assert measurement_limit in (100, 1000)
    partial = measurement_limit == 100
    assert Path(spec['command'][1]) == HERE/'tools/production/prefix_measurement_driver.py'
    assert spec['command'][2] == spec['cwd'] and spec['command'][3] == str(measurement_limit)
    assert spec['command'][6:] == spec['flags']
    if spec['machine'] == 'x86':
        plan = read(HERE/'plan.json')
        draft = {**plan['partial_commands'], **plan['prefix_gate_commands']}[case.name]
        assert spec['flags'] == draft['flags'] and spec['seed'] == draft['seed'] and spec['arm'] == draft['arm']
    else:
        assert partial and spec['seed'] == 1 and spec['arm'] == '#19-prefix-gate'
    assert '--score-logp-e' not in spec['flags']
    for flag, value in (('--verb-snap-append-only', 'on'), ('--stage2-birth-workers', str(children)),
                        ('--e-price', '0.01873710622997919'), ('--match-eps', '0')):
        assert spec['flags'][spec['flags'].index(flag)+1] == value
    assert datetime.now(timezone.utc) < datetime.fromisoformat(spec['start_deadline_jst'])
    for name in ('status.json', 'result.json', 'pid.json', 'run.log', 'resources.jsonl'):
        assert not (case/name).exists(), '既存監督や出力へ二重投入しない'
    assert not Path(spec['output']).exists()
    claim = read(case/'queue_claim_published.json')
    assert claim['normal_push_succeeded'] and claim['case_label'] == case.name
    assert len(claim['commit']) == 40 and claim['machine'] == spec['machine']
    assert claim['spec_sha256'] == sha(case/'spec.json')
    assert sha(__file__) == spec['runner_sha256']
    for file, digest in spec['observer_files'].items():
        assert sha(file) == digest
    for file, digest in read(HERE/'fixed_tools.json').items():
        assert sha(HERE/file) == digest
    for label in ('20', '22'):
        gate = read(HERE/f'evidence/comparison{label}_approved.json')
        assert gate['passed'] and gate['mismatching_files'] == 0
        assert gate['manifest_counts_comparison']['passed']
    preparation = read(HERE/'preparation_checks.json')
    assert preparation['passed'] and preparation['model_starts'] == 0
    prefix_preparation = read(HERE/'prefix_preparation_checks.json')
    assert prefix_preparation['passed'] and prefix_preparation['model_starts'] == 0
    if spec['machine'] == 'x86':
        if partial:
            assert claim['cloud_gate_authorized']
        else:
            if spec['arm'] == '#19':
                assert claim['cloud_pilot_authorized'] if spec['seed'] in (1, 2) else claim['Claude_M1_confirmed']
            else:
                assert claim['Astra_cost_approved']
            comparison = read(claim['cloud_gate_comparison_path'])
            assert comparison['passed'] and comparison['child_workers'] == children
            assert comparison['source_commit'] == HEAD and comparison['actual_files_excluded'] == comparison['probe_rows_excluded'] == 0
            assert comparison['manifest_counts_comparison']['passed'] and len(claim['cloud_gate_published_commit']) == 40
            assert sha(claim['cloud_gate_comparison_path']) == claim['cloud_gate_comparison_sha256']
            gate_flags = list(comparison['on_flags'])
            for flag in ('--seeds', '--v39-price'):
                gate_flags[gate_flags.index(flag)+1] = spec['flags'][spec['flags'].index(flag)+1]
            assert gate_flags == spec['flags']
    if not partial:
        prefix_gate = read(claim['prefix_gate_comparison_path'])
        assert prefix_gate['passed'] and prefix_gate['source_commit'] == HEAD
        assert prefix_gate['child_workers'] == children and prefix_gate['entry_limit'] == 100
        assert prefix_gate['actual_files_excluded'] == prefix_gate['probe_rows_excluded'] == 0
        assert prefix_gate['manifest_counts_comparison']['passed']
        assert sha(claim['prefix_gate_comparison_path']) == claim['prefix_gate_comparison_sha256']
        assert len(claim['prefix_gate_published_commit']) == 40
        prefix_flags = list(prefix_gate['on_flags'])
        prefix_flags[prefix_flags.index('--seeds')+1] = str(spec['seed'])
        assert prefix_flags == spec['flags']
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
    if spec['machine'] == 'Mac' and not partial:
        baseline = Path(spec['baseline_case'])
        original = read(baseline/'spec.json')
        assert original['source_commit'] == '9c9dd0e650f765ccdadca6029e81da4efc3cc619'
        assert spec['flags'] == original['flags'] + ['--verb-snap-append-only', 'on', '--stage2-birth-workers', '4']
        assert sha(baseline/'spec.json') == spec['baseline_spec_sha256']
        original_start = read(baseline/'machine_before_start.json')
        assert original_start['physical_memory_bytes'] == int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'], text=True))
        group = read(baseline/'pid.json')['pgid']
        own_original = subprocess.run(['/bin/ps', '-g', str(group), '-o', 'pid=,ppid=,rss=,stat=,args='], capture_output=True, text=True)
        evidence = dict(baseline_case=str(baseline), baseline_spec_sha256=sha(baseline/'spec.json'),
            original_start=original_start, original_pid=read(baseline/'pid.json'),
            original_own_ps=own_original.stdout, original_result=read(baseline/'result.json') if (baseline/'result.json').exists() else None,
            machine_boot_sha256=boot, basis='指示27が指定したこのMacの既存case、元開始記録・原PIDの自群確認。旧開始にはboot欄がないため後から作らない。')
        assert own_original.stdout.strip() or evidence['original_result'] is not None
        (case/'baseline_same_machine.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
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
    if measurement_limit == 1000:
        for n in (500, 1000):
            confirmed = read(Path(spec['output'])/f'comparison_checkpoints/completed_{n:04d}/confirmed.json')
            assert confirmed['confirmed'] is True and confirmed['completed_trials'] == n
            assert confirmed['last_trial'] == n-1 and confirmed['configured_trial_count'] == confirmed['horizon'] == 5000
        m1 = read(Path(spec['output'])/'comparison_checkpoints/m1_at_trial500.json')
        assert m1['first_trial'] == 200 and m1['last_trial'] == 500 and m1['trials'] == 301
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
