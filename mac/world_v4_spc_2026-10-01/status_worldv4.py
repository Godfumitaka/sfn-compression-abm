"""Codex 自身の走行の進み具合だけを読む。途中の記録は上書きしない。"""
import datetime
import json
import shutil
from run_worldv4 import ROOT, CELL

events = [json.loads(line) for line in (ROOT / "run_events.jsonl").read_text().splitlines()]
started = {(e["arm"], e["seed"]) for e in events if e["kind"] == "start"}
finished = {(e["arm"], e["seed"]) for e in events if e["kind"] == "finished"}
analysed = {(e["arm"], e["seed"]) for e in events if e["kind"] == "analysed"}
active = []
for arm, seed in sorted(started - finished):
    path = ROOT / "runs" / arm / f"seed{seed:03d}/side" / CELL / f"seed{seed:03d}.jsonl"
    trial = None
    if path.exists():
        with path.open("rb") as f:
            start = max(0, path.stat().st_size - 262144)
            f.seek(start)
            lines = f.read().splitlines()
        if start:
            lines = lines[1:]
        for line in reversed(lines):
            try:
                rec = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if rec.get("trial") is not None:
                trial = rec["trial"]
                break
    active.append(dict(arm=arm, seed=seed, latest_trial=trial))
print(json.dumps(dict(time=datetime.datetime.now().isoformat(timespec="seconds"),
                     completed=sum(a.startswith("v4spc_") for a,s in finished), analysed=len(analysed),
                     free_GB=round(shutil.disk_usage(ROOT).free/1e9,3), active=active), ensure_ascii=False))
