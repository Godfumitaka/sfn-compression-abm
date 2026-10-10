"""模型は変更せず観測する。LinuxのRSS単位と並列時のlock無しだけを扱う。"""
from pathlib import Path
import datetime, gzip, json, os, random, resource, sys, time
ROOT = Path(__file__).resolve().parent
SPEC = json.loads(Path(sys.argv[1]).read_text()) if __name__ == '__main__' else None
START = time.monotonic()
def peak_rss_bytes():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value*1024 if sys.platform.startswith('linux') else value
FOLDER = None

def write(path, row):
    with path.open('a') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

def stamp():
    return {'time': datetime.datetime.now().astimezone().isoformat(), 'elapsed_seconds': time.monotonic()-START}

class TimedLock:
    def __init__(self, real):
        self.real, self.begin, self.seconds = real, None, 0.0
    def acquire(self, *a, **k):
        value = self.real.acquire(*a, **k)
        if value: self.begin = time.monotonic()
        return value
    def release(self):
        value = self.real.release()
        if self.begin is not None:
            self.seconds += time.monotonic()-self.begin
            self.begin = None
        return value
    def active(self):
        return self.seconds + (time.monotonic()-self.begin if self.begin is not None else 0)

class Connection:
    def __init__(self, real, index, lock):
        self.real, self.index, self.lock = real, index, lock
        self.trial = -1
        self.global_initial = random.getstate()
    def send(self, value):
        kind = value.get('type')
        if kind in ('trial','received'): self.trial = value['t']
        if kind == 'received' and SPEC.get('export_final'):
            import smeshared
            write(FOLDER/f'agent{self.index}.rng.jsonl', {'trial':self.trial,
                'sme_rng':smeshared.ENGINE.rng.getstate(),
                'python_global_unchanged':random.getstate()==self.global_initial})
        if kind == 'probe' or kind == 'received' and (self.trial+1)%100==0:
            write(FOLDER/f'agent{self.index}.boundaries.jsonl', {'phase':kind,'trial':self.trial,
                **stamp(),'peak_rss_bytes':peak_rss_bytes(),
                'active_seconds':self.lock.active() if self.lock is not None else None})
        return self.real.send(value)
    def recv(self): return self.real.recv()
    def __getattr__(self, key): return getattr(self.real,key)

