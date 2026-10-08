"""指示34。Macの指定五模型と三比較だけ。自然終了を待ち、再投入しない。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from compare_records import tree, compare
from reference_observation import convert

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('readonly_resources', ROOT.parent / 'instruction19_speed_gate/gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def write(name, data, exclusive=True):
    p = ROOT / name
    if exclusive:
        with p.open('x') as out:
            out.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    else:
        temp = Path(str(p) + '.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        temp.replace(p)


def plan():
    return json.loads((ROOT / 'preparation_manifest.json').read_text())


def deadline():
    if G.stamp()[:19] >= '2026-10-11T09:00:00':
        raise RuntimeError('期限後の新規投入・再開無し')


def verify():
    p = plan()
    assert p['comparison_fixed_before_results'] and p['comparison_scope']['instruction_receipt_pushed']
    assert p['comparison_scope']['receipt_push_commit'] == 'a7750236'
    for c in p['cases'].values():
        source = Path(c['source'])
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == c['commit']
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=source, text=True).strip()
    for path, digest in p['immutable_sha256'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path


def warned(m):
    return (m['model_children'] > 8 or m['disk_free_bytes'] < 18.5 * 2**30
            or not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
            or sum(r['mem_gb'] for r in m['registered']) > 24)


def pending(active, m):
    registered = {r['pid'] for r in m['registered']}
    rows = G.G.processes()
    pending_models = pending_mem = 0
    for name, (proc, _) in active.items():
        if name not in plan()['cases'] or proc.poll() is not None:
            continue
        c = plan()['cases'][name]
        file = Path(c['folder']) / 'worker_pid.json'
        worker = json.loads(file.read_text())['pid'] if file.exists() else None
        if worker is None or worker not in rows:
            pending_models += 1
        if proc.pid not in registered:
            pending_mem += c['mem_gb']
    return pending_models, pending_mem


def can_start(m, mem, models, pending_models=0, pending_mem=0):
    return (G.start_ok(m) and m['model_children'] + pending_models + models <= 8
            and sum(r['mem_gb'] for r in m['registered']) + pending_mem + mem <= 24)


def alive(pid):
    rows = G.G.processes()
    return pid in rows and 'Z' not in rows[pid][1]


def validate(name):
    c = plan()['cases'][name]
    folder = Path(c['folder'])
    measure = json.loads((folder / 'measurement.json').read_text())
    worker = json.loads((folder / 'worker_pid.json').read_text())
    assert measure['trials'] == c['trials'] and measure['pid'] == worker['pid']
    assert not alive(worker['pid']) and not alive(worker['ppid'])
    with (folder / 'run.log').open('rb') as stream:
        stream.seek(max(0, (folder / 'run.log').stat().st_size - 65536))
        assert b'ALLDONE' in stream.read(), '原ALLDONE無し'
    if c['observer'] == 'plain':
        assert measure['native_loop_returned']
    else:
        assert measure['cpu_scope'] == 'worker_model_observer_state_save'
        assert all((folder / n).exists() for n in ('tie_state.jsonl', 'saved_matcher.jsonl.gz'))
    counts = json.loads((folder / 'json_fallback_counts.json').read_text())
    assert counts['attempted_records'] == counts['written_records']
    return measure, counts


def complete(name, proc):
    assert proc.returncode == 0, ('実受付終了コード', name, proc.returncode)
    measure, counts = validate(name)
    write(name + '_completed.json', dict(at=G.stamp(), receipt_pid=proc.pid,
        receipt_exit_code=proc.returncode, receipt_exit_code_observable=True,
        code=plan()['cases'][name]['commit'], trials=measure['trials'],
        native_all_done=True, measurement=measure, fallback_counts=counts,
        comparison_complete=False, production_authorized=False))


def guard(root, trials):
    value = json.loads((root / 'p10_cache_guard.jsonl.gz.summary.json').read_text())
    assert value['enabled'] and value['native_loop_returned']
    assert value['forbidden_reads'] == 0 and value['boundaries'] == trials
    return value


def comparison(name):
    deadline()
    verify()
    c = plan()['comparisons'][name]
    assert not (ROOT / (name + '_required_gate.json')).exists()
    for dep in c['dependencies']:
        done = json.loads((ROOT / (dep + '_completed.json')).read_text())
        assert done['receipt_exit_code'] == 0 and done['native_all_done']
        validate(dep)
    if name == 'b_e9_2a_1740':
        assert (ROOT / 'group_0_overlap_observed.json').exists(), '元と修正版を並べた実psの根拠無し'
    left, right = Path(c['left']), Path(c['right'])
    write(name + '_comparison_entry.json', dict(at=G.stamp(), left=str(left), right=str(right), mem_gb=1))
    result = tree(left, right, c['trials'], c['observer'] and not c['prune'])
    if c['guard']:
        result['guard'] = guard(right, c['trials'])
    if c['prune']:
        filtered = ROOT / (name + '_independent_reference')
        transformation = convert(left, filtered)
        assert transformation['passed'] and transformation['original_rng_digest_reconstructed']
        result['cache_observation'] = dict(transformation=transformation,
            records=[dict(file=n, **compare(filtered / n, right / n))
                     for n in ('tie_state.jsonl', 'saved_matcher.jsonl.gz')])
    result.update(at=G.stamp(), instruction=34, all_on_same_mac=True,
        reference_not_rerun=not c['reference_is_new_authorized_mac_run'],
        reference_is_new_authorized_mac_run=c['reference_is_new_authorized_mac_run'],
        existing_reference_not_rerun=True, production_authorized=False,
        fallback_counts={dep: json.loads((Path(plan()['cases'][dep]['folder']) / 'json_fallback_counts.json').read_text())
                         for dep in c['dependencies']})
    write(name + '_required_gate.json', result)


def command(name, comparing=False):
    c = plan()['cases'].get(name)
    return [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示34 ' + name,
            '--mem', '1' if comparing else str(c['mem_gb']), '--disk-path',
            str(ROOT if comparing else Path(c['folder']) / 'output'), '--', G.PY,
            str(ROOT / 'controller.py'), 'compare' if comparing else 'entry', name]


def submit(name, active, comparing=False):
    deadline()
    verify()
    assert not (ROOT / (name + '_receipt_submitted.json')).exists()
    c = plan()['cases'].get(name)
    log_path = ROOT / (name + '_comparison.log') if comparing else Path(c['folder']) / 'run.log'
    log = log_path.open('x')
    env = os.environ.copy()
    if c:
        env.update(c['environment'], SME_JSON_CASE=name)
    cmd = command(name, comparing)
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    active[name] = (proc, log)
    write(name + '_receipt_submitted.json', dict(at=G.stamp(), pid=proc.pid, command=cmd,
        mem_gb=1 if comparing else c['mem_gb'], comparing=comparing, automatic_retry=False))


def record_overlap():
    rows = G.G.processes()
    for number, names in enumerate(plan()['groups'][:2]):
        path = ROOT / ('group_' + str(number) + '_overlap_observed.json')
        if path.exists():
            continue
        workers = []
        for name in names:
            file = Path(plan()['cases'][name]['folder']) / 'worker_pid.json'
            if file.exists():
                workers.append(json.loads(file.read_text())['pid'])
        if len(workers) == 2 and all(p in rows and 'Z' not in rows[p][1] for p in workers):
            write(path.name, dict(at=G.stamp(), workers=workers,
                actual_ps={str(p): rows[p] for p in workers}, same_start_time=False))


def main():
    if len(sys.argv) > 1:
        action, name = sys.argv[1:]
        deadline()
        verify()
        assert not (ROOT / 'warning.json').exists() and not (ROOT / 'failure.json').exists()
        if action == 'compare':
            return comparison(name)
        assert action == 'entry'
        c = plan()['cases'][name]
        assert not (Path(c['folder']) / 'output').exists()
        m = G.machine()
        assert can_start(m, 0, 1), '登録済み受付の開始条件を緩めない'
        write(name + '_entry_started.json', dict(at=G.stamp(), machine=m, code=c['commit'],
            actual_native_command=c['native_command'], production_started=False))
        os.execv(G.PY, [G.PY, str(ROOT / 'observe_counted.py'), name])
    with (ROOT / 'supervisor.lock').open('x') as out:
        out.write(str(os.getpid()) + '\n')
    active = {}
    groups = list(plan()['groups'])
    comparisons = list(plan()['comparisons'])
    halted = False
    try:
        verify()
        for c in plan()['cases'].values():
            assert not any((Path(c['folder']) / f).exists() for f in ('output', 'run.log', 'worker_pid.json'))
        write('launch.json', dict(at=G.stamp(), pid=os.getpid(), groups=groups,
            comparisons=comparisons, deadline=plan()['deadline'], signals=False, deletes=False, automatic_retry=False))
        while active or groups or comparisons:
            try:
                verify()
                m = G.machine()
                if warned(m) and not halted:
                    write('warning.json', dict(at=G.stamp(), machine=m, models_not_signaled=True))
                    halted = True
                for name, (proc, log) in list(active.items()):
                    if proc.poll() is None:
                        continue
                    log.close()
                    write(name + '_receipt_ended.json', dict(at=G.stamp(), pid=proc.pid, exit_code=proc.returncode))
                    del active[name]
                    if not halted:
                        if name in plan()['cases']:
                            complete(name, proc)
                        else:
                            assert proc.returncode == 0, ('比較の実終了コード', name, proc.returncode)
                            assert json.loads((ROOT / (name + '_required_gate.json')).read_text())['passed']
                record_overlap()
                if not halted:
                    deadline()
                    m = G.machine()
                    pm, pb = pending(active, m)
                    if groups:
                        group = groups[0]
                        mem = sum(plan()['cases'][n]['mem_gb'] for n in group)
                        if can_start(m, mem, len(group), pm, pb):
                            for name in group:
                                submit(name, active)
                            groups.pop(0)
                    if not any(n in plan()['comparisons'] for n in active):
                        for name in list(comparisons):
                            c = plan()['comparisons'][name]
                            if all((ROOT / (d + '_completed.json')).exists() for d in c['dependencies']):
                                m = G.machine()
                                pm, pb = pending(active, m)
                                if can_start(m, 1, 0, pm, pb):
                                    submit(name, active, True)
                                    comparisons.remove(name)
                                break
                write('status.json', dict(at=G.stamp(), pid=os.getpid(), machine=m,
                    phase='no_new_submission_waiting_natural_end' if halted else 'models_or_comparisons_running_or_waiting',
                    active={n: p.pid for n, (p, _) in active.items()}, pending_groups=groups,
                    pending_comparisons=comparisons, models_not_signaled=True, automatic_retry=False), False)
            except Exception as exc:
                if not (ROOT / 'failure.json').exists():
                    write('failure.json', dict(at=G.stamp(), error=repr(exc), models_not_signaled=True, automatic_retry=False))
                halted = True
            if halted and not active:
                break
            if active or groups or comparisons:
                time.sleep(10)
        write('status.json', dict(at=G.stamp(), pid=os.getpid(),
            phase='stopped_no_automatic_retry' if halted else 'three_required_gates_completed_adoption_pending',
            models_not_signaled=True, production_authorized=False, automatic_retry=False), False)
    except Exception as exc:
        if not (ROOT / 'failure.json').exists():
            write('failure.json', dict(at=G.stamp(), error=repr(exc), models_not_signaled=True, automatic_retry=False))
        while any(proc.poll() is None for proc, _ in active.values()):
            time.sleep(10)
        raise


if __name__ == '__main__':
    main()
