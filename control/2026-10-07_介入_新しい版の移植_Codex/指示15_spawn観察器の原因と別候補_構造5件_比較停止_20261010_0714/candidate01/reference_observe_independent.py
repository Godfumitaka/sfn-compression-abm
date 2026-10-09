"""準備版の独立単独を外から読む。返り値・乱数・模型のargvは変えない。"""
import gzip
import json
import os
from pathlib import Path
import random
import sys

spec = json.loads(Path(sys.argv[1]).read_text())
source = Path(spec['cwd'])
folder = Path(spec['evidence'])
sys.path[:0] = [str(source/'tools'), str(source)]
import v3_run
import sweep
from runtime_capture import runtime_record
from v311c_fingerprint import canonical

real_run, real_worker = sweep.run_one, v3_run.worker


def write(path, value):
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False)+'\n')


def run(task):
    import abm.loop as loop
    import smeshared as S
    initial = random.getstate()
    predict, record = loop.predict, loop._ledger_record
    stream = gzip.open(folder/'agent0.runtime.jsonl.gz', 'wt')
    def capture(phase, trial):
        stream.write(json.dumps(dict(phase=phase, trial=trial,
                                    state=canonical(runtime_record())), ensure_ascii=False)+'\n')
    def pre(ai, state, config, rng):
        capture('pre', S.CTX['trial'])
        return predict(ai, state, config, rng)
    def post(agent_id, trial, *a, **kw):
        value = record(agent_id, trial, *a, **kw)
        capture('post', trial.trial)
        write(folder/'agent0.model-rng.jsonl', dict(trial=trial.trial,
              sme_rng=S.ENGINE.rng.getstate(), python_global_unchanged=random.getstate()==initial))
        return value
    loop.predict, loop._ledger_record = pre, post
    try:
        return real_run(task)
    finally:
        stream.close()


def worker(task):
    value = real_worker(task)
    import smeshared as S
    import smereplay as R
    star = sys.modules.get('cstar_runtime')
    if star is not None and star.ENGINE is not None:
        from runtime_capture import runtime_values
        from v311c_fingerprint import canonical
        (folder/'agent0.cstar-final.json').write_text(json.dumps(canonical(runtime_values(star.snapshot())),ensure_ascii=False)+'\n')
    with gzip.open(folder/'agent0.final-sme.jsonl.gz', 'wt') as f:
        def emit(name, value):
            f.write(json.dumps([name, R.encode(value)], ensure_ascii=False, separators=(',',':'))+'\n')
        emit('settings', S.ENGINE.settings)
        emit('sme_rng', S.ENGINE.rng.getstate())
        for name, table in [('cache',S.ENGINE.cache),('self_cache',S.ENGINE.self_cache),
             ('cache_rng',S.ENGINE.cache_rng),('RESULTS',S.RESULTS),('GRAPHS',S.GRAPHS),
             ('CHOICES',S.CHOICES),('STATS',S.STATS),('CTX',S.CTX)]:
            emit(name+'_length',len(table))
            for k,v in table.items(): emit(name,(k,v))
    return value


sweep.run_one, v3_run.worker = run, worker
sys.argv = spec['argv'][1:]
os.chdir(source)
v3_run.main()
