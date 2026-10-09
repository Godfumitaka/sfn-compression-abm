"""保存された二本の完了、200試行と旗、旧資料の不変を点検する。成績は判定しない。"""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import time

root = Path(__file__).resolve().parent
port = root.parent
started = time.perf_counter()
result = {"status": "running", "runs": {}, "formal_3b_material": False}
destination = root / "completed_D_verification_01.json"
assert not destination.exists(), "完了点検を重複実行しない"
try:
    assert json.loads((root / "off_comparison_01.json").read_text())["status"] == "passed"
    for label in ("D_q", "D_attention"):
        folder = root / label
        status = json.loads((folder / "status.json").read_text())
        assert status["status"] == "completed" and status["exit_code"] == 0
        before = json.loads((folder / "protected_before.json").read_text())
        after = json.loads((folder / "protected_after.json").read_text())
        assert status["protected_unchanged"] and before == after
        output = folder / "output"
        flag = json.loads((output / "flag.json").read_text())
        assert flag["use_forget"] == 0.4 and flag["use_forget_q"] is True
        assert bool(flag.get("use_forget_attn")) == (label == "D_attention")
        assert flag["shop_world"] == 2 and flag["workers"] == 1
        for name in ("stage2", "stage2_birth_hu", "stage2_speed", "stage2_cache_prune", "stage2_reuse"):
            assert not flag.get(name), name
        ledgers = list((output / "ledgers").rglob("*.jsonl.gz"))
        assert len(ledgers) == 1 and ledgers[0].with_name("seed001.done").exists()
        with gzip.open(ledgers[0], "rt") as stream:
            rows = [json.loads(line) for line in stream]
        assert len(rows) - 1 == 200
        audits = list((output / "retention").rglob("seed001.jsonl"))
        assert len(audits) == 1
        records = [json.loads(line) for line in audits[0].read_text().splitlines()]
        assert len(records) == 200 and all(row["tau"] == 0.4 for row in records)
        trials = [row["trial"] for row in records]
        assert all(right == left + 1 for left, right in zip(trials, trials[1:]))
        result["runs"][label] = {
            "ledger_records": 200, "retention_records": 200,
            "trial_first": trials[0], "trial_last": trials[-1],
            "completion_marker_present": True, "protected_unchanged": True,
            "flags_verified": True,
            "output_sha256": {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(output.rglob("*")) if path.is_file()},
            "admission_wait_seconds": status["admission_wait_seconds"],
            "cpu_wait_seconds": status["cpu_wait_seconds"],
            "model_seconds": status["seconds"],
            "peak_children_rss_bytes": status["peak_children_rss_bytes"],
            "ended_at_jst": status["ended_at_jst"],
        }
    state = json.loads((port / "instruction9_status.json").read_text())
    for name, expected in state["source_sha256"].items():
        assert hashlib.sha256((port / "source_c792_D_instruction9" / name).read_bytes()).hexdigest() == expected
    result.update(status="passed", source_unchanged=True)
except BaseException as error:
    result.update(status="stopped", error=repr(error))
    raise
finally:
    result["seconds"] = time.perf_counter() - started
    result["at_jst"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "runs": list(result["runs"]), "seconds": result["seconds"]}, ensure_ascii=False))