def main():
    global FOLDER
    FOLDER = Path(SPEC['evidence'])
    source = Path(SPEC['cwd'])
    sys.path[:0] = [str(source/'tools'),str(source)]
    import v3_run, v311c, sweep
    real_agent, real_run, real_worker = v311c._agent_main, sweep.run_one, v3_run.worker
    locks = {}

    def agent(conn, task):
        index = task['v311c']['agent']
        real_lock = task['v311c'].get('serial_lock')
        lock = TimedLock(real_lock) if real_lock is not None else None
        if lock is not None:
            locks[index] = lock
            task = dict(task, v311c=dict(task['v311c'],serial_lock=lock))
        (FOLDER/f'agent{index}.pid.json').write_text(json.dumps({'pid':os.getpid(),'agent':index}))
        return real_agent(Connection(conn,index,lock),task)

    def run(task):
        # 全ての差し替えの後で、既存の関数を返り値を変えずに包む。
        import abm.loop as loop
        index = v311c.CFG['agent']
        (FOLDER/f'agent{index}.pid.json').write_text(json.dumps({'pid':os.getpid(),'agent':index}))
        global_initial = random.getstate()
        in_probe = [False]
        totals = {'learning_fingerprint':0.0,'snapshot':0.0,'restore':0.0,'trial_audit':0.0}
        real_probe = v311c.probe
        for name,key in [('learning_fingerprint','learning_fingerprint'),('_snapshot_modules','snapshot'),('_restore_modules','restore'),('fingerprint','trial_audit')]:
            original = getattr(v311c,name)
            def clock(*a, _real=original, _key=key, **kw):
                start = time.monotonic()
                try: return _real(*a,**kw)
                finally:
                    if _key != 'trial_audit' or not in_probe[0]: totals[_key] += time.monotonic()-start
            setattr(v311c,name,clock)
        def probe(*a,**kw):
            before = dict(totals); start = time.monotonic(); in_probe[0] = True
            try: return real_probe(*a,**kw)
            finally:
                in_probe[0] = False
                write(FOLDER/f'agent{index}.probe-times.jsonl', {'trial':v311c.CTX.get('t'),
                    'seconds':time.monotonic()-start,
                    'parts_seconds':{k:totals[k]-before[k] for k in totals},**stamp()})
        v311c.probe = probe
        real_input, real_record = loop._agent_input, loop._ledger_record
        begin = {}
        def agent_input(trial,before):
            begin['time'] = time.monotonic()
            return real_input(trial,before)
        def ledger_record(agent_id,trial,*a,**kw):
            result = real_record(agent_id,trial,*a,**kw)
            write(FOLDER/f'agent{index}.performance.jsonl', {'trial':trial.trial,
                'seconds_including_wait_and_probe':time.monotonic()-begin['time'],
                'peak_rss_bytes':peak_rss_bytes(),
                'active_seconds':locks[index].active() if index in locks else None,'timer_totals':dict(totals),**stamp()})
            if SPEC.get('export_final'):
                import smeshared
                write(FOLDER/f'agent{index}.model-rng.jsonl', {'trial':trial.trial,
                    'sme_rng':smeshared.ENGINE.rng.getstate(),
                    'python_global_unchanged':random.getstate()==global_initial})
            return result
        loop._agent_input,loop._ledger_record = agent_input,ledger_record
        return real_run(task)

    def worker(task):
        value = real_worker(task)
        # 模型の計算とnative出力を閉じた後で、最終控えを項目ごとに全量保存する。
        # この検証専用の区間を別記し、旗の時間には含めない。乱数は読むだけ。
        if not SPEC.get('export_final'):return value
        star = sys.modules.get('cstar_runtime')
        if star is not None and star.ENGINE is not None:
            from runtime_capture import runtime_values
            from v311c_fingerprint import canonical
            (FOLDER/f'agent{task["v311c"]["agent"]}.cstar-final.json').write_text(json.dumps(canonical(runtime_values(star.snapshot())),ensure_ascii=False)+'\n')
        import smeshared, smereplay
        index = task['v311c']['agent']
        write(FOLDER/f'agent{index}.validation.jsonl',{'phase':'begin',**stamp()})
        with gzip.open(FOLDER/f'agent{index}.final-sme.jsonl.gz','wt') as f:
            def emit(name,value):
                f.write(json.dumps([name,smereplay.encode(value)],ensure_ascii=False,separators=(',',':'))+'\n')
            emit('settings',smeshared.ENGINE.settings)
            emit('sme_rng',smeshared.ENGINE.rng.getstate())
            for name,table in [('cache',smeshared.ENGINE.cache),('self_cache',smeshared.ENGINE.self_cache),
                ('cache_rng',smeshared.ENGINE.cache_rng),('RESULTS',smeshared.RESULTS),('GRAPHS',smeshared.GRAPHS),
                ('CHOICES',smeshared.CHOICES),('STATS',smeshared.STATS),('CTX',smeshared.CTX)]:
                emit(name+'_length',len(table))
                for k,v in table.items(): emit(name,(k,v))
        write(FOLDER/f'agent{index}.validation.jsonl',{'phase':'end',**stamp()})
        return value

    v311c._agent_main, sweep.run_one, v3_run.worker = agent,run,worker
    sys.argv = SPEC['argv'][1:]
    os.chdir(source)
    if SPEC.get('solo_agent') is not None:
        sys.path.insert(0,str(source/'tools/v311c_checks'))
        import coll8_solo
    v3_run.main()

if __name__ == '__main__': main()
