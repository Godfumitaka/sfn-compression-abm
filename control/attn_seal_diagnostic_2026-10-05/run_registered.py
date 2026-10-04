"""追加診断の記録の抽出だけを受付表へ登録して行う。"""
import importlib.util
import subprocess
import time
from pathlib import Path

JOB = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resource_supervisor', JOB.parent/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = JOB, JOB, 1
M.state = {'status': 'preparing', 'model_or_attention_replayed': False}


def main():
    if (JOB/'status.json').exists():
        raise RuntimeError('既存の診断を重複実行しない')
    M.machine('シール席の記録抽出前')
    cmd = [M.PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 シール席の追加診断・記録抽出',
           '--mem', '2.0', '--disk-path', str(JOB), '--', M.PYTHON, str(JOB/'extract_records.py')]
    with (JOB/'extraction.log').open('x') as log:
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        item = {'world': 2, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False}
        M.active.append(item)
        M.append('commands.jsonl', {'command': cmd})
        M.status(status='extracting_or_waiting_for_claim')
        while child.poll() is None:
            time.sleep(5)
            M.machine('シール席の記録抽出中')
        if child.returncode:
            raise RuntimeError(f'抽出の終了コード{child.returncode}。ログを確認する')
        M.registration('release', '--pid', str(child.pid))
        M.active.remove(item)
    M.machine('シール席の記録抽出後')
    M.status(status='extracted_waiting_for_score_arithmetic_permission')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        M.stop_own_jobs()
        M.status(status='stopped', error=repr(error))
        raise
