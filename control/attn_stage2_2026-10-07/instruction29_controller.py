"""指示29。既存OFFは監視のみ、未開始ONだけ並行、原比較関数を再利用。"""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'instruction27_p10_parallel'
OFF = OLD / 'p10_forget_exec_off_200'
KIND = 'p10_forget_exec_on_200'
OLD_PID = 88683
OFF_RECEIPT = 49838
sys.path.insert(0, str(OLD))
spec = importlib.util.spec_from_file_location('unchanged_p10_gate', OLD / 'gate.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
L.ROOT = ROOT
H, G = L.H, L.G
H.ROOT = ROOT


def deadline():
    if G.stamp()[:19] >= '2026-10-11T09:00:00':
        raise RuntimeError('延長後の期限。新規投入・再開無し')


G.deadline = deadline


def prior_failure():
    return any((OLD / name).exists() for name in ('warning.json', 'failure.json'))


def assert_unstarted():
    for root in (OLD, ROOT):
        if any((root / KIND / name).exists() for name in ('output', 'run.log', 'measurement.json', 'worker_pid.json')):
            raise RuntimeError('ONの既存成果・模型を繰り返さない')
        if any((root / (KIND + suffix + '.json')).exists() for suffix in ('_entry_started', '_receipt_submitted', '_completed')):
            raise RuntimeError('既存ONの開始・受付・完了を繰り返さない')


def validate_native(folder, receipt):
    measure = json.loads((folder / 'measurement.json').read_text())
    worker = json.loads((folder / 'worker_pid.json').read_text())
    ps = G.G.processes()
    if measure['trials'] != 200 or measure['pid'] != worker['pid']:
        raise RuntimeError('原200試行の完走計測と模型PIDが違う')
    if any(pid in ps and 'Z' not in ps[pid][1] for pid in (receipt, worker['pid'], worker['ppid'])):
        raise RuntimeError('受付・観測・模型がまだ生存')
    if measure.get('cpu_scope') != 'worker_model_observer_state_save':
        raise RuntimeError('模型・観測・状態保存の計測範囲が違う')
    with (folder / 'run.log').open('rb') as stream:
        stream.seek(max(0, (folder / 'run.log').stat().st_size - 65536))
        if b'ALLDONE' not in stream.read():
            raise RuntimeError('原ALLDONE無し')
    if any(not (folder / name).exists() for name in ('tie_state.jsonl', 'saved_matcher.jsonl.gz')):
        raise RuntimeError('原順つき保存状態無し')
    return measure


def observe_off_completion():
    measure = validate_native(OFF, OFF_RECEIPT)
    H.write('off_observed_completed.json', dict(at=G.stamp(), code=H.CODE, trials=200,
        original_root=str(OFF), receipt_pid=OFF_RECEIPT, receipt_exit_code=None,
        receipt_exit_code_observable=False, receipt_exit_code_note='引き継いだ受付なので未知',
        native_all_done=True, measurement=measure, original_completion_not_fabricated=True))


def environment():
    return dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(H.SOURCE))


def receipt_command(compare=False):
    return [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示29 P10 忘却あり ' + ('比較' if compare else 'ON200'),
        '--mem', '1', '--disk-path', str(ROOT if compare else ROOT / KIND), '--',
        G.PY, str(ROOT / 'controller.py'), 'compare' if compare else 'entry', KIND]


