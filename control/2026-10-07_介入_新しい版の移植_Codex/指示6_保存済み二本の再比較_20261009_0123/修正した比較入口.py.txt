"""指示5の世界2・種1・全部入り200試行を、記録の有無だけで照合する。"""
import argparse
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parents[1]
TOOLS = SOURCE / "tools"
PORT = SOURCE.parent
sys.path.insert(0, str(PORT))
from admission_guard import census

# 実行前に固定する。時間以外の値・空白・順・表記は一切変えない。
TIME_FIELDS = ("timestamp", "seconds", "wrapper_seconds", "engine_seconds",
               "rematch_fraction_of_stage2_seconds")
TIME_PATTERN = re.compile(rb'("(?:' + b'|'.join(k.encode() for k in TIME_FIELDS) +
                          rb')"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|null)')
MODEL_DIRS = ("ledgers", "side", "attention", "stage2", "evictions")


def now():
    return datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def model_files(root):
    return {p.relative_to(root).as_posix(): p for directory in MODEL_DIRS
            for p in (root / directory).rglob("*") if p.is_file()}


def comparable(path, ledger=False):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        for index, line in enumerate(stream):
            if ledger and index == 0:
                if json.loads(line).get("record_type") != "run_header":
                    raise ValueError("台帳の見出しが無い")
                continue
            if ".json" in path.name:
                line = TIME_PATTERN.sub(lambda match: match[1] + b"null", line)
            yield line


def compare_files(left, right, ledger=False):
    from itertools import zip_longest
    a_hash, b_hash = hashlib.sha256(), hashlib.sha256()
    for number, (a, b) in enumerate(zip_longest(comparable(left, ledger), comparable(right, ledger)), 1):
        if a is not None: a_hash.update(a)
        if b is not None: b_hash.update(b)
        if a != b:
            first = next((i for i, pair in enumerate(zip(a or b"", b or b"")) if pair[0] != pair[1]),
                         min(len(a or b""), len(b or b"")))
            return dict(match=False, first_line=number, first_byte_in_line=first,
                        left_sample=(a or b"")[max(0, first-35):first+75].hex(),
                        right_sample=(b or b"")[max(0, first-35):first+75].hex())
    return dict(match=True, compared_sha256=a_hash.hexdigest(), right_sha256=b_hash.hexdigest())


def command(output, recording=False, records=None):
    args = [sys.executable, str(TOOLS / ("intervention46_record_run.py" if recording else "v3_run.py")),
            str(SOURCE / "config/sweep_shop_hide1_s1_2026-10-01.json"), str(output),
            "--nohash", "--vt", "0.3842", "--extend-rule", "none", "--charge1", "d32",
            "--fast", "--no-public-history", "--dump-slot-history", "--fix2-full", "--fix-order2",
            "--proj-first", "--fill-norestate", "--no-charge2", "--own-evidence", "--v39",
            "--v39-budget", "inf", "--v39-decay", "actr", "--v310-be", "--hist-role", "--score-role",
            "--u-struct", "--relearn-init", "--tie-struct", "--amb-local", "--nsim", "0.7",
            "--ident-rho", "0.5", "--ident-argmax", "--ident-commons",
            "--cells", "f0.5000_th2.1000_first_order", "--dump-answers", "--dump-routing", "--answer-gap",
            "--strict-pc", "--e-price", "0.01873710622997919", "--v39-price", "0.01873710622997919",
            "--shop-world", "2", "--workers", "1", "--seeds", "1", "--trial-count", "200",
            "--no-compare", "--horizon", "1740", "--score-arg-order", "--sme2017", "--shop-scatter",
            "--sme-call-seed", "--sme-tie-uniform", "--sme-intern-cache", "--sme-evict-trial-cache",
            "--sme-evict-tombstone", "--score-logp", "--match-cstar", "--match-cstar-e", "--match-eps", "0",
            "--h-dirichlet", "1", "--birth-score", "seq", "--logp-eps", "0.01",
            "--attn-sme", "global", "--attn-position", "k2", "--attn-eta", "0.1", "--attn-allin",
            "--stage2", "on", "--stage2-loss", "top1", "--stage2-init", "virtual", "--stage2-scope", "all",
            "--stage2-reuse", "off", "--stage2-birth-hu", "on"]
    if recording: args.extend(["--intervention-record-dir", str(records)])
    return args


def run_one(root, label, recording):
    output, records = root / label / "output", root / "research_records"
    cmd = command(output, recording, records)
    save(root / (label + "_command.json"), cmd)
    waiting = time.monotonic()
    while True:
        rows, active, paused = census()
        if len(active) < 8:
            break
        save(root / (label + "_cpu_wait.json"), dict(at_jst=now(), active=len(active), paused=len(paused)))
        time.sleep(15)
    save(root / (label + "_before_start.json"), dict(at_jst=now(), active=len(active), paused=len(paused),
         models=[dict(pid=p, **rows[p]) for p in sorted(active | paused)],
         cpu_wait_seconds=time.monotonic()-waiting, child_command=cmd))
    env = dict(os.environ, PYTHONHASHSEED="0")
    env.pop("INTERVENTION46_RESEARCH_RECORD_DIR", None)
    started = time.monotonic()
    with (root / (label + ".log")).open("xb") as log:
        process = subprocess.run(cmd, cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT)
    timing = dict(label=label, exit_code=process.returncode, elapsed_seconds=time.monotonic()-started)
    save(root / (label + "_completed.json"), timing)
    if process.returncode:
        raise RuntimeError("200試行の模型が自然終了時に例外を返した：" + label)
    return timing


