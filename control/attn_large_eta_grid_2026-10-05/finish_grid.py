"""40種の完了後だけ、省メモリ化した同じ集計を受付表で実行する。"""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
SOURCE = BASE/'source'
CODE = '0e40feb53745d375ea36038bcf71200843076805'
PYTHON = '/opt/homebrew/bin/python3.12'
spec = importlib.util.spec_from_file_location('resource_supervisor', BASE/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = JOB/'supervision', JOB/'summary', 1


class HashText:
    """従来のDictReader→DictWriterと同じバイトを、保存先とは独立に検算する。"""
    def __init__(self):
        self.digest = hashlib.sha256()
    def write(self, value):
        self.digest.update(value.encode('utf-8'))
        return len(value)


def aggregate_and_verify():
    sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
    import attnaggregate as G
    import resource
    marker = JOB/'summary/all_C.json'
    if marker.exists():
        check = json.loads(marker.read_text())
        assert check['passed'] and check['grid'] == 'large-eta' and check['seeds'] == 40
    else:
        G.aggregate(JOB/'summary', 'C', grid_name='large-eta')
    target = HashText()
    fields = writer = None
    for world in (1, 2):
        for seed in range(1, 21):
            source = JOB/'summary'/f'n3_w{world}_A_L50'/f'seed{seed:03d}'/'weights_100_trials.csv'
            with source.open(encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream)
                if fields is None:
                    fields = reader.fieldnames
                    writer = csv.DictWriter(target, fieldnames=fields)
                    writer.writeheader()
                assert fields == reader.fieldnames
                for row in reader:
                    writer.writerow(row)
    joined = JOB/'summary/aggregate/seed_weights_100_trials.csv'
    digest = hashlib.sha256()
    with joined.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    actual = digest.hexdigest()
    assert actual == target.digest.hexdigest()
    (JOB/'streamed_table_check.json').write_text(json.dumps({
        'passed': True, 'seeds': 40, 'actual_sha256': actual,
        'reference_sha256': target.digest.hexdigest(), 'bytes_identical': True,
        'peak_rss_self_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'reference': '同じ種・欄・行の順で元のDictReader→DictWriterを一行ずつ実行。計算式は呼ばない。'},
        ensure_ascii=False, indent=2)+'\n')


def main():
    M.state = json.loads((M.JOB/'status.json').read_text())
    assert M.state['completed'] == {'1': list(range(1, 21)), '2': list(range(1, 21))}
    assert M.state['status'] == 'stopped' and M.state['error'] == 'KeyboardInterrupt()'
    assert not M.active and not M.state['active_jobs']
    assert not M.pid_running(M.state['controller_pid'])
    assert not (JOB/'summary/all_C.json').exists()
    assert not (JOB/'summary/aggregate').exists()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    assert head == CODE and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE, text=True)
    for world in (1, 2):
        for seed in range(1, 21):
            result = json.loads((JOB/'batches'/f'w{world}_seed{seed:03d}.json').read_text())
            assert result['passed'] and result['summary']['passed'] and result['inputs_unchanged']
    M.state.pop('error', None)
    M.state.pop('failure', None)
    M.state.update(aggregation_commit=CODE, aggregation_reservation_gb=.5,
                   aggregation_streams_weight_table=True, scientific_calculations_changed=False)
    M.machine('大きなηの格子の逐次結合と全集計の開始前')
    command = [PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 大η 全集計（逐次結合）',
               '--mem', '0.5', '--disk-path', str(JOB/'summary'), '--', PYTHON,
               str(Path(__file__)), 'leaf']
    with (M.JOB/'aggregate_streamed.log').open('x') as log:
        child = subprocess.Popen(command, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        item = {'world': 0, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False}
        M.active.append(item)
        M.append('commands.jsonl', {'command': command, 'pid': child.pid, 'aggregation_commit': CODE})
        M.status(status='aggregating_streamed')
        while child.poll() is None:
            time.sleep(10)
            M.machine('大きなηの逐次結合の稼働中')
        path = JOB/'summary/all_C.json'
        check = json.loads(path.read_text()) if path.exists() else None
        if child.returncode or not check or not check['passed']:
            M.state['failure'] = {'exit_code': child.returncode, 'check': check}
            raise RuntimeError('逐次結合の全集計で停止')
        assert check['trial_records'] == 1183200 and check['door_trial_records'] == 107202
        bytecheck = json.loads((JOB/'streamed_table_check.json').read_text())
        assert bytecheck['passed'] and bytecheck['bytes_identical']
        M.registration('release', '--pid', str(child.pid))
        M.active.remove(item)
    M.machine('大きなηの格子の全集計終了後')
    M.status(status='complete_large_eta_ready_for_report', finished_at=M.stamp())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'leaf':
        aggregate_and_verify()
    else:
        try:
            main()
        except BaseException as error:
            M.stop_own_jobs()
            M.status(status='stopped', error=repr(error))
            raise
