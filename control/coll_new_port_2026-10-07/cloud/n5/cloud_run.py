"""八体のクラウド用の実行準備。既定は計画表示だけで、AWS資源は作らない。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
COMMIT = "c4cfed12a3944071951775b2c9373ca27705fb25"
DEADLINE = datetime(2026, 10, 9, tzinfo=timezone.utc)


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def flag(argv, name):
    return argv[argv.index(name) + 1]


def validate(spec):
    argv = spec["model_argv"]
    assert spec["commit"] == COMMIT
    assert spec["models"] == 8
    assert argv[:3] == ["tools/v3_run.py", "{config}", "{output}"]
    assert flag(argv, "--workers") == "1"
    assert flag(argv, "--v311c-b-n") == "8"
    assert flag(argv, "--v311c-runs") == "1"
    assert len(flag(argv, "--v311c-f").split(",")) == 8
    assert spec["parallel"] == ("--v311c-serial" not in argv)
    assert not any(x in argv for x in ("--stage2-reuse", "--trial-gc", "--fast-json"))
    seeds = spec["seeds"]
    assert seeds and all(type(x) is int and 1 <= x <= 5 for x in seeds)
    assert flag(argv, "--seeds") == ",".join(map(str, seeds))
    assert spec["phase"] in ("off200", "measure300", "production1740")
    assert int(flag(argv, "--trial-count")) == {
        "off200": 200, "measure300": 300, "production1740": 1740
    }[spec["phase"]]
    assert len(seeds) == 1, "一つのspecは一つの集団種。一括並行投入をしない"
    if spec["phase"] == "off200":
        assert flag(argv, "--v311c-q") == "0"
        assert flag(argv, "--v311c-m") == "0"
        assert "--attn-allin" not in argv and "--score-logp" not in argv
    else:
        assert "--attn-allin" in argv and "--score-logp" in argv
        assert flag(argv, "--stage2-birth-hu") == "on"
        assert "--cf-value" not in argv
        assert "--score-logp-e" not in argv
        if spec["phase"] == "production1740":
            assert spec["parallel"] and "{L50_ref}" in argv
    return spec


def materialize(spec, source, output, evidence, python, price):
    validate(spec)
    assert hashlib.sha256((HERE / "shop-seed1.json").read_bytes()).hexdigest() == spec["config_sha256"]
    replacements = {"{config}": str(HERE / "shop-seed1.json"), "{output}": str(output)}
    if "{L50_ref}" in spec["model_argv"]:
        assert price is not None and price > 0, "較正済みL50_refが未指定"
        replacements["{L50_ref}"] = str(price)
    argv = [python] + [replacements.get(x, x) for x in spec["model_argv"]]
    return {**spec, "plan_spec_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
            "argv": argv, "cwd": str(source), "output": str(output),
            "evidence": str(evidence), "export_final": spec["phase"] == "off200",
            "solo_agent": None, "env": {"PYTHONHASHSEED": "0"}}


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


def prerequisite(spec, gate_root, queue_proof):
    for name in spec["requires"]:
        record = read(gate_root / name)
        assert record["passed"] is True, ("必要な関門が未合格", name)
        assert record["candidate"] == COMMIT, ("関門の版が違う", name)
    if spec["phase"] == "production1740":
        assert queue_proof is not None, "#20の最新の通常push済み取得記録が必要"
        proof = read(queue_proof)
        assert proof["row"] == "20" and proof["commit"] == COMMIT
        assert proof["status"].startswith("走行中") and proof["normal_push_confirmed"] is True
        assert proof["spec_sha256"] == hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        assert re.fullmatch(r"[0-9a-f]{40}", proof["results_commit"])
        assert proof["lambda_source"] == "L50_ref"


def registered(args):
    # この入口はクラウドのjobs.pyからだけ呼ぶ。予約と環境の設定を変更しない。
    assert sys.platform.startswith("linux"), "マックの本番・並列走行は禁止"
    assert datetime.now(timezone.utc) < DEADLINE, "期限後に新しい模型を始めない"
    spec = read(args.runtime)
    validate(spec)
    assert spec["reservation_gb"] is not None
    source, output, evidence = map(Path, (spec["cwd"], spec["output"], spec["evidence"]))
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() == COMMIT
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=source)
    assert len(os.sched_getaffinity(0)) >= 8, "八体の枠が必要"
    assert not output.exists() and not (evidence / "process.json").exists()
    rows = processes()
    assert not counted(rows, descendants(rows, os.getpid())), "他の模型等がある。八体を始めない"
    assert shutil.disk_usage(output.parent).free >= 20 * 2**30
    assert not read(args.resource_clearance)["warning"], "資源の警告時は新しく始めない"
    clearance = read(args.resource_clearance)
    assert clearance["spec_sha256"] == spec["plan_spec_sha256"]
    assert clearance["source"] == str(source) and clearance["output"] == str(output)
    assert clearance["reservation_gb"] == spec["reservation_gb"]
    save(evidence / "start.json", {"time": now(), "models_including_idle": 8,
                                  "computing_upper_bound": 8 if spec["parallel"] else 1,
                                  "processes_before": rows, "reservation_gb": spec["reservation_gb"],
                                  "python": sys.version, "platform": platform.platform()})
    start = time.monotonic()
    peak = 0
    warnings = set()
    with (evidence / "stdout.log").open("x") as log, (evidence / "resources.jsonl").open("x") as resource_log:
        child = subprocess.Popen([spec["argv"][0], str(HERE / "observe.py"), args.runtime],
                                 cwd=source, env={**os.environ, **spec["env"]}, stdout=log,
                                 stderr=subprocess.STDOUT)
        save(evidence / "process.json", {"pid": child.pid, "started": now()})
        # 既に走行中の模型や他係の過程へ信号を送らない。
        while child.poll() is None:
            rows = processes()
            own = descendants(rows, child.pid)
            rss = sum(r["rss_bytes"] for r in rows if r["pid"] in own)
            peak = max(peak, rss)
            if rss > spec["reservation_gb"] * 1e9:
                warnings.add("RSSが予約を超えた")
            if counted(rows, own | descendants(rows, os.getpid())):
                warnings.add("別の模型等の開始を検出")
            if shutil.disk_usage(output.parent).free < 20 * 2**30:
                warnings.add("空き20GiB未満")
            resource_log.write(json.dumps({"time": now(), "rss_sum_bytes": rss,
                                           "models_including_idle": 8,
                                           "warnings": sorted(warnings)}, ensure_ascii=False) + "\n")
            resource_log.flush()
            time.sleep(1)
        result = {"name": spec["name"], "candidate": COMMIT, "exitcode": child.returncode,
                  "elapsed_seconds": time.monotonic() - start, "rss_sum_peak_bytes": peak,
                  "models_including_idle": 8, "parallel": spec["parallel"], "warnings": sorted(warnings),
                  "cpu_note": "実CPU秒は未計測。芯×実時間は計画量として別記。"}
        save(evidence / "resource.json", result)
        if child.returncode or warnings:
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("spec")
    run = sub.add_parser("run")
    run.add_argument("spec")
    for p in (run,):
        p.add_argument("--source", type=Path, required=True)
        p.add_argument("--root", type=Path, required=True)
        p.add_argument("--python", required=True)
        p.add_argument("--jobs", type=Path, required=True)
        p.add_argument("--gate-root", type=Path, required=True)
        p.add_argument("--resource-clearance", type=Path, required=True)
        p.add_argument("--queue-proof", type=Path)
        p.add_argument("--l50-ref", type=float)
    reg = sub.add_parser("registered")
    reg.add_argument("runtime")
    reg.add_argument("--resource-clearance", required=True)
    args = parser.parse_args()
    if args.mode == "registered":
        return registered(args)
    spec = validate(read(args.spec))
    if args.mode == "plan":
        print(json.dumps({"spec": spec, "starts_model": False,
                          "ready_for_submission": False}, ensure_ascii=False, indent=2))
        return
    assert sys.platform.startswith("linux") and datetime.now(timezone.utc) < DEADLINE
    assert spec["reservation_gb"] is not None, "実測に基づく受付予約が未確定"
    prerequisite(spec, args.gate_root, args.queue_proof)
    assert args.jobs.is_file() and args.resource_clearance.is_file()
    evidence = args.root / "evidence" / spec["name"]
    output = args.root / "outputs" / spec["name"]
    assert not evidence.exists() and not output.exists(), "保存済み・開始済みを再走行しない"
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=False)
    runtime = materialize(spec, args.source.resolve(), output.resolve(), evidence.resolve(), args.python, args.l50_ref)
    save(evidence / "runtime.json", runtime)
    command = [args.python, str(args.jobs), "run", "--wait", "--owner", "Codex3 N5 " + spec["name"],
               "--mem", str(spec["reservation_gb"]), "--disk-path", str(output), "--",
               args.python, str(HERE / "cloud_run.py"), "registered", str(evidence / "runtime.json"),
               "--resource-clearance", str(args.resource_clearance)]
    save(evidence / "admission-command.json", {"command": command, "time": now()})
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main() or 0)
