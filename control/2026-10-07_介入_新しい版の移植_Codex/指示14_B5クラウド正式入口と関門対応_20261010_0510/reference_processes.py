"""Linuxの過程を読む。待機中の個体を数え、T/Zは除く。"""
import subprocess,re
from pathlib import Path

def processes():
    raw = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,stat=,pcpu=,rss=,args="], text=True
    )
    rows = []
    for line in raw.splitlines():
        fields = line.strip().split(None, 5)
        if len(fields) != 6:
            continue
        pid, parent, state, cpu, rss, command = fields
        rows.append({"pid": int(pid), "parent": int(parent), "state": state,
                     "cpu": float(cpu), "rss_bytes": int(rss) * 1024, "command": command})
    return rows

def descendants(rows, pid):
    own = {pid}
    while True:
        grown = own | {r["pid"] for r in rows if r["parent"] in own}
        if grown == own:
            return own
        own = grown

def counted(rows, excluded=()):
    parents = {r["parent"] for r in rows}
    result = []
    for r in rows:
        cmd = r["command"]
        if r["pid"] in excluded or r["pid"] in parents or "T" in r["state"] or "Z" in r["state"]:
            continue
        if not re.fullmatch(r"python(?:3(?:\.\d+)?)?", Path(cmd.split()[0]).name, re.I):
            continue
        if "jobs.py" in cmd or "resource_tracker" in cmd:
            continue
        if any(x in cmd for x in ("v3_run.py", "spawn_main", "forkserver", "observe.py")) or r["rss_bytes"] >= 100 * 1024**2 or r["cpu"] >= 5:
            result.append(r)
    return result
