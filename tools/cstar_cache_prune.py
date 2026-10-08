"""指示26。過去の呼び出し種の控えだけを試行境界で捨て、再参照を止める。"""
from pathlib import Path
import gzip
import json


class PruneGuard:
    def __init__(self, path=None):
        self.trial = None
        # 深い対応や値は持たない。捨てた鍵の種の由来だけを見張りに残す。
        self.origins = {}
        self.requests = {'mapping':0, 'engine':0}
        self.forbidden_reads = 0
        self.boundaries = 0
        self.removed = {'cache':0, 'cache_rng':0}
        self.path = Path(path) if path else None
        self.stream = gzip.open(self.path,'xt',encoding='utf-8') if self.path else None

    def record(self, row):
        if self.stream:
            self.stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            self.stream.flush()

    def snapshot(self):
        # 試行の文脈は反実仮想で復元する。監査の回数・由来は診断として残す。
        return self.trial

    def restore(self, trial):
        self.trial = trial

    @staticmethod
    def seed(key):
        return key[-1] if isinstance(key,tuple) and len(key)>=2 and key[-2]=='call-seed-v1' else None

    def request(self, key, trial, where):
        seed = self.seed(key)
        if seed is None: return
        self.requests[where] += 1
        if trial != self.trial:
            raise RuntimeError(('C*の試行の文脈が不一致',self.trial,trial))
        origin = self.origins.get(seed,trial)
        if origin != trial:
            self.forbidden_reads += 1
            self.record(dict(kind='forbidden_read',trial=trial,origin=origin,seed=seed,where=where,
                             forbidden_reads=self.forbidden_reads))
            raise RuntimeError('過去の呼び出し種の控えを参照した')
        self.origins[seed] = trial

    def begin_trial(self, engine, trial):
        if self.trial == trial: return
        removed = {}
        for name in ('cache','cache_rng'):
            table = getattr(engine,name)
            dead = []
            for key in table:
                seed = self.seed(key)
                if seed is not None:
                    if seed not in self.origins:
                        raise RuntimeError('C*の控えの種に由来の記録が無い')
                    if self.origins[seed] != trial: dead.append(key)
            for key in dead: del table[key]
            removed[name] = len(dead); self.removed[name] += len(dead)
        self.trial = trial; self.boundaries += 1
        self.record(dict(kind='trial_boundary',trial=trial,removed=removed,
                         cache_count=len(engine.cache),cache_rng_count=len(engine.cache_rng),
                         self_cache_count=len(engine.self_cache),forbidden_reads=self.forbidden_reads))

    def close(self, native_loop_returned):
        summary = dict(enabled=True,trial=self.trial,boundaries=self.boundaries,requests=self.requests,
                       removed=self.removed,forbidden_reads=self.forbidden_reads,
                       remembered_seed_origins=len(self.origins),native_loop_returned=native_loop_returned)
        if self.stream:
            self.record(dict(kind='summary',**summary)); self.stream.close(); self.stream=None
            Path(str(self.path)+'.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        return summary
