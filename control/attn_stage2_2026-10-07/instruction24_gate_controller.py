"""指示24。二枠を待ち、別枝の開示の保存控えoff/onを並べて200試行だけ測る。"""
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
BASE = ROOT.parents[2]
SOURCE = BASE / 'cstar_stage2_disclosure_speed_source'
CODE = '75858e0b4bbff608b57391c075cf5b72c678e636'
REFERENCE = BASE / 'stage2_attention_2026-10-08/instruction19_speed_gate/reuse_off_200'
KINDS = ('isolation_off_200', 'isolation_on_200')
MEM_GB = 1
TRIALS = 200
spec = importlib.util.spec_from_file_location('readonly_instruction19', REFERENCE.parent / 'gate.py')
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def write(name, data):
    path = ROOT / name
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def source_ok():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'],
                                    cwd=SOURCE, text=True).strip()
    if head != CODE or dirty:
        raise RuntimeError(('別枝の固定ソースが変わった', head, dirty))
    manifest = json.loads((ROOT / 'preparation_manifest.json').read_text())
    for filename, digest in manifest['immutable_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise RuntimeError(('固定した道具・設定・命令が変わった', filename))


def alive(pid, ps=None):
    rows = G.G.processes() if ps is None else ps
    return pid in rows and 'Z' not in rows[pid][1]


def warning(m):
    return (m['model_children'] > 8 or m['disk_free_bytes'] < 18.5 * 2**30
            or not m['swap_ok'] or m['thermal_warnings'] or m['unregistered_heavy']
            or sum(r['mem_gb'] for r in m['registered']) > 24)


def start_resources(m, models_to_add, mem_to_add):
    return (G.start_ok(m) and m['model_children'] + models_to_add <= 8
            and sum(r['mem_gb'] for r in m['registered']) + mem_to_add <= 24)


def environment():
    env = dict(os.environ, PYTHONHASHSEED='0', SME_EXACT_SOURCE=str(SOURCE))
    for key in ('LANG', 'LC_ALL', 'LC_CTYPE'):
        env.pop(key, None)
    return env


def assert_unstarted():
    for kind in KINDS:
        for name in ('output', 'run.log', 'worker_pid.json', 'measurement.json'):
            if (ROOT / kind / name).exists():
                raise RuntimeError(('既存模型・成果を再投入しない', kind, name))
        for suffix in ('entry_started', 'receipt_submitted', 'completed'):
            if (ROOT / (kind + '_' + suffix + '.json')).exists():
                raise RuntimeError(('開始又は完了記録を上書きしない', kind, suffix))


def pending_models():
    # 二本とも受付へ渡すまで、その二枠を自分の待ちにも数える。
    return sum(not (ROOT / kind / 'worker_pid.json').exists() for kind in KINDS)


def entry(kind):
    if kind not in KINDS or (ROOT / kind / 'output').exists():
        raise RuntimeError('指定されていない又は開始済みの模型')
    if (ROOT / (kind + '_entry_started.json')).exists():
        raise RuntimeError('開始を重複させない')
    while True:
        G.deadline()
        source_ok()
        if any((ROOT / name).exists() for name in ('warning.json', 'failure.json')):
            raise RuntimeError('停止済み。新しい模型を始めない')
        m = G.machine()
        registered = {r['pid'] for r in m['registered']}
        missing = 0
        for other in KINDS:
            path = ROOT / (other + '_receipt_submitted.json')
            if path.exists():
                pid = json.loads(path.read_text())['pid']
                missing += MEM_GB if pid not in registered and alive(pid) else 0
            else:
                missing += MEM_GB
        if start_resources(m, pending_models(), missing):
            break
        write(kind + '_entry_waiting.json', dict(at=G.stamp(), machine=m,
              pending_pair_models=pending_models(), missing_pair_mem_gb=missing))
        time.sleep(10)
    write(kind + '_entry_started.json', dict(at=G.stamp(), monotonic_ns=time.monotonic_ns(),
          code=CODE, world=2, seed=41, trials=TRIALS, mem_gb=MEM_GB, machine=m,
          isolation='on' if kind == KINDS[1] else 'off', no_forget_exec=True,
          birth_hu='on', reuse='off', gc_threshold=None, fast_encode=False,
          actual_native_command=json.loads((ROOT / kind / 'native_command.json').read_text()),
          adoption_decided=False, production_started=False))
    os.execv(G.PY, [G.PY, str(ROOT / 'observe.py'), str(ROOT / kind / 'native_command.json')])


def completed(kind, proc):
    path = ROOT / (kind + '_completed.json')
    if path.exists():
        return
    if proc.returncode != 0:
        raise RuntimeError(('模型の実終了コード', kind, proc.returncode))
    folder = ROOT / kind
    measurement = json.loads((folder / 'measurement.json').read_text())
    worker = json.loads((folder / 'worker_pid.json').read_text())
    if (measurement['trials'] != TRIALS or measurement['pid'] != worker['pid']
            or measurement.get('cpu_scope') != 'worker_model_observer_state_save'
            or alive(worker['pid'])):
        raise RuntimeError(('原計測又は実模型の終了の確認不足', kind))
    with (folder / 'run.log').open('rb') as stream:
        stream.seek(max(0, (folder / 'run.log').stat().st_size - 65536))
        if b'ALLDONE' not in stream.read():
            raise RuntimeError(('原ALLDONEが無い', kind))
    if not all((folder / name).exists() for name in ('tie_state.jsonl', 'saved_matcher.jsonl.gz')):
        raise RuntimeError(('原保存状態が無い', kind))
    write(kind + '_completed.json', dict(at=G.stamp(), code=CODE, trials=TRIALS,
          receipt_pid=proc.pid, receipt_exit_code=proc.returncode,
          receipt_exit_code_observable=True, measurement=measurement,
          native_all_done=True, observer_returned_and_state_saved=True))


def compare_pair(left_root, right_root):
    def files(root):
        folder = root / 'output'
        return {str(p.relative_to(folder)): p for pattern in ('ledgers/**/*.jsonl.gz', 'side/**/*')
                for p in folder.glob(pattern) if p.is_file()}
    left, right = files(left_root), files(right_root)
    if left.keys() != right.keys():
        raise RuntimeError('模型のファイル集合の不一致')
    records = [dict(file=name, **G.byte_compare(left[name], right[name], name.startswith('ledgers/')))
               for name in sorted(left)]
    for name in ('tie_state.jsonl', 'saved_matcher.jsonl.gz'):
        records.append(dict(file=name, **G.byte_compare(left_root / name, right_root / name)))
    required = json.loads((ROOT / 'required_files.json').read_text())
    if len(required) != 9 or not set(required).issubset({r['file'] for r in records}):
        raise RuntimeError('所定9ファイルが揃っていない')
    for root in (left_root, right_root):
        folder = root / 'output'
        ledgers = list(folder.glob('ledgers/**/*.jsonl.gz'))
        if len(ledgers) != 1:
            raise RuntimeError('台帳の本数不足又は追加の模型')
        with gzip.open(ledgers[0], 'rb') as stream:
            if sum(1 for _ in stream) - 1 != TRIALS:
                raise RuntimeError('台帳の試行数不足')
        summary = json.loads(next(folder.glob('attention/**/*.summary.json')).read_text())
        if summary['trials'] != TRIALS or summary['all_trials_leakage_checked'] != TRIALS:
            raise RuntimeError('全試行の情報境界の記録不足')
    return dict(at=G.stamp(), passed=True, code=CODE, world=2, seed=41, trials=TRIALS,
                records=records, excluded=['台帳の見出し一行だけ'],
                full_length_gate_complete=False, adoption_decided=False, production_started=False)


def compare_entry():
    G.deadline()
    source_ok()
    if any((ROOT / name).exists() for name in ('warning.json', 'failure.json', 'required_gate_200.json')):
        raise RuntimeError('警告・停止又は合格済みの比較を再投入しない')
    if not all((ROOT / (kind + '_completed.json')).exists() for kind in KINDS):
        raise RuntimeError('両方の実完走の前に比較しない')
    if not (ROOT / 'overlap_observed.json').exists():
        raise RuntimeError('両実模型が並んで生存した原確認が無い')
    write('comparison_entry_started.json', dict(at=G.stamp(), code=CODE, mem_gb=1))
    # 既定offは保存済みe9の同じ200とも照合する。参考を再走行しない。
    off_gate = compare_pair(REFERENCE, ROOT / KINDS[0])
    off_gate.update(reference_code='e9ed84ae3ee6c458f392cd58cadf9fc030639900',
                    reference_not_rerun=True, isolation='off')
    write('default_off_gate_200.json', off_gate)
    gate = compare_pair(ROOT / KINDS[0], ROOT / KINDS[1])
    off, on = [json.loads((ROOT / kind / 'measurement.json').read_text()) for kind in KINDS]
    write('cpu_comparison_200.json', dict(at=G.stamp(), code=CODE, trials=TRIALS,
          off=off, on=on, on_over_off_cpu=on['cpu_seconds'] / off['cpu_seconds'],
          on_over_off_wall=on['wall_seconds'] / off['wall_seconds'],
          reduction_fraction=1 - on['cpu_seconds'] / off['cpu_seconds'],
          includes_observer_and_state_save=True, isolation_flag_only=True,
          actual_overlap=json.loads((ROOT / 'overlap_observed.json').read_text()),
          starts_at_same_time=False, adoption_decided=False, full_length_estimate=False))
    gate.update(isolation_flags=['off', 'on'], timing_diagnostics_separate=True)
    write('required_gate_200.json', gate)


def observe_overlap(active):
    if (ROOT / 'overlap_observed.json').exists():
        return
    workers = {}
    for kind in KINDS:
        path = ROOT / kind / 'worker_pid.json'
        if not path.exists():
            return
        workers[kind] = json.loads(path.read_text())
    ps = G.G.processes()
    if all(alive(row['pid'], ps) and active[kind].poll() is None for kind, row in workers.items()):
        write('overlap_observed.json', dict(at=G.stamp(), monotonic_ns=time.monotonic_ns(),
              workers=workers, actual_ps={str(row['pid']): ps[row['pid']] for row in workers.values()},
              starts_at_same_time=False, simultaneous_live_workers=True))


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'entry':
            return entry(sys.argv[2])
        if sys.argv[1] == 'compare':
            return compare_entry()
        raise RuntimeError('指定されていない入口')
    with (ROOT / 'supervisor.lock').open('x') as lock:
        lock.write(str(os.getpid()) + '\n')
    active, logs = {}, []
    halted = False
    try:
        source_ok()
        assert_unstarted()
        while True:
            G.deadline()
            source_ok()
            m = G.machine()
            if start_resources(m, 2, 2 * MEM_GB):
                break
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), phase='waiting_two_model_slots',
                  code=CODE, machine=m, requested_model_slots=2, requested_mem_gb=2 * MEM_GB))
            time.sleep(20)
        write('pair_admission.json', dict(at=G.stamp(), machine=m, code=CODE,
              pending_model_slots=2, pending_mem_gb=2 * MEM_GB))
        for index, kind in enumerate(KINDS):
            G.deadline()
            source_ok()
            m = G.machine()
            if warning(m):
                raise RuntimeError('投入の切替で資源警告。次の模型を入れない')
            command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示24 開示200 ' + kind,
                       '--mem', str(MEM_GB), '--disk-path', str(ROOT / kind), '--',
                       G.PY, str(ROOT / 'controller.py'), 'entry', kind]
            log = (ROOT / kind / 'run.log').open('x')
            logs.append(log)
            before = time.monotonic_ns()
            proc = subprocess.Popen(command, cwd=SOURCE, env=environment(), stdout=log,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            active[kind] = proc
            write(kind + '_receipt_submitted.json', dict(at=G.stamp(), pid=proc.pid,
                  command=command, mem_gb=MEM_GB, monotonic_before_ns=before,
                  monotonic_after_ns=time.monotonic_ns(), sequence=index))
        while any(proc.poll() is None for proc in active.values()):
            source_ok()
            m = G.machine()
            if warning(m):
                if not halted:
                    write('warning.json', dict(at=G.stamp(), machine=m, models_not_signaled=True))
                halted = True
            observe_overlap(active)
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=CODE, machine=m,
                  phase='no_new_submission_waiting_natural_end' if halted else 'pair_receipts_wait_or_running',
                  receipt_pids={k: p.pid for k, p in active.items()}, models_not_signaled=True))
            time.sleep(20)
        if halted:
            raise RuntimeError('資源警告を保全。比較・新規投入を止める')
        for kind, proc in active.items():
            completed(kind, proc)
        while True:
            G.deadline()
            source_ok()
            m = G.machine()
            if start_resources(m, 0, 1):
                break
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=CODE,
                  phase='waiting_readonly_comparison_receipt', machine=m))
            time.sleep(20)
        command = [G.PY, G.JOBS, 'run', '--wait', '--owner', 'Codex2 指示24 開示200 全バイト比較',
                   '--mem', '1', '--disk-path', str(ROOT), '--', G.PY, str(ROOT / 'controller.py'), 'compare']
        log = (ROOT / 'comparison.log').open('x')
        logs.append(log)
        proc = subprocess.Popen(command, cwd=SOURCE, env=environment(), stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        active['comparison'] = proc
        write('comparison_receipt_submitted.json', dict(at=G.stamp(), pid=proc.pid, command=command))
        while proc.poll() is None:
            m = G.machine()
            if warning(m):
                halted = True
                if not (ROOT / 'warning.json').exists():
                    write('warning.json', dict(at=G.stamp(), machine=m, models_not_signaled=True))
            time.sleep(20)
        if halted or proc.returncode != 0:
            raise RuntimeError(('読取り比較の停止又は終了コード', halted, proc.returncode))
        if not all((ROOT / name).exists() for name in ('default_off_gate_200.json', 'required_gate_200.json',
                                                       'cpu_comparison_200.json')):
            raise RuntimeError('実際の関門又はCPU診断が無い')
        write('status.json', dict(at=G.stamp(), pid=os.getpid(), code=CODE,
              phase='gate_200_completed_adoption_review_pending', production_started=False))
    except Exception as exc:
        # 原出力を保全し、稼働中を自然終了まで待つ。模型シグナルや再試行はしない。
        write('failure.json', dict(at=G.stamp(), error=repr(exc), automatic_retry=False,
              models_not_signaled=True))
        while any(proc.poll() is None for proc in active.values()):
            write('status.json', dict(at=G.stamp(), pid=os.getpid(), error=repr(exc),
                  phase='no_new_submission_waiting_natural_end', models_not_signaled=True))
            time.sleep(20)
        write('status.json', dict(at=G.stamp(), pid=os.getpid(), error=repr(exc),
              phase='stopped_no_automatic_retry', models_not_signaled=True))
        raise
    finally:
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
