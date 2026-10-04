"""段2の別々の変更と合わせた変更を、小走行から順に確かめる。"""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import threading
import time

from compare_body import compare

ROOT = Path(__file__).resolve().parent
KEY = ROOT.parent / "codex_sme_keyfast_2026-10-04"
ns = {"__file__": str(ROOT / "resource_conditions.py")}
exec((KEY / "run_profiles.py").read_text().split("for name in ('profile_A_01'")[0], ns)
conditions, guard, STOP = ns["conditions"], ns["guard"], ns["STOP"]
plan = json.loads((ROOT / "small_plan_01.json").read_text())
completed = []
for item in plan:
    folder = Path(item["folder"])
    row = conditions()
    assert row["free_bytes"] >= 20 * 2**30 and not row["swap_grew"] and not row["thermal_warning"], row
    assert not (folder / "run.log").exists(), "二重に走らせない"
    (folder / "resources_start.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
    env = dict(os.environ, SME_EXACT_SOURCE=item["source"], PYTHONHASHSEED="0")
    for k in ("LC_ALL", "LANG", "LC_CTYPE"):
        env.pop(k, None)
    STOP.clear()
    thread = threading.Thread(target=guard, args=(folder,), daemon=True)
    thread.start(); begin = time.perf_counter()
    with (folder / "run.log").open("w") as log:
        rc = subprocess.run([sys.executable, str(ROOT / "observe.py"), str(folder / "command.json")],
                            env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    STOP.set(); thread.join()
    result = {"exit": rc, "wall_seconds": time.perf_counter() - begin,
              "at": datetime.datetime.now().astimezone().isoformat()}
    (folder / "run_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(item["mode"], folder.name, result, flush=True)
    if rc or (folder / "resource_stop.json").exists():
        raise SystemExit(1)
    proof = compare(Path(item["reference"]) / "output", folder / "output", folder / "body_comparison.json")
    print("body", proof["passed"], flush=True)
    if not proof["passed"]:
        raise SystemExit(2)
    completed.append({"mode": item["mode"], "case": folder.name, "passed": True})
    (ROOT / "small_progress_01.json").write_text(json.dumps(completed, indent=2) + "\n")
(ROOT / "small_complete_01.json").write_text(json.dumps({"passed": True, "cases": completed}, indent=2) + "\n")
