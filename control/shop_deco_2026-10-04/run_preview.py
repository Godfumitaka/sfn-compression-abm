"""段4の160本。模型走行も読取も一本ずつ受付で待ち、失敗したら停止する。"""
from datetime import datetime
from pathlib import Path
import itertools
import hashlib
import json
import subprocess
import traceback
from run_registered import AREA, CONFIG, PYTHON, ROOT, command, registered


def main():
    dest = AREA / "preview"
    dest.mkdir(exist_ok=True)
    gate = json.loads((ROOT / "control/shop_deco_2026-10-04/stage3/run_gate_approved.json").read_text())
    assert gate["passed"]
    model_files = subprocess.check_output(["git", "ls-files", "abm", "tools", "config/sweep_shop_hide1_s1_2026-10-01.json"], cwd=ROOT, text=True).splitlines()
    model_files = [name for name in model_files if name.endswith((".py", ".json"))]
    fingerprints = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in model_files}
    combinations = list(itertools.product(range(1, 6), ("N3", "support"), ("A", "D"), (1, 2),
                                          ("skeleton", "current", "plus4", "plus8")))
    pilot = (1, "N3", "D", 2, "plus8")
    combinations.remove(pilot); combinations.insert(0, pilot)
    assert len(combinations) == len(set(combinations)) == 160
    plan = [{"seed": seed, "selection": selection, "retention": retention, "world": world, "level": level,
             "tag": f"{level}_{selection}_{retention}_w{world}_s{seed:03d}"}
            for seed, selection, retention, world, level in combinations]
    (dest / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    (dest / "model_fingerprints.json").write_text(json.dumps(fingerprints, indent=2) + "\n")
    progress = {"status": "running", "planned": 160, "runs_completed": 0, "analyses_completed": 0,
                "started_at": datetime.now().isoformat(), "current": None, "run_memory_budget_gb": 0.5,
                "analysis_memory_budget_gb": 0.8, "records": []}
    path = dest / "progress.json"

    def save():
        progress["updated_at"] = datetime.now().isoformat()
        path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n")

    save()
    try:
        for row in plan:
            assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in fingerprints.items()), "模型のファイルが開始後に変わった"
            assert 1 <= row["seed"] <= 5
            tag = row["tag"]
            out, analysis_out = dest / "runs" / tag, dest / "analysis" / tag
            progress["current"] = {**row, "phase": "run"}; save()
            run = registered(command(CONFIG, out, row["selection"], row["retention"], row["world"], row["seed"], row["level"]),
                             out, f"Codex-shop-deco-preview-{tag}", mem=0.5)
            assert run["peak_descendants_rss_bytes"] <= 0.5e9, f"走行の受付見込みを超えた: {tag}"
            progress["runs_completed"] += 1; save()
            progress["current"]["phase"] = "analysis"; save()
            result = registered([PYTHON, "-B", "control/shop_deco_2026-10-04/analyse_run.py", str(out), str(row["seed"]), str(analysis_out)],
                                analysis_out, f"Codex-shop-deco-read-{tag}", mem=0.8, result_file="summary.json")
            assert result["peak_descendants_rss_bytes"] <= 0.8e9, f"解析の受付見込みを超えた: {tag}"
            summary = json.loads((analysis_out / "summary.json").read_text())
            assert summary["trial_count"] == 1740 and not summary["pilot_all_spoken"]
            progress["analyses_completed"] += 1
            progress["records"].append({**row, "run_resources": str(out / "resources.json"),
                                         "analysis_resources": str(analysis_out / "resources.json"),
                                         "summary": str(analysis_out / "summary.json")}); save()
            print(f"下見：走行{progress['runs_completed']}/160・解析{progress['analyses_completed']}/160完了。{tag}", flush=True)
        progress["status"] = "complete"; progress["current"] = None; save()
    except Exception as error:
        progress["status"] = "stopped"
        progress["stopped_reason"] = repr(error)
        progress["traceback"] = traceback.format_exc(); save()
        raise
    finally:
        # 終了・停止時の報告は同じスレッドの承認済みの報告へ追記する。
        with (dest / "completion_report.log").open("a") as log:
            subprocess.run(["/usr/bin/python3", "/Users/tatsu-admin/jobs/jobs.py", "run", "--wait",
                            "--owner", "Codex-shop-deco-completion-report", "--mem", "0.2", "--disk-path", str(dest), "--",
                            PYTHON, "-B", "control/shop_deco_2026-10-04/report_preview.py"], cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == "__main__":
    main()
