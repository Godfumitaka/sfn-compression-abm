"""指示20。種41/42を監視だけ引き継ぎ、未開始の43/44だけを各3GBで渡す。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent/'instruction18_calibration'
DATA = ROOT.parent/'instruction16_calibration_preview_seed41'
SPEED_GATE = ROOT.parent/'instruction19_speed_gate'
OLD_PID = 9047
ADOPTED = {41: 95408, 42: 9073}
NEW_SEEDS = (43, 44)
MEM_GB = 3
GATE_MEM_GB = 4
BUNDLE = ['--stage2-reuse on', '--sme-gc-threshold 100000', '--sme-fast-encode']
spec = importlib.util.spec_from_file_location('unchanged_instruction18', OLD/'controller.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
P = C.P


def write(name, data):
    path = ROOT/name
    temporary = Path(str(path)+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def case_root(seed):
    if seed == 41:
        return DATA/'birth_hu_on'
    if seed == 42:
        return OLD/'w2_seed042'
    if seed not in NEW_SEEDS:
        raise RuntimeError('指定範囲以外の種を扱わない')
    return ROOT/f'w2_seed{seed:03d}'


def source_ok():
    C.source_ok()
    manifest = json.loads((ROOT/'preparation_manifest.json').read_text())
    for filename, digest in manifest['immutable_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('固定した新しい道具又は命令が変わった', filename))


def assert_unstarted(seed):
    if seed not in NEW_SEEDS:
        raise RuntimeError('新規投入は種43/44だけ')
    for folder, owner in ((case_root(seed), ROOT), (OLD/f'w2_seed{seed:03d}', OLD)):
        if (any((folder/name).exists() for name in ('output', 'run.log', 'measurement.json'))
                or any((owner/f'w2_seed{seed:03d}_{name}.json').exists()
                       for name in ('entry_started', 'receipt_submitted', 'completed'))):
            raise RuntimeError(('開始済み又は既存成果を再投入しない', seed, str(folder)))


def speed_gate(gate):
    required = json.loads((SPEED_GATE/'required_files.json').read_text())
    records = gate.get('records', [])
    if (gate.get('passed') is not True or gate.get('code') != P.CODE
            or gate.get('trials') != 200 or gate.get('flag_bundle') != BUNDLE
            or gate.get('world') != 2 or gate.get('seed') != 41
            or gate.get('birth_hu') != 'on' or gate.get('no_forget_exec') is not True
            or not set(required).issubset({row['file'] for row in records})
            or not all(row.get('equal') is True for row in records)):
        raise RuntimeError('高速化200関門の版・旗・世界/種・全バイトの確認不足')
    return gate


def entry(seed):
    if seed not in NEW_SEEDS:
        raise RuntimeError('指定範囲以外の種を開始しない')
    # 自分の受付が作ったrun.log以外に、模型の開始・出力がないことを確認する。
    root = case_root(seed)
    if ((root/'output').exists() or (ROOT/f'w2_seed{seed:03d}_entry_started.json').exists()
            or (OLD/f'w2_seed{seed:03d}_entry_started.json').exists()
            or (OLD/f'w2_seed{seed:03d}'/'run.log').exists()):
        raise RuntimeError('開始済みの模型を再投入しない')
    while True:
        P.deadline()
        source_ok()
        if any((ROOT/name).exists() for name in ('warning.json', 'failure.json')):
            raise RuntimeError('警告又は停止済み。新しい模型を開始しない')
        m = P.machine()
        if P.start_ok(m):
            break
        write(f'w2_seed{seed:03d}_entry_waiting.json', dict(at=P.stamp(), machine=m))
        time.sleep(30)
    native = root/'native_command.json'
    small_gate = SPEED_GATE/'required_gate_200.json'
    gate = None
    if small_gate.exists():
        gate = speed_gate(json.loads(small_gate.read_text()))
        command = json.loads(native.read_text())
        command[command.index('--stage2-reuse')+1] = 'on'
        command += ['--sme-gc-threshold', '100000', '--sme-fast-encode']
        native = root/'native_command_speed_gate_passed.json'
        with native.open('x') as stream:
            stream.write(json.dumps(command, ensure_ascii=False, indent=2)+'\n')
    write(f'w2_seed{seed:03d}_entry_started.json', dict(at=P.stamp(), machine=m,
        code=P.CODE, world=2, seed=seed, trials=1740, mem_gb=MEM_GB,
        no_forget_exec=True, birth_hu='on', calibration=True, heavy_matcher_observer=False,
        speed_flags_enabled=gate is not None, native_command=str(native),
        actual_native_command=json.loads(native.read_text()),
        small_speed_gate=str(small_gate) if gate else None,
        small_speed_gate_sha256=hashlib.sha256(small_gate.read_bytes()).hexdigest() if gate else None,
        small_speed_gate_record=gate))
    os.execv(P.PY, [P.PY, str(DATA/'observe_light.py'), str(native)])


def completed_native(seed, receipt_pid, exit_code, observable):
    root = case_root(seed)
    measurement = json.loads((root/'measurement.json').read_text())
    finished = json.loads((root/'worker_finished.json').read_text())
    if (measurement['trials'] != 1740 or not measurement['native_loop_returned']
            or finished['pid'] != measurement['pid'] or 'ALLDONE' not in (root/'run.log').read_text()):
        raise RuntimeError(('自然完走の原証拠不足', seed))
    write(f'w2_seed{seed:03d}_completed.json', dict(at=P.stamp(), code=P.CODE,
        world=2, seed=seed, trials=1740, receipt_pid=receipt_pid,
        receipt_exit_code=exit_code, receipt_exit_code_observable=observable,
        native_loop_returned=True, worker_finished=finished,
        original_completion_not_fabricated=True,
        receipt_exit_code_note='実子の終了コード' if observable else '引継ぎのため未知'))


def record_peak(seed):
    name = f'w2_seed{seed:03d}_peak_rss_over_3gb.json'
    if (ROOT/name).exists():
        return
    for filename in ('progress.json', 'measurement.json', 'worker_finished.json'):
        path = case_root(seed)/filename
        if path.exists():
            row = json.loads(path.read_text())
            if row.get('peak_rss_bytes', 0) > 3_000_000_000:
                write(name, dict(at=P.stamp(), world=2, seed=seed,
                    threshold_bytes=3_000_000_000, peak_rss_bytes=row['peak_rss_bytes'],
                    source=str(path), source_at=row['at'], report_only=True,
                    model_stopped=False, resource_conditions_unchanged=True))
                return


def reserved_gb(m, active_pids, adopted_pids, gate_alive):
    registered = {r['pid'] for r in m['registered']}
    reserved = sum(r['mem_gb'] for r in m['registered'])
    reserved += MEM_GB*sum(pid not in registered for pid in active_pids)
    reserved += 4*sum(pid not in registered for pid in adopted_pids)
    if gate_alive:
        gate_mem = sum(r['mem_gb'] for r in m['registered']
                       if r['owner'].startswith('Codex2 指示19 高速化関門 '))
        reserved += max(0, GATE_MEM_GB-gate_mem)
    return reserved


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'entry':
        return entry(int(sys.argv[2]))
    with (ROOT/'supervisor.lock').open('x') as lock:
        lock.write(str(os.getpid())+'\n')
    source_ok()
    if C.alive(OLD_PID):
        raise RuntimeError('旧監督が生存中。重複監督を開始しない')
    for seed in NEW_SEEDS:
        assert_unstarted(seed)
    adopted = dict(ADOPTED)
    pending = list(NEW_SEEDS)
    active, completed = {}, []
    halted = False
    write('launch.json', dict(at=P.stamp(), pid=os.getpid(), code=P.CODE,
        world=2, seeds=[41, 42, 43, 44], adopted_receipts=adopted,
        new_seeds=pending, removed_seeds=[45, 46, 47, 48], mem_gb=MEM_GB,
        existing_reservations_unchanged=True, model_signals=False, deletes=False,
        automatic_retry=False, completed_instruction20_transfer=True))
    try:
        while pending or active or adopted:
            for seed, pid in list(adopted.items()):
                if C.alive(pid):
                    continue
                # 種41/42は新監督の子でない。観測不能な終了コードを作らない。
                completed_native(seed, pid, None, False)
                completed.append(seed)
                del adopted[seed]
            for seed, (process, log) in list(active.items()):
                exit_code = process.poll()
                if exit_code is None:
                    continue
                log.close()
                del active[seed]
                write(f'w2_seed{seed:03d}_receipt_ended.json', dict(at=P.stamp(),
                    seed=seed, receipt_pid=process.pid, exit_code=exit_code))
                if exit_code:
                    raise RuntimeError(('較正の受付終了コード', seed, exit_code))
                completed_native(seed, process.pid, exit_code, True)
                completed.append(seed)
            m = P.machine()
            for seed in list(adopted)+list(active):
                record_peak(seed)
            prior_warning = any((folder/'warning.json').exists()
                for folder in (OLD, ROOT.parent/'instruction17_on_mem4_controller'))
            if P.warning(m) or prior_warning:
                if not (ROOT/'warning.json').exists():
                    write('warning.json', dict(at=P.stamp(), machine=m,
                        previous_controller_resource_warning=prior_warning,
                        new_submission_stopped=True, models_not_signaled=True, automatic_retry=False))
                halted = True
            gate_lock = SPEED_GATE/'supervisor.lock'
            gate_alive = gate_lock.exists() and C.alive(int(gate_lock.read_text().strip()))
            reserved = reserved_gb(m, [p.pid for p, _ in active.values()], adopted.values(), gate_alive)
            if pending and not halted:
                P.deadline()
                source_ok()
                if P.start_ok(m) and reserved+MEM_GB <= 24:
                    seed = pending[0]
                    assert_unstarted(seed)
                    root = case_root(seed)
                    command = [P.PY, P.JOBS, 'run', '--wait', '--owner',
                        f'Codex2 指示20 較正 世界2 種{seed}', '--mem', str(MEM_GB),
                        '--disk-path', str(root), '--', P.PY, str(ROOT/'controller.py'),
                        'entry', str(seed)]
                    write(f'w2_seed{seed:03d}_receipt_command.json', command)
                    env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(P.SOURCE))
                    for key in ('LANG', 'LC_ALL', 'LC_CTYPE'):
                        env.pop(key, None)
                    log = (root/'run.log').open('x')
                    process = subprocess.Popen(command, cwd=P.SOURCE, env=env,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    active[seed] = (process, log)
                    pending.pop(0)
                    reserved += MEM_GB
                    write(f'w2_seed{seed:03d}_receipt_submitted.json', dict(at=P.stamp(),
                        seed=seed, command=command, receipt_pid=process.pid,
                        mem_gb=MEM_GB, machine_before=m, effective_reserved_before=reserved-MEM_GB))
            write('status.json', dict(at=P.stamp(), pid=os.getpid(), code=P.CODE,
                phase=('no_new_submission_waiting_natural_end' if halted and (active or adopted)
                    else 'stopped_no_automatic_retry' if halted
                    else 'calibration_running_or_waiting' if pending or active or adopted
                    else 'mac41_44_completed_other_world_seeds_and_analysis_pending'),
                adopted_receipts={str(s): p for s, p in adopted.items()},
                active={str(s): p.pid for s, (p, _) in active.items()},
                pending=pending, removed_seeds=[45, 46, 47, 48], completed=completed,
                machine=m, mem_gb=MEM_GB, effective_reserved_gb=reserved,
                speed_gate_reserved_gb=GATE_MEM_GB if gate_alive else 0,
                models_not_signaled=True, automatic_retry=False))
            if halted and not active and not adopted:
                break
            if pending or active or adopted:
                time.sleep(5)
    except Exception as exc:
        write('failure.json', dict(at=P.stamp(), error=repr(exc),
            new_submission_stopped=True, models_not_signaled=True, automatic_retry=False))
        while any(C.alive(pid) for pid in adopted.values()) or any(p.poll() is None for p, _ in active.values()):
            for seed in list(adopted)+list(active):
                record_peak(seed)
            write('status.json', dict(at=P.stamp(), pid=os.getpid(),
                phase='no_new_submission_waiting_natural_end', error=repr(exc),
                adopted_receipts=adopted, active={str(s): p.pid for s, (p, _) in active.items()},
                pending=pending, removed_seeds=[45, 46, 47, 48],
                models_not_signaled=True, automatic_retry=False))
            time.sleep(30)
        for _, log in active.values():
            log.close()
        write('status.json', dict(at=P.stamp(), pid=os.getpid(),
            phase='stopped_no_automatic_retry', error=repr(exc),
            models_not_signaled=True, automatic_retry=False))
        raise


if __name__ == '__main__':
    main()
