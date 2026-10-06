"""一本の解析を同じ受付の内側で行い、元の全出力のバイトが変わらないことを確かめる。"""
from pathlib import Path
import argparse
import json
import subprocess
import traceback
from common import ROOT, PYTHON, CELL, digest
from summarise_run import summarise


def fingerprints(root):
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path);parser.add_argument("seed", type=int)
    parser.add_argument("dest", type=Path)
    a = parser.parse_args()
    assert 1 <= a.seed <= 5
    a.dest.mkdir(parents=True, exist_ok=True)
    validation = {"passed": False, "original": str(a.original)}
    try:
        before = fingerprints(a.original)
        validation["original_before_sha256"] = before
        command = json.loads((a.original / "command.json").read_text())["command"]
        assert command[0] == PYTHON and command[1] == "-B"
        # 既存再生道具のCLIは[python,script,config,out]。模型への引数を変更せず形を合わせる。
        command = [command[0], *command[2:]]
        (a.dest / "replay_command.json").write_text(json.dumps(command, ensure_ascii=False, indent=2) + "\n")
        states = a.original / "side" / CELL / f"seed{a.seed:03d}.sme.states.jsonl.gz"
        args = [PYTHON, "-B", str(Path(__file__).with_name("replay_observe.py")), "--check-legacy",
                str(a.dest / "replay_command.json"), str(a.dest / "replay"), str(states)]
        subprocess.run(args, cwd=ROOT, check=True)
        summary = summarise(a.original, a.dest / "replay", a.dest / "summary.json", a.seed)
        after = fingerprints(a.original)
        validation.update(passed=before == after, original_after_sha256=after,
                          original_all_files_bytes_equal=before == after, **summary["validation"])
        assert validation["passed"]
    except BaseException:
        validation["error"] = traceback.format_exc()
        raise
    finally:
        (a.dest / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":main()
