"""完了した試行だけの照合の控えを捨てる、配管だけの探索の旗。

名前・採点・対応・同点の種を変えない。試行内の診断では捨てない。
捨てた完全な鍵は台帳とsideの外へ記録する。検査では再参照を止める。
"""
from collections import Counter
import json
from pathlib import Path

MANAGER = None


class CacheTable(dict):
    def __init__(self, manager, label, data=()):
        super().__init__(data)
        self.manager, self.label = manager, label

    def __contains__(self, key):
        self.manager.lookup(self.label, key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self.manager.lookup(self.label, key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.manager.lookup(self.label, key)
        return super().get(key, default)

    def __setitem__(self, key, value):
        self.manager.epochs[self.label].setdefault(key, self.manager.shared.CTX['trial'])
        return super().__setitem__(key, value)


class Manager:
    labels = ('cache', 'self_cache', 'cache_rng', 'results')

    def __init__(self, shared, path, tombstone):
        self.shared, self.path = shared, Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError('控えを捨てた記録を上書きしない')
        self.stream = shared._text_gzip(self.path)
        self.epochs = {label: {} for label in self.labels}
        self.dead = {label: set() for label in self.labels} if tombstone else None
        self.removed = Counter()
        self.last_trial = None
        self.boundaries = 0
        self.tombstone_hits = 0

    def tables(self):
        return {'cache': self.shared.ENGINE.cache,
                'self_cache': self.shared.ENGINE.self_cache,
                'cache_rng': self.shared.ENGINE.cache_rng,
                'results': self.shared.RESULTS}

    def wrap(self):
        for label, table in self.tables().items():
            if isinstance(table, CacheTable):
                continue
            # 取り付ける前からあった項目は寿命が分からないので残す。
            for key in table:
                self.epochs[label].setdefault(key, None)
            wrapped = CacheTable(self, label, table)
            if label == 'results':
                self.shared.RESULTS = wrapped
            else:
                setattr(self.shared.ENGINE, label, wrapped)

    def lookup(self, label, key):
        if self.dead is not None and key in self.dead[label]:
            from smereplay import encode
            self.tombstone_hits += 1
            (self.path.parent/(self.path.name+'.failure.json')).write_text(json.dumps({
                'table': label, 'trial': self.shared.CTX['trial'], 'key': encode(key),
                'reason': '捨てた鍵が後で引かれた'}, ensure_ascii=False, indent=2)+'\n')
            raise RuntimeError(('SME控えの墓石の検査が不通', label, self.shared.CTX['trial']))

    def enter(self, trial):
        if not isinstance(trial, int):
            raise TypeError('試行の番号が整数でない')
        if self.last_trial is not None and trial < self.last_trial:
            raise RuntimeError('前の試行へ戻る実行では控えを捨てない')
        if self.last_trial is None or trial == self.last_trial:
            self.last_trial = trial
            return
        if not self.shared.CTX.get('call_seed'):
            raise RuntimeError('呼び出しごとの種なしでは控えを捨てない')
        from smereplay import encode
        for label, table in self.tables().items():
            ages = self.epochs[label]
            remove = [key for key in table
                      if ages.get(key) is not None and ages[key] < trial
                      and isinstance(key, tuple) and len(key) >= 2
                      and key[-2] == 'call-seed-v1' and isinstance(key[-1], int)]
            for key in remove:
                self.stream.write(json.dumps({'trial': trial, 'table': label,
                    'created_trial': ages[key], 'key': encode(key)},
                    ensure_ascii=False, separators=(',', ':'))+'\n')
                if self.dead is not None:
                    self.dead[label].add(key)
                dict.__delitem__(table, key)
                self.removed[label] += 1
            # 診断から戻した項目の寿命だけを保持する。値は持たない。
            self.epochs[label] = {key: ages.get(key) for key in table}
        self.stream.flush()
        self.last_trial = trial
        self.boundaries += 1

    def close(self):
        self.stream.close()
        (self.path.parent/(self.path.name+'.summary.json')).write_text(json.dumps({
            'removed': dict(self.removed), 'boundaries': self.boundaries,
            'last_trial': self.last_trial, 'tombstone_enabled': self.dead is not None,
            'tombstone_hits': self.tombstone_hits,
            'kept_entries': {label: len(table) for label, table in self.tables().items()}},
            ensure_ascii=False, indent=2)+'\n')


def install(path, *, tombstone=False):
    global MANAGER
    import abm.loop as loop
    import smeshared as shared
    if not shared.CTX.get('call_seed'):
        raise ValueError('控えの寿命の旗は呼び出しごとの種と一緒に使う')
    manager = MANAGER = Manager(shared, path, tombstone)
    manager.wrap()
    real_restore = shared.ENGINE.restore
    def restore(snapshot):
        real_restore(snapshot)
        manager.wrap()
    shared.ENGINE.restore = restore
    real_input = loop._agent_input
    def agent_input(trial, before):
        # 本物の次の入力の前。同じ試行の二体目では捨てない。
        manager.enter(trial.trial)
        return real_input(trial, before)
    loop._agent_input = agent_input


def close():
    MANAGER.close()
