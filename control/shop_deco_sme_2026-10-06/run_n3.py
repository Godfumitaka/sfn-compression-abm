"""承認済みのN3・80本だけを、一走行・一解析ずつ共有受付へ渡す。"""
from datetime import datetime
from pathlib import Path
import json
import os
import signal
import subprocess
import threading
import time
import traceback
from common import ROOT, AREA, PYTHON, command, registered, digest

HERE = Path(__file__).resolve().parent
PREVIEW = AREA / "preview_n3"
OLD = AREA.parent / "codex_shop_deco_2026-10-04"


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def source_hashes():
    return {str(p.relative_to(ROOT)): digest(p) for folder in ("abm", "tools")
            for p in sorted((ROOT / folder).rglob("*.py"))}


def stop_old(start_log, errors, done):
    try:
        while not done.is_set():
            if start_log.exists() and any(json.loads(s)["event"] == "started" for s in start_log.read_text().splitlines()):
                break
            time.sleep(1)
        else:return
        if (PREVIEW / "old_stop.json").exists():return
        old = json.loads((OLD / "preview/progress.json").read_text())
        ps = subprocess.check_output(["/bin/ps", "-axww", "-o", "pid=,ppid=,args="], text=True)
        stopped = []
        for line in ps.splitlines():
            fields = line.split(None, 2)
            if len(fields) != 3:continue
            pid, parent, args = fields
            if "python" in args.lower() and any(str(OLD / p) in args for p in ("preview", "source/control/shop_deco_2026-10-04")):
                stopped.append(int(pid))
        for pid in stopped:
            try:os.kill(pid, signal.SIGCONT);os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:pass
        marks = {}
        for folder in ("runs", "analysis"):
            base = OLD / "preview" / folder
            for p in base.glob("*/resources.json"):
                assert int(p.parent.name.rsplit("_s", 1)[1]) in range(1, 6)
                marks[str(p.relative_to(OLD / "preview"))] = digest(p)
        for p in (OLD / "preview/runs").glob("*/ledgers/cells/*/seed*.done"):
            assert 1 <= int(p.name[4:7]) <= 5
            marks[str(p.relative_to(OLD / "preview"))] = digest(p)
        stamp = datetime.now().astimezone().isoformat()
        result = {"stopped_at": stamp, "reason": "SMEのN3先行下見の開始により旧版の残りを停止",
            "runs_completed": old["runs_completed"], "analyses_completed": old["analyses_completed"],
            "last_current": old["current"], "terminated_pids": stopped, "original_completion_marks_sha256": marks}
        save(PREVIEW / "old_stop.json", result)
        save(PREVIEW / "old_progress_before_stop.json", old)
        old.update(status="stopped", stopped_at=stamp, stopped_reason=result["reason"],
                   migrated_to=str(PREVIEW), output_preserved=True)
        save(OLD / "preview/progress.json", old)
    except BaseException:errors.append(traceback.format_exc())


def main():
    PREVIEW.mkdir(exist_ok=True)
    assert json.loads((AREA / "gates/run_gate.json").read_text())["passed"]
    assert json.loads((HERE / "gates/world_gate.json").read_text())["passed"]
    fingerprints = source_hashes()
    assert fingerprints == json.loads((AREA / "gates/run_gate.json").read_text())["source_sha256"]["ported"]
    pilot = {"selection": "N3", "retention": "D", "world": 2, "seed": 1, "level": "plus8"}
    items = [pilot] + [{"selection": "N3", "retention": r, "world": w, "seed": s, "level": l}
        for s in range(1, 6) for r in ("A", "D") for w in (1, 2)
        for l in ("skeleton", "current", "plus4", "plus8")
        if (r, w, s, l) != ("D", 2, 1, "plus8")]
    for item in items:
        item["tag"] = f"{item['level']}_N3_{item['retention']}_w{item['world']}_s{item['seed']:03d}"
    assert len(items) == 80 and len({x["tag"] for x in items}) == 80
    prereg = json.loads((HERE / "preregistration.json").read_text())
    plan = {"selection": "N3", "planned": 80, "items": items, "trial_count": 1740,
        "lambda": "0.01873710622997919", "U": "global", "D_tau": 0.4,
        "support_work": "N3の80本の報告後まで保留（2026-10-06利用者の順序変更）",
        "predictions": {k: prereg[k] for k in ("P-05c", "D-04v")},
        "run_memory_budget_gb": 1.0, "analysis_memory_budget_gb": 3.0}
    if (PREVIEW / "plan.json").exists():assert json.loads((PREVIEW / "plan.json").read_text()) == plan
    save(PREVIEW / "plan.json", plan);save(PREVIEW / "source_sha256.json", fingerprints)
    progress = json.loads((PREVIEW / "progress.json").read_text()) if (PREVIEW / "progress.json").exists() else {
        "status": "starting", "planned": 80, "runs_completed": 0, "analyses_completed": 0,
        "started_at": datetime.now().astimezone().isoformat(), "records": [], "current": None}
    progress["controller_pid"] = os.getpid()
    save(PREVIEW / "progress.json", progress)
    completed = {r["tag"] for r in progress["records"]}
    from report_n3 import publish
    try:
        publish()
        for item in items:
            if item["tag"] in completed:continue
            assert source_hashes() == fingerprints, "模型の実ファイルが下見の途中で変更された"
            run = PREVIEW / "runs" / item["tag"]
            analysis = PREVIEW / "analysis" / item["tag"]
            progress.update(status="running", current={**item, "phase": "run"}, updated_at=datetime.now().astimezone().isoformat())
            save(PREVIEW / "progress.json", progress)
            errors = [];finished = threading.Event()
            observer = threading.Thread(target=stop_old, args=(run / "cpu.jsonl", errors, finished), daemon=True)
            observer.start()
            try:
                registered(command(run, item["world"], item["seed"], item["retention"], item["level"]),
                    run, "shop-deco-sme-n3-" + item["tag"], mem=1.0)
            finally:
                finished.set();observer.join(timeout=15)
            assert not errors, errors
            progress["runs_completed"] = len(list((PREVIEW / "runs").glob("*/resources.json")))
            progress["current"]["phase"] = "analysis"
            save(PREVIEW / "progress.json", progress)
            if progress["analyses_completed"] == 0:publish()
            registered([PYTHON, "-B", str(HERE / "analyse_run.py"), str(run), str(item["seed"]), str(analysis)],
                analysis, "shop-deco-sme-n3-analysis-" + item["tag"], mem=3.0, result_file="validation.json")
            assert json.loads((analysis / "validation.json").read_text())["passed"]
            progress["records"].append({**item, "summary": str(analysis / "summary.json"),
                "run_resources": str(run / "resources.json"), "analysis_resources": str(analysis / "resources.json"),
                "validation_sha256": digest(analysis / "validation.json")})
            progress["analyses_completed"] = len(progress["records"])
            progress["updated_at"] = datetime.now().astimezone().isoformat()
            save(PREVIEW / "progress.json", progress)
        progress.update(status="complete", current=None, completed_at=datetime.now().astimezone().isoformat())
        save(PREVIEW / "progress.json", progress)
        publish()
    except BaseException:
        progress.update(status="stopped", stopped_reason=traceback.format_exc(), stopped_at=datetime.now().astimezone().isoformat())
        save(PREVIEW / "progress.json", progress)
        try:publish()
        except BaseException:
            save(PREVIEW / "report_error.json", {"error": traceback.format_exc()})
        raise


if __name__ == "__main__":main()
