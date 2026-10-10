"""指示34。設定とlen5000を保ち、同じ本番観察器で先頭100/1000を自然に終える。"""
from contextlib import contextmanager
from dataclasses import replace
from itertools import islice
from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess
import sys


class PrefixTrials:
    def __init__(self, trials, limit):
        assert len(trials) == 5000 and limit in (100, 1000)
        self.trials, self.limit = trials, limit

    def __len__(self):
        return len(self.trials)

    def __iter__(self):
        return islice(iter(self.trials), self.limit)


@contextmanager
def count_written(ledger, count):
    native = ledger.append
    absent = object()
    previous = vars(ledger).get('append', absent)
    def append(row):
        result = native(row)
        count(row)
        return result
    ledger.append = append
    try:
        yield
    finally:
        if previous is absent:
            del ledger.append
        else:
            ledger.append = previous


def partial_worker(task, limit, source, sweep, original_worker, original_longitudinal, observe, observe_timing):
    assert task['cfg']['trial_count'] == 5000 and task['cfg']['agent_ids'] == ['agent']
    assert task['seed'] in range(1, 11) and limit in (100, 1000)
    out = Path(task['out_root'])
    completed = 0
    def count(row):
        nonlocal completed
        assert row['prediction_order'] == completed
        completed += 1
        assert completed <= limit
    def longitudinal(world, *args, **kw):
        assert len(world.trials) == 5000
        ledger = kw['ledger'] if 'ledger' in kw else args[2]
        prefix = SimpleNamespace(trials=PrefixTrials(world.trials, limit), world_hash=world.world_hash)
        with observe(out, ledger, attention_enabled=bool(task.get('attn_sme')),
                     stage2_enabled=task.get('stage2') == 'on'), observe_timing(out, ledger), count_written(ledger, count):
            result = original_longitudinal(prefix, *args, **kw)
        assert completed == limit
        return replace(result, trial_count=limit)
    sweep.run_longitudinal = longitudinal
    try:
        record = original_worker(task)
    finally:
        sweep.run_longitudinal = original_longitudinal
    assert record['trial_count'] == completed == limit and not record.get('error')
    marker = dict(measurement_only=True, completed_trials=completed, configured_trial_count=5000,
                  horizon=5000, full_5000_completed=False,
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
                  production_observers_unchanged=False, structural_gate_boundary100_only=True, measurement_limit=limit)
    dest = out/'measurement'
    dest.mkdir(exist_ok=False)
    (dest/'partial_done.json').write_text(json.dumps(marker, ensure_ascii=False, indent=2)+'\n')
    return {**record, **marker}


if __name__ in ('__main__', '__mp_main__'):
    if __name__ == '__main__':
        os.environ['VERB_PARTIAL_PRODUCTION_SOURCE'] = sys.argv[1]
        os.environ['VERB_PARTIAL_PRODUCTION_LIMIT'] = sys.argv[2]
    source = Path(os.environ['VERB_PARTIAL_PRODUCTION_SOURCE']).resolve()
    limit = int(os.environ['VERB_PARTIAL_PRODUCTION_LIMIT'])
    assert limit in (100, 1000)
    sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(source/'tools'), str(source)]
    import sweep, v3_run
    from checkpoint_observer import observe
    from timing100_observer import observe_timing
    original_worker, original_longitudinal = v3_run.worker, sweep.run_longitudinal
    sweep.code_commit = lambda: '4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'
    def worker(task):
        return partial_worker(task, limit, source, sweep, original_worker, original_longitudinal, observe, observe_timing)
    v3_run.worker = worker
    if __name__ == '__main__':
        sys.argv = [str(source/'tools/v3_run.py'), *sys.argv[3:]]
        v3_run.main()
