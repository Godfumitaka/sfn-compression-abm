"""共有受付の内側でCPU枠を待つ。過程数が上限を超えたら自分の組だけ待機する。"""
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import time


def census():
    rows = {}
    # macOSはargsを後ろに置くとcommを短く切る。幅指定と実行ファイル名も使う。
    text = subprocess.check_output(["/bin/ps", "-axww", "-o", "pid=,ppid=,rss=,stat=,comm=,args="], text=True)
    for line in text.splitlines():
        parts = line.split(None, 5)
        if len(parts) != 6:continue
        pid, parent, rss, state, name, command = parts
        executable = command.split(None, 1)[0].lower()
        is_python = any(word in name.lower() or word in executable for word in ("python", "pypy"))
        # SIGSTOPで止まった過程は計算しない。互いの待機をCPU占有と数えない。
        heavy = is_python and not state.startswith("T") and "resource_tracker" not in command and "jobs.py" not in command and (
            "spawn_main" in command or (state.startswith("R") and int(rss) >= 100 * 1024))
        rows[int(pid)] = (int(parent), heavy)
    return rows


def descendants(rows, pid):
    chosen = {pid}
    while True:
        extra = {p for p, (parent, _heavy) in rows.items() if parent in chosen}
        if extra <= chosen:return chosen
        chosen |= extra


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[0] == "--" else args.command
    limit = int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.physicalcpu"], text=True)) - 2
    assert limit >= 1
    path = Path(args.log);path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as log:
        def record(event, **values):
            log.write(json.dumps({"time_ns": time.time_ns(), "event": event,
                "cpu_limit": limit, **values}, ensure_ascii=False) + "\n");log.flush()
        while True:
            rows = census();own = descendants(rows, os.getpid())
            outside = sum(heavy for pid, (_parent, heavy) in rows.items() if pid not in own)
            # 各指令は一過程／worker一つ。開始後も全体を数え、自分の組だけ待機する。
            if outside + 1 <= limit:break
            record("wait_before_start", outside_heavy=outside)
            time.sleep(10)
        thermal = subprocess.check_output(["/usr/bin/pmset", "-g", "therm"], text=True)
        if any(s in thermal for s in ("warning level has been recorded", "Speed_Limit")):
            # jobsの条件と同じ。値があるときだけ再確認する。
            import re
            m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", thermal)
            warning = any("warning" in line.lower() and "no " not in line.lower() for line in thermal.splitlines())
            assert not warning and (m is None or m.group(1) == "100"), thermal
        process = subprocess.Popen(command, cwd=args.cwd, start_new_session=True)
        def interrupted(signum, _frame):
            # 終了の指示が来たとき、受付から離れた自分の組を残さない。
            try:
                os.killpg(process.pid, signal.SIGCONT)
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:pass
            record("interrupted", signal=signum)
            raise SystemExit(128 + signum)
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        record("started", model_parent_pid=process.pid, outside_heavy=outside)
        paused = False
        max_outside = outside
        while process.poll() is None:
            rows = census();own = descendants(rows, process.pid)
            outside = sum(heavy for pid, (_parent, heavy) in rows.items() if pid not in own and pid != os.getpid())
            inside = sum(rows[p][1] for p in own if p in rows)
            max_outside = max(max_outside, outside)
            should_pause = outside + max(inside, 1) > limit
            if should_pause != paused:
                try:os.killpg(process.pid, signal.SIGSTOP if should_pause else signal.SIGCONT)
                except ProcessLookupError:break
                paused = should_pause
                record("paused" if paused else "resumed", outside_heavy=outside, own_heavy=inside)
            time.sleep(1)
        record("finished", exit_code=process.wait(), max_outside_heavy=max_outside)
        raise SystemExit(process.returncode)


if __name__ == "__main__":main()
