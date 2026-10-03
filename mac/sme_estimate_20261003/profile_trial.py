"""種1・64試行の時間測定だけ。直列実行で呼び出しの内訳を保存する。"""
import cProfile
import json
import pstats
import sys
import time
from concurrent.futures import Future
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'source'), str(ROOT/'source/tools')]
import v3_run


class SerialExecutor:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def shutdown(self, **kwargs):
        pass

    def submit(self, fn, task):
        future = Future()
        profile = cProfile.Profile()
        start = time.perf_counter()
        try:
            value = profile.runcall(fn, task)
            seconds = time.perf_counter()-start
            profile.dump_stats(str(ROOT/'trial_profile.pstats'))
            stats = pstats.Stats(profile)
            calls = [{ 'file':Path(file).name,'line':line,'function':name,
                       'primitive_calls':cc,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct}
                      for (file,line,name),(cc,nc,tt,ct,_callers) in stats.stats.items()
                      if Path(file).name in ('fixorder2.py','strictpc.py','v310be.py','v39.py')]
            (ROOT/'trial_profile.json').write_text(json.dumps(
                {'seed':1,'trials':64,'wall_seconds_profiled':seconds,
                 'seconds_per_trial_profiled':seconds/64,'functions':calls},
                ensure_ascii=False,indent=2)+'\n')
            future.set_result(value)
        except BaseException as exc:
            future.set_exception(exc)
        return future


if __name__ == '__main__':
    v3_run.ProcessPoolExecutor = SerialExecutor
    flags = '''--nohash --vt 0.3842 --extend-rule none --charge1 d32 --fast
    --no-public-history --dump-slot-history --fix2-full --fix-order2 --proj-first
    --fill-norestate --no-charge2 --own-evidence --v39 --v39-budget inf --v39-decay actr
    --v310-be --hist-role --score-role --u-struct --relearn-init --tie-struct --amb-local
    --nsim 0.7 --ident-rho 0.5 --ident-argmax --ident-commons
    --cells f0.5000_th2.1000_first_order --dump-answers --dump-routing --answer-gap
    --strict-pc --cf-value --probe-world --e-price 0.01873710622997919 --workers 1
    --no-compare --v39-price 0.01873710622997919 --shop-world 2 --select-n3
    --seeds 1 --trial-count 64'''.split()
    sys.argv = ['tools/v3_run.py', str(ROOT/'source/config/sweep_shop_hide1_s1_2026-10-01.json'),
                str(ROOT/'timing_trial_A'), *flags]
    v3_run.main()
