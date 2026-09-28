import concurrent.futures as cf
class SyncExecutor:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def submit(self, fn, *a, **k):
        f = cf.Future()
        try: f.set_result(fn(*a, **k))
        except Exception as e: f.set_exception(e)
        return f
    def shutdown(self, *a, **k): pass
cf.ProcessPoolExecutor = SyncExecutor
