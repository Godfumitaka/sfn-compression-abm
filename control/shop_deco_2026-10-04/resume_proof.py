"""停止した解析だけの修復と、完了済み全ファイルの全バイト保存を確認する。"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from run_registered import AREA, ROOT, CELL

TAG = "skeleton_N3_A_w1_s001"
FIRST = "plus8_N3_D_w2_s001"
HERE = ROOT / "control/shop_deco_2026-10-04/stage4_stop_2026-10-05"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_files():
    preview = AREA / "preview"
    folders = [preview / "runs" / FIRST, preview / "runs" / TAG,
               preview / "analysis" / FIRST]
    return {str(p.relative_to(preview)): {"bytes": p.stat().st_size, "sha256": digest(p)}
            for folder in folders for p in sorted(folder.rglob("*")) if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "check"))
    args = parser.parse_args()
    HERE.mkdir(exist_ok=True)
    preview = AREA / "preview"
    fingerprints = json.loads((preview / "model_fingerprints.json").read_text())
    assert all(digest(ROOT / name) == sha for name, sha in fingerprints.items())
    before = HERE / "protected_before.json"
    if args.mode == "capture":
        assert not before.exists(), "保存済みの修復前の証拠を上書きしない"
        progress = json.loads((preview / "progress.json").read_text())
        assert progress["status"] == "stopped" and progress["current"]["tag"] == TAG
        assert progress["runs_completed"] == 2 and progress["analyses_completed"] == 1
        for name in ("run.log", "resources.json", "validation.json", "command.json"):
            shutil.copy2(preview / "analysis" / TAG / name, HERE / ("failed_" + name))
        shutil.copy2(preview / "progress.json", HERE / "stopped_progress.json")
        before.write_text(json.dumps(protected_files(), ensure_ascii=False, indent=2) + "\n")
        print("完了済みの2走行と1解析を全バイト比較用に保存した", flush=True)
        return
    protected = json.loads(before.read_text())
    after = protected_files()
    assert after == protected, "完了済みファイルの集合・全バイトに変更がある"
    out = preview / "analysis" / TAG
    resources = json.loads((out / "resources.json").read_text())
    validation = json.loads((out / "validation.json").read_text())
    summary = json.loads((out / "summary.json").read_text())
    assert resources["exit_code"] == 0 and resources["peak_descendants_rss_bytes"] <= 0.8e9
    assert validation["C_end_mismatch"] == validation["args_unrestored"] == 0
    assert validation["memory_trials_read"] == validation["expected_trials"] == 1740
    assert all(validation["check"][k] == 0 for k in ("予測が本物と違う", "一位が本物の選びと違う", "一位でやり直した答えが本物と違う"))
    assert summary["trial_count"] == 1740 and not summary["pilot_all_spoken"]
    done_checks = []
    for tag in (FIRST, TAG):
        run = preview / "runs" / tag
        done = run / "ledgers/cells" / CELL / "seed001.done"
        marker = json.loads(done.read_text())
        manifest = [json.loads(s) for s in (run / "manifest.jsonl").read_text().splitlines()]
        assert len(manifest) == 1 and all(manifest[0][k] == v for k, v in marker.items())
        assert marker["ledger_bytes"] == (done.with_suffix(".jsonl.gz")).stat().st_size
        done_checks.append({"tag": tag, "done_sha256": digest(done), "done_raw_bytes_equal": True,
                            "all_done_fields_equal_to_manifest": True})
    result = {"passed": True, "repaired_tag": TAG, "fix_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protected_files": len(protected), "protected_file_sets_and_raw_bytes_equal": True,
        "model_file_fingerprints_unchanged": len(fingerprints), "done_checks": done_checks,
        "resources": resources, "validation": validation,
        "summary_sha256": digest(out / "summary.json")}
    (HERE / "resume_proof.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    shutil.copy2(out / "validation.json", HERE / "repaired_validation.json")
    shutil.copy2(out / "resources.json", HERE / "repaired_resources.json")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
