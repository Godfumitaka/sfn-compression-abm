"""既存の点検入口を通常受付内で一度呼び、時間だけを別保存する。"""
import datetime
import json
import os
from pathlib import Path
import runpy
import sys
import time
here = Path(__file__).resolve().parent
port = here.parents[1]
started = time.time()
at = datetime.datetime.now().astimezone().isoformat()
code = 0
try:
    sys.argv = [str(port / "instruction12/B5/verify_case_dependency01.py"), "B5_on200_after"]
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else 1
except BaseException:
    code = 1
    raise
finally:
    result = dict(started_at_jst=at, ended_at_jst=datetime.datetime.now().astimezone().isoformat(),
        analysis_seconds=time.time()-started, admission_to_entry_seconds=started-float(os.environ["INTERVENTION_VERIFICATION_SUBMITTED_EPOCH"]),
        cpu_wait_seconds=None, cpu_wait_note="点検入口の独立CPU待機は計測していない", exit_code=code,
        original_verifier_unchanged=True, model_started=False)
    with (here / "verification_timing_01.json").open("x") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write("\n")
sys.exit(code)
