"""指示13A：自然終了、200件、試験の全D控え・原字節不変を点検する。"""
from pathlib import Path
import datetime, gzip, hashlib, json, shutil, subprocess, sys, time

here = Path(__file__).resolve().parent
port = here.parent
label = sys.argv[1]
assert label in ('candidate_on_D_04_200_01', 'candidate_on_D_015_200_01')
assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat('2026-10-13T09:00:00+09:00')
sys.path.insert(0, str(here))
from resource_census_02 import census

destination = here / (label + '_verification_02.json')
assert not destination.exists(), '完了点検を重複実行しない'
rows, active, paused = census()
before = dict(at_jst=datetime.datetime.now().astimezone().isoformat(), active=len(active),
    paused=len(paused), processes=[dict(pid=pid, **rows[pid]) for pid in sorted(active | paused)],
    free_disk_bytes=shutil.disk_usage(here/label/'output').free)
(here / (label + '_verification_before_start_02.json')).write_text(json.dumps(before, ensure_ascii=False, indent=2)+'\n')
assert len(active) < 8 and before['free_disk_bytes'] >= 20*2**30
started = time.perf_counter()
result = dict(status="running", runs={}, formal_3b_material=False, production_started=False)
try:
    off = json.loads((here / 'candidate_off100_comparison_03.json').read_text())
    assert off["passed"] and off["actual_files_excluded"] == off["probe_rows_excluded"] == 0
    assert json.loads((here / 'structure_status_01.json').read_text())['passed']
    assert json.loads((here/'structure_status_01.json').read_text())['protected_unchanged']
    specs = json.loads((here / 'candidate_on200_commands_02.json').read_text())
    for label, tau in [(label, .4 if label=='candidate_on_D_04_200_01' else .15)]:
        folder = here / label
        status = json.loads((folder / "status.json").read_text())
        assert status["state"] == "completed" and status["exit_code"] == 0 and status["completed_trials"] == 200
        assert status["command"] == specs[label]
        assert status["protected_unchanged"]
        assert (folder / "protected_before.json").read_bytes() == (folder / "protected_after.json").read_bytes()
        output = folder / "output"
        marker = json.loads((output / "measurement/partial_done.json").read_text())
        assert marker["completed_trials"] == 200 and marker["configured_trial_count"] == marker["horizon"] == 5000
        assert marker["source_commit"] == "70df13393e437580cb58d2c6e6f84dd5244aca4e"
        assert marker["full_5000_completed"] is False
        flag = json.loads((output / "flag.json").read_text())
        assert flag["attn_probe_name_receipts"] is True and flag["use_forget"] == tau and flag["use_forget_q"] is flag["use_forget_attn"] is True
        assert flag["verb_world"] is flag["probe_world"] is True and flag["horizon"] == 5000
        argv = status["command"]["argv"]
        assert "--score-logp-e" not in argv
        for name in ["--stage2", "--stage2-birth-hu", "--stage2-reuse"]:
            assert argv[argv.index(name)+1] == "off"
        assert "--stage2-speed" not in argv and "--stage2-cache-prune" not in argv
        for name, value in [("--e-price", "0.01873710622997919"), ("--v39-price", "0.00035129738499384776"),
                            ("--match-eps", "0"), ("--seeds", "1")]:
            assert argv[argv.index(name)+1] == value
        ledgers = list((output / "ledgers").rglob("*.jsonl.gz"))
        assert len(ledgers) == 1 and ledgers[0].with_name("seed001.done").exists()
        with gzip.open(ledgers[0], "rt") as stream:
            ledger = [json.loads(line) for line in stream]
        assert len(ledger)-1 == 200
        assert [row['prediction_order'] for row in ledger[1:]]==list(range(200))
        done=json.loads(ledgers[0].with_name('seed001.done').read_text())
        assert done['ledger_bytes']==ledgers[0].stat().st_size and done['trial_count']==200
        assert done['code_commit']=='4dc6a05d88ba10dbc22fd14ec77ec5c720e1c9a2'
        paths = list((output / "retention").rglob("seed001.jsonl"))
        assert len(paths) == 1
        audit = [json.loads(line) for line in paths[0].read_text().splitlines()]
        assert len(audit) == 200 and [row["trial"] for row in audit] == list(range(200))
        assert all(row["tau"] == tau for row in audit)
        old_side = list((output / "side").rglob("seed001.useforget.jsonl"))
        assert len(old_side) == 1 and len(old_side[0].read_text().splitlines()) == 200
        probes = list((output / "retention").rglob("*.probe_checks.json"))
        evaluations = list((output / "side").rglob("*.evaluation_checks.json"))
        assert len(probes) == len(evaluations) == 1
        pc = json.loads(probes[0].read_text()); ec = json.loads(evaluations[0].read_text())
        assert [row["trial"] for row in pc] == [100, 200]
        assert len(ec) >= 2 and sum(row["call"] == "probeworld._probe" for row in ec) == 2
        assert all(row["unchanged"] and row["before_sha256"] == row["after_sha256"] for row in pc+ec)
        result["runs"][label] = dict(ledger_records=200, retention_records=200, old_D_side_records=200,
            probe_trials=[100, 200], evaluation_checks=len(ec), all_D_state_and_record_bytes_unchanged=True,
            completion_marker_present=True, flags_verified=True, protected_unchanged=True,
            admission_wait_seconds=status["admission_wait_seconds"], cpu_wait_seconds=status["cpu_wait_seconds"],
            model_seconds=status["model_seconds"], peak_children_rss_bytes=status["peak_children_rss_bytes"],
            ended_at_jst=status["ended_at_jst"],
            output_sha256={str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(output.rglob("*")) if p.is_file()})
    source = port / "source_verb_probe_names_instruction22"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() == marker["source_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=source, text=True).strip()
    protected = json.loads((here / 'candidate_protected_01.json').read_text())
    assert all(hashlib.sha256((Path(root)/name).read_bytes()).hexdigest() == sha
               for root, files in protected.items() for name, sha in files.items())
    result.update(status="passed", source_commit=marker["source_commit"], hand_tests=40,
                  off_files=off["file_count"], off_manifest_dictionaries=off["manifest_counts_comparison"]["file_count"],
                  source_unchanged=True)
except BaseException as error:
    result.update(status="stopped", error=repr(error))
    raise
finally:
    result.update(seconds=time.perf_counter()-started, at_jst=datetime.datetime.now().astimezone().isoformat())
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({k:v for k,v in result.items() if k != "runs"}, ensure_ascii=False))
