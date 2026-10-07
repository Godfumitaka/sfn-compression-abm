"""指示12の別出力の観測の準備。実行中の模型・観測・入力を変えない。"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import resource
import subprocess
import sys
import time

from retained_size_01 import measure

SOURCE = Path(os.environ['SME_EXACT_SOURCE'])
sys.path[:0] = [str(SOURCE / 'tools'), str(SOURCE)]
import v3_run
REAL_WORKER = v3_run.worker


def current_rss():
    done = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(os.getpid())],
                          capture_output=True, text=True, check=True)
    return int(done.stdout.strip()) * 1024


def worker(task):
    import sweep
    real_run = sweep.run_one

    def run_one(task):
        import abm.loop as loop
        import cstar_runtime as cstar
        import smereplay
        import smeshared
        from cstar_matcher import CstarEngine
        root = Path(task['out_root']).parent
        stream = (root / 'memory_observations.jsonl').open('x')
        configured = task['cfg']['trial_count']
        marks = {99, 999, 1739} if configured == 1740 else {configured - 1}
        transient_trial = 1399 if configured == 1740 else configured - 1
        record = dict(predictions=0, in_prediction=False, transient_done=False,
                      snapshot_done=False, observer_cpu_seconds=0., samples=0)
        real_predict, real_engine_run, real_snapshot = loop.predict, CstarEngine.run, smeshared.snapshot

        def roots():
            # 同じ実体はこの順で初めて届いた所だけに含める。独立な内訳と呼ばない。
            tables = [('Cstar.cache', cstar.ENGINE.cache),
                      ('Cstar.cache_rng', cstar.ENGINE.cache_rng),
                      ('Cstar.self_cache', cstar.ENGINE.self_cache),
                      ('SME.cache', smeshared.ENGINE.cache),
                      ('SME.cache_rng', smeshared.ENGINE.cache_rng),
                      ('SME.self_cache', smeshared.ENGINE.self_cache),
                      ('shared.RESULTS', smeshared.RESULTS),
                      ('shared.GRAPHS', smeshared.GRAPHS),
                      ('shared.CHOICES', smeshared.CHOICES)]
            return tables

        def observe(kind, extra=()):
            begin = time.process_time()
            rss_before = current_rss()
            measured = measure(roots() + list(extra))
            value = dict(at=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
                         kind=kind, trial_index=smereplay.ST['trial'],
                         counts={name: len(table) for name, table in roots()},
                         current_rss_before_bytes=rss_before,
                         current_rss_after_bytes=current_rss(),
                         past_maximum_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         **measured)
            stream.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
            stream.flush()
            record['observer_cpu_seconds'] += time.process_time() - begin
            record['samples'] += 1

        def predict(ai, state, config, rng):
            prior = record['in_prediction']
            record['in_prediction'] = True
            try:
                result = real_predict(ai, state, config, rng)
            finally:
                record['in_prediction'] = prior
            record['predictions'] += 1
            if smereplay.ST['trial'] in marks:
                observe('after_prediction')
            return result

        def engine_run(self):
            result = real_engine_run(self)
            if (not record['transient_done'] and record['in_prediction']
                    and smereplay.ST['trial'] == transient_trial):
                record['transient_done'] = True
                # 点や候補を選び直さず、元の返り値と生きている作業用の物だけを読む。
                observe('first_engine_return_at_fixed_trial',
                        [('live_CstarEngine', self), ('returned_result', result)])
            return result

        def snapshot():
            result = real_snapshot()
            if not record['snapshot_done'] and smereplay.ST['trial'] == transient_trial:
                record['snapshot_done'] = True
                observe('first_snapshot_at_fixed_trial', [('live_snapshot', result)])
            return result

        loop.predict, CstarEngine.run, smeshared.snapshot = predict, engine_run, snapshot
        try:
            result = real_run(task)
            observe('completion')
        finally:
            loop.predict, CstarEngine.run, smeshared.snapshot = real_predict, real_engine_run, real_snapshot
            stream.close()
        assert record['predictions'] == configured
        (root / 'observations_complete.json').write_text(json.dumps(dict(
            at=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(), configured_trials=configured,
            observer_completed=True, **record,
            exactness_unconfirmed_until_byte_gate=True,
            inputs_flags_values_unchanged=True, model_results_not_used_for_selection=True,
            scope='固定した試行番号の控え・最初の生きている照合器・最初の保存の写しを読む。'
                  '模型・乱数を操作しない。sys.getsizeofの到達データの合計と現在の常駐と過去の'
                  '最大を分ける。速度の比較には使わない。'), ensure_ascii=False, indent=2) + '\n')
        return result

    sweep.run_one = run_one
    return REAL_WORKER(task)


def main():
    command = json.loads(Path(sys.argv[1]).read_text())
    assert command[command.index('--seeds') + 1] == '1'
    assert command[command.index('--shop-world') + 1] == '2'
    assert command[command.index('--horizon') + 1] == '1740'
    assert command[command.index('--trial-count') + 1] in ('20', '1740')
    assert os.environ['PYTHONHASHSEED'] == '0'
    assert not Path(command[3]).exists(), '既存の出力を上書きしない'
    v3_run.worker = worker
    sys.argv = command[1:]
    os.chdir(SOURCE)
    v3_run.main()


if __name__ == '__main__':
    main()
