"""全表の逐次読みの全バイト検算後、記録だけから報告を作る。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

JOB = Path(__file__).resolve().parent
BASE = JOB.parent
SOURCE = BASE/'source'
CODE = 'cb27282a89c5f8aee302577d9b6f90cb747c194c'
PYTHON = '/opt/homebrew/bin/python3.12'
spec = importlib.util.spec_from_file_location('resource_supervisor', BASE/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = JOB/'report_supervision', JOB/'summary', 1


def verify_leaf():
    import hashlib
    import resource
    sys.path[:0] = [str(SOURCE/'tools'), str(SOURCE)]
    import attnaggregate as G
    target = JOB/'streaming_verification'
    assert not target.exists()
    target.mkdir()
    for world in (1, 2):
        name = f'n3_w{world}_A_L50'
        (target/name).symlink_to(JOB/'summary'/name)
    G.aggregate(target, 'C', grid_name='large-eta')
    checked = []
    for path in sorted((JOB/'summary/aggregate').glob('*.csv')):
        other = target/'aggregate'/path.name
        a = hashlib.sha256(path.read_bytes()).hexdigest()
        b = hashlib.sha256(other.read_bytes()).hexdigest()
        assert path.stat().st_size == other.stat().st_size and a == b
        checked.append({'file': path.name, 'bytes': path.stat().st_size, 'original_sha256': a, 'streamed_sha256': b})
    assert len(checked) == 16
    (JOB/'all_csv_streaming_check.json').write_text(json.dumps({
        'passed': True, 'code_commit': CODE, 'csv_files': checked, 'all_bytes_identical': True,
        'attention_learning_rerun': False, 'model_rerun': False,
        'peak_rss_self_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, ensure_ascii=False, indent=2)+'\n')


def main():
    assert not (M.JOB/'status.json').exists()
    M.JOB.mkdir(exist_ok=True)
    state = json.loads((JOB/'supervision/status.json').read_text())
    assert state['status'] == 'complete_large_eta_ready_for_report'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == CODE
    M.state = {'status': 'preparing', 'phase3_started': False, 'code_commit': CODE, 'reservation_gb': .5}
    for label, leaf, marker, disk in [
        ('CSV全件の逐次読み検算', [PYTHON, str(Path(__file__)), 'leaf'], JOB/'all_csv_streaming_check.json', JOB/'streaming_verification'),
        ('大きなηの報告生成', [PYTHON, str(JOB/'build_report.py')], JOB/'report_built.json', BASE/'report/control')]:
        M.OUTPUT = disk if disk.exists() else disk.parent
        M.machine(label+'の開始前')
        command = [PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 '+label, '--mem', '0.5',
                   '--disk-path', str(M.OUTPUT), '--', *leaf]
        with (M.JOB/(label+'.log')).open('x') as log:
            child = subprocess.Popen(command, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            item = {'world': 0, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False}
            M.active.append(item)
            M.append('commands.jsonl', {'command': command, 'pid': child.pid})
            M.status(status='running_or_waiting_for_claim', current_job=label)
            while child.poll() is None:
                time.sleep(5)
                M.machine(label+'の稼働中')
            result = json.loads(marker.read_text()) if marker.exists() else None
            if child.returncode or not result or not result.get('passed', result.get('all_tables_saved', False)):
                M.state['failure'] = {'stage': label, 'exit_code': child.returncode, 'check': result}
                raise RuntimeError('検算又は報告生成で停止')
            M.registration('release', '--pid', str(child.pid))
            M.active.remove(item)
            print(label+'完了', flush=True)
    M.machine('検算・報告生成の完了後')
    M.status(status='report_ready_for_review_and_push', finished_at=M.stamp())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'leaf':
        verify_leaf()
    else:
        try:
            main()
        except BaseException as error:
            M.stop_own_jobs()
            M.status(status='stopped', error=repr(error))
            raise
