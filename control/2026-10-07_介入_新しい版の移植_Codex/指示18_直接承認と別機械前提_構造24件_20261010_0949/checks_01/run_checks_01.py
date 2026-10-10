from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import resource
import runpy
import sys
import time

HERE = Path(__file__).resolve().parent
test = HERE.parent / 'candidate01/test_cohort18.py'
assert datetime.now(ZoneInfo('Asia/Tokyo')) < datetime(2026, 10, 13, 9, tzinfo=ZoneInfo('Asia/Tokyo'))
start = time.perf_counter()
code = 0
error = None
old = json.loads((HERE / 'protected_before_01.json').read_text())
sys.argv = [str(test)]
try:
    runpy.run_path(str(test), run_name='__main__')
except SystemExit as e:
    code = e.code or 0
except BaseException as e:
    code, error = 1, repr(e)
    raise
finally:
    after = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in old}
    unchanged = old == after
    if not unchanged:
        code = 1
    result = dict(at_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
                  state='passed' if code == 0 else 'stopped', exitcode=code,
                  pid=os.getpid(), elapsed_seconds=time.perf_counter() - start,
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  protected_before_after_unchanged=unchanged,
                  protected_files=len(old), error=error,
                  model_started=False, cloud_applied=False,
                  fixture_is_real_gate_evidence=False)
    (HERE / 'protected_after_01.json').write_text(json.dumps(after, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'status.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
sys.exit(code)
