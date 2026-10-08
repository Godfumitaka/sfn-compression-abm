"""指示21。既存OFFを監視だけ引き継ぎ、GCと書き出し二旗の全長だけを並べる。"""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'instruction19_speed_gate'
OFF = OLD / 'reuse_off_1740'
ON = ROOT / 'gc_fast_1740'
OLD_PID = 9042
OFF_RECEIPT = 49451
MEM_GB = 3
COMPARE_MEM_GB = 1
TRIALS = 1740
BUNDLE = ['--sme-gc-threshold 100000', '--sme-fast-encode']
spec = importlib.util.spec_from_file_location('unchanged_instruction19_gate', OLD / 'gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def write(name, data):
    path = ROOT / name
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def alive(pid):
    row = G.G.processes().get(pid)
    return row is not None and 'Z' not in row[1]


def source_ok():
    G.source_ok()
    manifest = json.loads((ROOT / 'preparation_manifest.json').read_text())
    for filename, digest in manifest['immutable_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('固定した道具・設定・命令が変わった', filename))


def prior_warning():
    return (OLD / 'warning.json').exists() or (OLD / 'failure.json').exists()


def resource_warning(m):
    return (m['model_children'] > 8 or m['disk_free_bytes'] < 18.5 * 2**30
            or not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
            or sum(r['mem_gb'] for r in m['registered']) > 24 or prior_warning())


def reserved_gb(m, own_receipt=None, own_mem=MEM_GB):
    registered = {r['pid'] for r in m['registered']}
    total = sum(r['mem_gb'] for r in m['registered'])
    if alive(OFF_RECEIPT) and OFF_RECEIPT not in registered:
        total += 4
    if own_receipt is not None and own_receipt not in registered:
        total += own_mem
    return total


def assert_unstarted():
    if any((ON / name).exists() for name in ('output', 'run.log', 'measurement.json')):
        raise RuntimeError('新しい二旗の模型を再投入しない')
    if any((ROOT / name).exists() for name in ('on_entry_started.json', 'on_receipt_submitted.json', 'on_completed.json')):
        raise RuntimeError('新しい二旗の開始又は完了記録がある')
    if any((OLD / name).exists() for name in ('reuse_on_1740/output', 'reuse_on_1740/run.log', 'reuse_on_1740_entry_started.json')):
        raise RuntimeError('旧三旗ONが開始済み。引き継がない')


def entry():
    if (ON / 'output').exists() or (ROOT / 'on_entry_started.json').exists():
        raise RuntimeError('二旗の模型の既存成果・開始を上書きしない')
    while True:
        G.deadline()
        source_ok()
        m = G.machine()
        if any((ROOT / name).exists() for name in ('warning.json', 'failure.json')) or prior_warning():
            raise RuntimeError('資源警告又は停止済み。新規投入を止める')
        if G.start_ok(m) and sum(r['mem_gb'] for r in m['registered']) <= 24:
            break
        write('on_entry_waiting.json', dict(at=G.stamp(), machine=m))
        time.sleep(10)
    native = ON / 'native_command.json'
    write('on_entry_started.json', dict(at=G.stamp(), code=G.CODE, world=2, seed=41,
        trials=TRIALS, mem_gb=MEM_GB, no_forget_exec=True, birth_hu='on', reuse='off',
        flag_bundle=BUNDLE, machine=m, actual_native_command=json.loads(native.read_text()),
        off_original_root=str(OFF), existing_off_unchanged=True, production_started=False))
    os.execv(G.PY, [G.PY, str(ROOT / 'observe.py'), str(native)])


def last_json(path):
    if not path.exists():
        return None
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        rows = stream.read().decode().splitlines()
    return json.loads(rows[-1]) if rows else None


def record_peak():
    for kind, root in (('off', OFF), ('on', ON)):
        name = kind + '_peak_rss_over_3gb.json'
        if (ROOT / name).exists():
            continue
        for filename in ('measurement.json', 'performance.jsonl'):
            row = (json.loads((root / filename).read_text()) if (root / filename).exists()
                   and filename.endswith('.json') else last_json(root / filename))
            if row and row.get('peak_rss_bytes', 0) > 3_000_000_000:
                write(name, dict(at=G.stamp(), source=str(root / filename), source_record=row,
                    threshold_bytes=3_000_000_000, peak_rss_bytes=row['peak_rss_bytes'],
                    report_only=True, models_not_signaled=True))
                break


def completed_native(kind, receipt_pid, exit_code, observable):
    root = OFF if kind == 'off' else ON
    measure = json.loads((root / 'measurement.json').read_text())
    worker = json.loads((root / 'worker_pid.json').read_text())
    if (measure['trials'] != TRIALS or measure['pid'] != worker['pid'] or alive(worker['pid'])
            or measure.get('cpu_scope') != 'worker_model_observer_state_save'):
        raise RuntimeError(('全長の原計測・模型終了の確認不足', kind))
    with (root / 'run.log').open('rb') as stream:
        stream.seek(max(0, (root / 'run.log').stat().st_size - 65536))
        if b'ALLDONE' not in stream.read():
            raise RuntimeError(('全長のnative ALLDONEが無い', kind))
    if not (root / 'saved_matcher.jsonl.gz').exists() or not (root / 'tie_state.jsonl').exists():
        raise RuntimeError(('原保存状態が無い', kind))
    write(kind + '_completed.json', dict(at=G.stamp(), code=G.CODE, trials=TRIALS,
        receipt_pid=receipt_pid, receipt_exit_code=exit_code,
        receipt_exit_code_observable=observable,
        receipt_exit_code_note='実子の終了コード' if observable else '引き継いだ受付なので未知',
        original_root=str(root), measurement=measure, native_all_done=True,
        observer_returned_and_state_saved=True, original_completion_not_fabricated=True))


def compare_outputs():
    def files(root):
        folder = root / 'output'
        return {str(p.relative_to(folder)): p for pattern in ('ledgers/**/*.jsonl.gz', 'side/**/*')
                for p in folder.glob(pattern) if p.is_file()}
    left, right = files(OFF), files(ON)
    if left.keys() != right.keys():
        raise RuntimeError('模型のファイル集合の不一致')
    records = [dict(file=name, **G.byte_compare(left[name], right[name], name.startswith('ledgers/')))
               for name in sorted(left)]
    for name in ('tie_state.jsonl', 'saved_matcher.jsonl.gz'):
        records.append(dict(file=name, **G.byte_compare(OFF / name, ON / name)))
    required = json.loads((ROOT / 'required_files.json').read_text())
    if not set(required).issubset({row['file'] for row in records}):
        raise RuntimeError('所定9ファイルが揃っていない')
    for root in (OFF, ON):
        folder = root / 'output'
        with gzip.open(next(folder.glob('ledgers/**/*.jsonl.gz')), 'rb') as stream:
            if sum(1 for _ in stream) - 1 != TRIALS:
                raise RuntimeError('台帳の試行数不足')
        summary = json.loads(next(folder.glob('attention/**/*.summary.json')).read_text())
        if summary['trials'] != TRIALS or summary['all_trials_leakage_checked'] != TRIALS:
            raise RuntimeError('注意の情報境界の全試行の記録不足')
    return dict(at=G.stamp(), passed=True, code=G.CODE, world=2, seed=41, trials=TRIALS,
        records=records, flag_bundle=BUNDLE, reuse='off', no_forget_exec=True, birth_hu='on',
        excluded=['台帳の見出し一行だけ'], full_length_gate_complete=True,
        production_started=False, timing_diagnostics_separate=True)


def compare_entry():
    G.deadline()
    source_ok()
    if any((ROOT / name).exists() for name in ('warning.json', 'failure.json', 'required_gate_1740.json')):
        raise RuntimeError('警告・停止又は完了済み。比較を再投入しない')
    for kind in ('off', 'on'):
        if not (ROOT / (kind + '_completed.json')).exists():
            raise RuntimeError('模型の完走確認前に比較しない')
    write('comparison_entry_started.json', dict(at=G.stamp(), code=G.CODE, mem_gb=COMPARE_MEM_GB))
    gate = compare_outputs()
    off = json.loads((OFF / 'measurement.json').read_text())
    on = json.loads((ON / 'measurement.json').read_text())
    write('cpu_comparison_1740.json', dict(at=G.stamp(), code=G.CODE, trials=TRIALS,
        off=off, on=on, on_over_off_cpu=on['cpu_seconds']/off['cpu_seconds'],
        on_over_off_wall=on['wall_seconds']/off['wall_seconds'],
        includes_observer_and_state_save=True, flag_bundle=BUNDLE, reuse='off',
        gc_seconds=None, gc_count=None,
        gc_note='原の同じ観測台本と固定模型にはGC秒・回数の計測が無い。後から補わない。',
        off_original_start=json.loads((OLD/'reuse_off_1740_entry_started.json').read_text())['at'],
        on_start=json.loads((ROOT/'on_entry_started.json').read_text())['at'],
        starts_at_different_times_but_runs_overlap=True, adoption_decided=False))
    write('required_gate_1740.json', gate)


def environment():
    env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(G.SOURCE))
    for key in ('LANG', 'LC_ALL', 'LC_CTYPE'):
        env.pop(key, None)
    return env


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'entry':
            return entry()
        if sys.argv[1] == 'compare':
            return compare_entry()
        raise RuntimeError('指定されていない入口')
    with (ROOT/'supervisor.lock').open('x') as lock:
        lock.write(str(os.getpid())+'\n')
    active = log = None
    adopted = True
    submitted = False
    halted = False
    try:
        source_ok()
        if alive(OLD_PID) or not (ROOT/'old_supervisor_ended.json').exists():
            raise RuntimeError('旧監督が終了していない。後続投入を重複させない')
        assert_unstarted()
        if not alive(OFF_RECEIPT):
            raise RuntimeError('引き継ぐOFF受付が既に終了した。再投入しない')
        write('launch.json', dict(at=G.stamp(), pid=os.getpid(), code=G.CODE,
            adopted_off_receipt=OFF_RECEIPT, original_off=str(OFF), new_on=str(ON),
            mem_gb=MEM_GB, flag_bundle=BUNDLE, reuse='off', trials=TRIALS,
            old_three_flag_on_not_started=True, model_signals=False, deletes=False, automatic_retry=False))
        while adopted or active is not None or not submitted:
            if adopted and not alive(OFF_RECEIPT):
                completed_native('off', OFF_RECEIPT, None, False)
                adopted = False
            if active is not None and active.poll() is not None:
                code = active.returncode
                log.close()
                write('on_receipt_ended.json', dict(at=G.stamp(), receipt_pid=active.pid, exit_code=code))
                if code:
                    raise RuntimeError(('新ON受付の終了コード', code))
                completed_native('on', active.pid, code, True)
                active = log = None
            m = G.machine()
            record_peak()
            if resource_warning(m):
                if not (ROOT/'warning.json').exists():
                    write('warning.json', dict(at=G.stamp(), machine=m, previous_gate_warning=prior_warning(),
                        models_not_signaled=True, new_submission_stopped=True, automatic_retry=False))
                halted = True
            if not submitted and not halted:
                G.deadline()
                source_ok()
                if G.start_ok(m) and reserved_gb(m)+MEM_GB <= 24:
                    assert_unstarted()
                    command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示21 GC書き出し二旗 全1740',
                        '--mem', str(MEM_GB), '--disk-path', str(ON), '--', G.PY, str(ROOT/'controller.py'), 'entry']
                    log = (ON/'run.log').open('x')
                    active = subprocess.Popen(command, cwd=G.SOURCE, env=environment(), stdout=log,
                        stderr=subprocess.STDOUT, start_new_session=True)
                    submitted = True
                    write('on_receipt_submitted.json', dict(at=G.stamp(), receipt_pid=active.pid,
                        command=command, mem_gb=MEM_GB, machine_before=m, effective_reserved_before=reserved_gb(m)))
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=G.CODE,
                phase='no_new_submission_waiting_natural_end' if halted else 'parallel_models_running_or_waiting',
                adopted_off_receipt=OFF_RECEIPT if adopted else None,
                on_receipt=active.pid if active else None, on_submitted=submitted, machine=m,
                effective_reserved_gb=reserved_gb(m, active.pid if active else None),
                models_not_signaled=True, automatic_retry=False))
            if halted and not adopted and active is None:
                raise RuntimeError('資源警告。自然終了後も新規比較・再投入をしない')
            if adopted or active is not None or not submitted:
                time.sleep(10)
        while True:
            G.deadline()
            source_ok()
            m = G.machine()
            if resource_warning(m) or halted:
                raise RuntimeError('資源確認不足。比較を新規投入しない')
            if G.start_ok(m) and reserved_gb(m)+COMPARE_MEM_GB <= 24:
                break
            write('status.json', dict(at=G.stamp(), phase='waiting_readonly_comparison_receipt', machine=m))
            time.sleep(10)
        command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示21 完走出力の読取り全バイト比較',
            '--mem', str(COMPARE_MEM_GB), '--disk-path', str(ROOT/'analysis'), '--', G.PY, str(ROOT/'controller.py'), 'compare']
        with (ROOT/'analysis/run.log').open('x') as comparison_log:
            active = subprocess.Popen(command, cwd=G.SOURCE, env=environment(), stdout=comparison_log,
                stderr=subprocess.STDOUT, start_new_session=True)
            write('comparison_receipt_submitted.json', dict(at=G.stamp(), command=command, receipt_pid=active.pid, mem_gb=COMPARE_MEM_GB))
            while active.poll() is None:
                m = G.machine()
                if resource_warning(m):
                    halted = True
                    if not (ROOT/'warning.json').exists():
                        write('warning.json', dict(at=G.stamp(), machine=m, models_not_signaled=True, new_submission_stopped=True))
                time.sleep(10)
            write('comparison_receipt_ended.json', dict(at=G.stamp(), exit_code=active.returncode))
            if active.returncode or halted:
                raise RuntimeError(('比較の終了又は資源警告', active.returncode, halted))
            active = None
        write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='two_flag_full_gate_completed_review_pending',
            code=G.CODE, adoption_decided=False, production_started=False))
    except Exception as exc:
        write('failure.json', dict(at=G.stamp(), error=repr(exc), automatic_retry=False,
            models_not_signaled=True, new_submission_stopped=True))
        while (adopted and alive(OFF_RECEIPT)) or (active is not None and active.poll() is None):
            record_peak()
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='no_new_submission_waiting_natural_end',
                error=repr(exc), models_not_signaled=True, automatic_retry=False))
            time.sleep(10)
        if log is not None and not log.closed:
            log.close()
        write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='stopped_no_automatic_retry', error=repr(exc)))
        raise


if __name__ == '__main__':
    main()