def main():
    if len(sys.argv) > 1:
        H.source_ok()
        if prior_failure():
            raise RuntimeError('原P10の警告・停止を保全。新規投入無し')
        if sys.argv[1:] == ['entry', KIND]:
            return L.entry(KIND)
        if sys.argv[1:] == ['compare', KIND]:
            validate_native(OFF, OFF_RECEIPT)
            done = json.loads((ROOT / (KIND + '_completed.json')).read_text())
            validate_native(ROOT / KIND, done['receipt_pid'])
            L.comparison(KIND)
            path = ROOT / (KIND + '_cpu_comparison.json')
            data = json.loads(path.read_text())
            data.update(starts_at_different_times_but_runs_overlap=True, timing_diagnostic_only=True,
                off_original_start=json.loads((OLD / 'p10_forget_exec_off_200_entry_started.json').read_text())['at'],
                on_start=json.loads((ROOT / (KIND + '_entry_started.json')).read_text())['at'])
            H.write(path.name, data)
            return
        raise RuntimeError('指定されていない入口')
    with (ROOT / 'supervisor.lock').open('x') as stream:
        stream.write(str(os.getpid()) + '\n')
    active = log = None
    adopted = H.alive(OFF_RECEIPT)
    submitted = False
    halted = False
    try:
        deadline()
        H.source_ok()
        assert_unstarted()
        if H.alive(OLD_PID) or not (ROOT / 'old_supervisor_ended.json').exists() or prior_failure():
            raise RuntimeError('原監督が生存・未移管・警告又は停止済み')
        if not L.dependency():
            raise RuntimeError('前提の原200関門が未合格')
        H.write('launch.json', dict(at=G.stamp(), pid=os.getpid(), code=H.CODE,
            adopted_off_receipt=OFF_RECEIPT, original_off=str(OFF), new_on=str(ROOT / KIND),
            mem_gb=1, comparison_mem_gb=1, trials=200, deadline='2026-10-11T09:00:00+09:00',
            model_signals=False, deletes=False, automatic_retry=False))
        if not adopted:
            observe_off_completion()
        while adopted or active is not None or not submitted:
            if adopted and not H.alive(OFF_RECEIPT):
                observe_off_completion()
                adopted = False
            if active is not None and active.poll() is not None:
                H.write(KIND + '_receipt_ended.json', dict(at=G.stamp(), pid=active.pid, exit_code=active.returncode))
                log.close()
                H.completed(KIND, active)
                validate_native(ROOT / KIND, active.pid)
                active = log = None
            H.source_ok()
            machine = G.machine()
            if H.warning(machine) or prior_failure():
                if not halted:
                    H.write('warning.json', dict(at=G.stamp(), machine=machine, prior_failure=prior_failure(),
                        models_not_signaled=True, new_submission_stopped=True, automatic_retry=False))
                halted = True
            if not submitted and not halted:
                deadline()
                if H.start_ok(machine, 1, 1):
                    assert_unstarted()
                    command = receipt_command()
                    log = (ROOT / KIND / 'run.log').open('x')
                    active = subprocess.Popen(command, cwd=H.SOURCE, env=environment(), stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True)
                    submitted = True
                    H.write(KIND + '_receipt_submitted.json', dict(at=G.stamp(), pid=active.pid,
                        command=command, mem_gb=1, machine_before=machine))
            if active is not None and adopted and not (ROOT / 'overlap_observed.json').exists():
                ps = G.G.processes()
                worker_file = ROOT / KIND / 'worker_pid.json'
                if worker_file.exists():
                    worker = json.loads(worker_file.read_text())['pid']
                    off_worker = json.loads((OFF / 'worker_pid.json').read_text())['pid']
                    if worker in ps and off_worker in ps:
                        H.write('overlap_observed.json', dict(at=G.stamp(), off_worker=off_worker,
                            on_worker=worker, actual_ps={str(p): ps[p] for p in (off_worker, worker)}, same_start_time=False))
            H.write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=H.CODE,
                phase='no_new_submission_waiting_natural_end' if halted else 'parallel_forget_models_running_or_waiting',
                adopted_off_receipt=OFF_RECEIPT if adopted else None, on_receipt=active.pid if active else None,
                on_submitted=submitted, machine=machine, models_not_signaled=True, automatic_retry=False))
            if halted and not adopted and active is None:
                raise RuntimeError('資源警告。自然終了後も新規投入・比較無し')
            if adopted or active is not None or not submitted:
                time.sleep(10)
        H.monitored(receipt_command(compare=True), KIND, 0)
        H.write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=H.CODE,
            phase='forget_exec_200_gate_completed_review_pending', world1_gate_complete=False,
            full_first_bundle_complete=False, adoption_decided=False))
    except Exception as exc:
        H.write('failure.json', dict(at=G.stamp(), error=repr(exc), automatic_retry=False,
            models_not_signaled=True, new_submission_stopped=True))
        while (adopted and H.alive(OFF_RECEIPT)) or (active is not None and active.poll() is None):
            H.write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='no_new_submission_waiting_natural_end',
                error=repr(exc), models_not_signaled=True, automatic_retry=False))
            time.sleep(10)
        if log is not None and not log.closed:
            log.close()
        H.write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='stopped_no_automatic_retry', error=repr(exc)))
        raise


if __name__ == '__main__':
    main()
