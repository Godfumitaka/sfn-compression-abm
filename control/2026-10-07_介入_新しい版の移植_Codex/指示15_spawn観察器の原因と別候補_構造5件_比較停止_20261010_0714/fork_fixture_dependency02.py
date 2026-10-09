"""旧観察器と別候補を同じfork条件で比較する診断用の外側だけの入口。"""
import concurrent.futures
import json
import multiprocessing as mp
from pathlib import Path
import runpy
import sys

runtime_path, observer_path = sys.argv[1:]
runtime = json.loads(Path(runtime_path).read_text())
sys.path[:0] = [str(Path(observer_path).resolve().parent), str(Path(runtime['cwd'])/'tools'), runtime['cwd']]
import v3_run


class DiagnosticForkPool(concurrent.futures.ProcessPoolExecutor):
    def __init__(self, max_workers, max_tasks_per_child):
        assert max_workers == 1 and max_tasks_per_child == 1
        # 本体と設定を変えず、一つのtaskだけを同じforkで実行する小例に限る。
        super().__init__(max_workers=1, mp_context=mp.get_context('fork'))


v3_run.ProcessPoolExecutor = DiagnosticForkPool
sys.argv = [observer_path, runtime_path]
runpy.run_path(observer_path, run_name='__main__')
