"""検算後の追加診断の表だけを、機械記録と受付表付きで作る。"""
import importlib.util
import subprocess
import time
from pathlib import Path

JOB = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('resource_supervisor', JOB.parent/'stageB1_resumed_2026-10-04/run_baseline_registered.py')
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.JOB, M.OUTPUT, M.MAX_WORKERS = JOB, JOB, 1
M.state = {'status': 'preparing_tables', 'model_or_attention_replayed': False}


def main():
    if (JOB/'tabulation_check.json').exists():
        raise RuntimeError('区分表を重複生成しない')
    M.machine('シール席の区分表・点差表の生成前')
    cmd = [M.PYTHON, M.JOBS, 'run', '--wait', '--owner', 'Codex2 シール席の区分表・事後点差',
           '--mem', '2.0', '--disk-path', str(JOB), '--', M.PYTHON, str(JOB/'tabulate_records.py')]
    with (JOB/'tabulation.log').open('x') as log:
        child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        M.active.append({'world': 2, 'seed': 0, 'pid': child.pid, 'process': child, 'adopted': False})
        M.append('commands.jsonl', {'command': cmd})
        M.status(status='tabulating_or_waiting_for_claim')
        while child.poll() is None:
            time.sleep(2)
            M.machine('シール席の区分表・点差表の生成中')
        if child.returncode:
            raise RuntimeError(f'表の生成終了コード{child.returncode}。ログを確認する')
        M.registration('release', '--pid', str(child.pid))
        M.active.clear()
    M.machine('シール席の区分表・点差表の生成後')
    M.status(status='complete_tables_ready_for_report')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        M.stop_own_jobs()
        M.status(status='stopped', error=repr(error))
        raise
