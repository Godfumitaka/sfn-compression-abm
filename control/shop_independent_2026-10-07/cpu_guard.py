"""Local check immediately inside jobs.py; never modifies shared registry rules."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--record", required=True)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ["--"] else args.command
text = subprocess.check_output(["/bin/ps", "-axww", "-o", "pid=,ppid=,rss=,stat=,comm=,args="], text=True)
workers, other, own = [], [], []
for line in text.splitlines():
    row = line.strip().split(None, 5)
    if len(row) != 6:
        continue
    pid, ppid, rss, state, short_comm, cmd = row
    # macOS ps truncates `comm` even with -ww; `args` retains the executable.
    executable = cmd.split(None, 1)[0]
    if not ("python" in executable.lower() or "pypy" in executable.lower()):
        continue
    if "resource_tracker" in cmd or "/jobs/jobs.py" in cmd:
        continue
    data = {"pid": int(pid), "ppid": int(ppid), "rss_kib": int(rss), "state": state, "command": cmd}
    if "shop_independent_2026-10-07" in cmd:
        own.append(data)
    if "T" in state or int(pid) == os.getpid():
        continue
    if "spawn_main" in cmd:
        workers.append(data)
    elif "R" in state and int(rss) >= 100*1024:
        other.append(data)
record = {"time_jst": datetime.now().astimezone().isoformat(), "model_workers": workers,
          "other_heavy_R": other, "admission_count": len(workers)+len(other), "own": own,
          "rule": "exclude T, jobs.py and resource_tracker; count non-T spawn_main plus other Python R with RSS>=100MiB"}
path = Path(args.record)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({"model_workers": len(workers), "other_heavy_R": len(other),
                  "pids": [r["pid"] for r in workers+other]}, ensure_ascii=False), flush=True)
if len(workers)+len(other) >= 8:
    print("CPU slots full: no calculation started", flush=True)
    sys.exit(78)
sys.exit(subprocess.call(command))
