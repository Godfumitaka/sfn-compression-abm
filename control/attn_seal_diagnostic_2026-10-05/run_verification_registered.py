"""全件の算術検算を受付表へ登録する。"""
import importlib.util
import subprocess
import time
from pathlib import Path

JOB = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resource_supervisor', JOB.parent/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = JOB, JOB, 1
M.state = {'status': 'preparing_score_verification', 'model_or_attention_replayed': False}


def main():
    if (JOB/'score_verification.json').exists():
        raise RuntimeError('検算を重複しない')
    M.machine('保存Qの全件算術検算前')
    cmd = [M.PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 保存Qの算術検算',
           '--mem', '2.0', '--disk-path', str(JOB), '--', M.PYTHON, str(JOB/'verify_score_arithmetic.py')]
    with (JOB/'score_verification.log').open('x') as log:
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        M.active.append({'world': 2, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False})
        M.append('commands.jsonl', {'command': cmd})
        M.status(status='verifying_scores_or_waiting_for_claim')
        while child.poll() is None:
            time.sleep(5)
            M.machine('保存Qの全件算術検算中')
        if child.returncode:
            raise RuntimeError(f'保存Qの検算終了コード{child.returncode}。違う件数と値を報告する')
        M.registration('release', '--pid', str(child.pid))
        M.active.clear()
    M.machine('保存Qの全件算術検算後')
    M.status(status='score_verification_passed_ready_for_gap_table')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        M.stop_own_jobs()
        M.status(status='stopped', error=repr(error))
        raise