def validate_records(root):
    pre, context, births = [], [], []
    for path in (root / "research_records").rglob("*.jsonl.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["kind"] == "pre":
                    assert tuple(row["observations"]) == (
                        "entities", "arguments", "parents", "shapes", "table", "names", "events", "last_trial")
                    assert row["observations"]["last_trial"] == row["trial"]-1
                    assert row["questions"]["door"] + row["questions"]["other"] == row["trial"]+1
                    pre.append(row["trial"])
                elif row["kind"] == "prediction_context":
                    context.append(row["trial"])
                elif row["kind"] == "birth_seat":
                    assert row["first_experienced_trial"] <= row["second_experienced_trial"] == row["trial"]
                    assert row["base_age"] == row["trial"]-row["first_experienced_trial"]
                    births.append((row["trial"], row["definition_name"], row["slot_index"]))
                else:
                    raise ValueError("知らない記録の種類")
    assert pre == context == list(range(200)), "予測前の全試行が保存されていない"
    assert births and len(set(births)) == len(births), "誕生の席の保存が無い又は重複"
    return dict(pre_records=len(pre), prediction_context_records=len(context), birth_seat_records=len(births))


def compare_outputs(root, status):
    left, right = (root / name / "output" for name in ("without_records", "with_records"))
    a, b = model_files(left), model_files(right)
    assert a and set(a) == set(b), "模型の出力ファイルの集合が違う"
    status["completion_markers"] = []
    for name in a:
        # 指示6：完了札は両側の存在だけを確認し、模型の記録は従来どおり全て比べる。
        if name.endswith(".done"):
            status["completion_markers"].append(dict(file=name, present_both=True))
            continue
        result = dict(file=name, **compare_files(a[name], b[name], name.startswith("ledgers/")))
        status["comparisons"].append(result)
        if not result["match"]:
            status["status"] = "stopped_mismatch"
            raise RuntimeError("記録の有無で全バイトが不一致。修正せず停止：" + name)
    assert (left / "flag.json").read_bytes() == (right / "flag.json").read_bytes()


def fingerprints(root):
    result = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def compare_existing(root, evidence):
    """自然終了した本を読み取るだけ。旧関門と模型のファイルへは書かない。"""
    assert root.is_dir() and not evidence.is_relative_to(root), "証拠は旧関門の外へ保存する"
    previous = json.loads((root / "status.json").read_text())
    assert (previous["seed"], previous["world"], previous["trials"]) == (1, 2, 200)
    completed = [json.loads((root / (label + "_completed.json")).read_text())
                 for label in ("without_records", "with_records")]
    assert all(item["exit_code"] == 0 for item in completed), "模型の自然終了が未確認"
    evidence.mkdir(parents=True, exist_ok=False)
    status = dict(status="running", at_jst=now(), trials=200, seed=1, world=2,
                  authorizing_instruction=6, model_rerun=False, input_root=str(root),
                  time_fields_excluded=list(TIME_FIELDS), ledger_header_only_excluded=True,
                  comparisons=[], completed=completed)
    before = fingerprints(root)
    save(evidence / "input_before.json", before)
    started = time.monotonic()
    try:
        compare_outputs(root, status)
        status["records"] = validate_records(root)
        status["status"] = "passed"
    except BaseException as error:
        if status["status"] == "running":
            status["status"] = "stopped"
        status["error"] = repr(error)
        raise
    finally:
        status["comparison_and_record_validation_seconds"] = time.monotonic() - started
        after = fingerprints(root)
        save(evidence / "input_after.json", after)
        status["input_files_count"] = len(before)
        status["input_files_unchanged"] = before == after
        if before != after:
            status["status"] = "stopped"
            status["preservation_error"] = "読み取りの前後で入力資料の全バイトが変わった"
        status["updated_at_jst"] = now()
        save(evidence / "status.json", status)
        assert before == after, "読み取りの前後で入力資料が変わった"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--compare-existing", action="store_true")
    parser.add_argument("--evidence-dir")
    args = parser.parse_args()
    root = Path(args.output).resolve()
    if args.compare_existing:
        assert args.evidence_dir, "再比較の証拠の保存先を指定する"
        compare_existing(root, Path(args.evidence_dir).resolve())
        return
    assert args.evidence_dir is None, "別保存先は再比較専用"
    root.mkdir(parents=True, exist_ok=False)
    status = dict(status="running", at_jst=now(), trials=200, seed=1, world=2,
                  time_fields_excluded=list(TIME_FIELDS), ledger_header_only_excluded=True,
                  comparisons=[], completed=[])
    try:
        for label, recording in (("without_records", False), ("with_records", True)):
            save(root / "status.json", status)
            status["completed"].append(run_one(root, label, recording))
        compare_outputs(root, status)
        status["records"] = validate_records(root)
        status["status"] = "passed"
    except BaseException as error:
        if status["status"] == "running": status["status"] = "stopped"
        status["error"] = repr(error)
        raise
    finally:
        status["updated_at_jst"] = now()
        save(root / "status.json", status)


if __name__ == "__main__":
    main()
