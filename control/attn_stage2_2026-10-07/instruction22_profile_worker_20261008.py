"""指示22の計測だけ。開示の第二段会計を包み、原値・更新・旗を変えない。"""
from pathlib import Path
import cProfile
import importlib.util
import json
import os
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT.parent / 'instruction16_calibration_preview_seed41' / 'observe_light.py'
spec = importlib.util.spec_from_file_location('original_light_observer', ORIGINAL)
O = importlib.util.module_from_spec(spec)
spec.loader.exec_module(O)


def profile_worker(task):
    import abm.loop as loop
    import attnstage2_runtime as runtime
    profile = cProfile.Profile()
    original_install = runtime.install
    calls = 0
    wall = 0.0
    installed = False

    def install(*args, **kwargs):
        nonlocal installed
        result = original_install(*args, **kwargs)
        original_accounting = loop._update_accounting

        def accounting(state, output, scene, config, horizon, score, coin, revealed):
            nonlocal calls, wall
            if not coin.f_fired:
                return original_accounting(state, output, scene, config, horizon, score, coin, revealed)
            calls += 1
            begin = time.perf_counter()
            profile.enable()
            try:
                return original_accounting(state, output, scene, config, horizon, score, coin, revealed)
            finally:
                profile.disable()
                wall += time.perf_counter() - begin

        loop._update_accounting = accounting
        installed = True
        return result

    runtime.install = install
    returned = False
    try:
        result = O.worker(task)
        returned = True
        return result
    finally:
        runtime.install = original_install
        out = Path(task['out_root']).parent
        profile.dump_stats(str(out / 'disclosure_accounting.pstats'))
        stats = pstats.Stats(profile)
        rows = []
        for (filename, line, name), (primitive, total, own, cumulative, callers) in stats.stats.items():
            rows.append(dict(file=filename, line=line, function=name, primitive_calls=primitive,
                total_calls=total, self_seconds=own, cumulative_seconds=cumulative,
                callers=[dict(file=k[0], line=k[1], function=k[2], values=list(v) if isinstance(v, tuple) else v)
                         for k, v in callers.items()]))
        O.write(out / 'disclosure_profile.json', dict(at=O.stamp(), pid=os.getpid(),
            returned=returned, stage2_wrapper_installed=installed, disclosed_accounting_calls=calls,
            profiled_wall_seconds=wall, total_profile_self_seconds=stats.total_tt,
            scope='disclosed_trials_stage2_accounting_wrapper_including_original_accounting_and_accumulation',
            birth_virtual_questions_outside_accounting_not_profiled=True,
            profiler_overhead_present=True, unprofiled_wall_not_inferred=True,
            model_source_unchanged=True, original_observer=str(ORIGINAL),
            functions=sorted(rows, key=lambda r: r['cumulative_seconds'], reverse=True)))


if __name__ == '__main__':
    command = json.loads(Path(sys.argv[1]).read_text())
    if Path(command[3]).exists():
        raise RuntimeError('既存の模型出力を上書きしない')
    O.v3_run.worker = profile_worker
    sys.argv = command[1:]
    os.chdir(O.SOURCE)
    O.v3_run.main()
