"""受付の枠内で、13本を一つずつ実行・比較する。不通の後は走らせない。"""
from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import sys
import threading
import time

from compare_expanded import compare

ROOT = Path(__file__).resolve().parent
KEY = ROOT.parent / "codex_sme_keyfast_2026-10-04"
ns = {"__file__": str(ROOT / "resources.py")}
exec((KEY / "run_profiles.py").read_text().split("for name in ('profile_A_01'")[0], ns)
conditions, guard, STOP = ns["conditions"], ns["guard"], ns["STOP"]
plan = json.loads((ROOT / "plan_small_01.json").read_text())
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
    thread.start()
    start = time.perf_counter()
    with (folder / "run.log").open("w") as log:
        rc = subprocess.run([item["interpreter"], str(ROOT / "observe.py"), str(folder / "command.json")],
                            env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    STOP.set(); thread.join()
    result = {"exit": rc, "wall_seconds": time.perf_counter() - start,
              "finished": datetime.now().astimezone().isoformat()}
    (folder / "run_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(folder.name, result, flush=True)
    if rc or (folder / "resource_stop.json").exists():
        raise SystemExit(1)
    proof = compare(Path(item["reference"]) / "output", folder / "output", folder / "comparison.json")
    print(folder.name, "expanded_equal", proof["all_equal"], "first", proof["first_difference"], flush=True)
    if not proof["all_equal"]:
        raise SystemExit(2)
(ROOT / "small_complete_01.json").write_text(json.dumps({"passed": True, "cases": len(plan)}, indent=2) + "\n")
