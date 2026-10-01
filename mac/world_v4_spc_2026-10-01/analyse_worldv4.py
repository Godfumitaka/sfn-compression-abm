"""完了した記録だけを読み、指定の数を集計する。世界・状態・席の検査を併記する。"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
import csv
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import time

from run_worldv4 import ROOT, SOURCE, PYTHON, CELL, ARMS, completed, run_root, event

OUTCOMES = {"的中": "correct", "失敗": "wrong", "保留": "abstain"}
ROLE_PREFIXES = {"(i) 伏せた関係": "held_out", "(ii) 見えている関係": "visible", "(iii) 対応先なし": "none"}
ERROR_KEYS = ("check1_mismatch", "check2_mismatch", "hash_mismatch", "args_unrestored", "score_R_differs", "answer_R_differs")

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {int(r["trial"]): r for r in csv.DictReader(f)}

def analyse_one(arm, seed):
    destination = ROOT / "analysis" / arm / f"seed{seed:03d}"
    metrics_path = destination / "metrics.json"
    if metrics_path.exists():
        return json.loads(metrics_path.read_text())
    assert arm.startswith("v4spc_") and completed(arm, seed)
    destination.mkdir(parents=True, exist_ok=True)
    run = run_root(arm, seed)
    role_dir = destination / "roles"
    gate_roles = ROOT / "gate1_roles" / arm
    if (role_dir / "checks.json").exists():
        # 完了した再計算は、下の全検査を通してから再利用する。
        pass
    elif seed == 1 and (gate_roles / "checks.json").exists():
        shutil.copytree(gate_roles, role_dir, dirs_exist_ok=True)
    else:
        with (destination / "role_recompute.log").open("x") as log:
            subprocess.run([PYTHON, "tools/roletarget_recompute.py", str(run), str(role_dir), str(seed)], cwd=SOURCE,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    checks = json.loads((role_dir / "checks.json").read_text())[0]
    assert checks["trials"] == 1740
    assert all(checks[k] == 0 for k in ERROR_KEYS), (arm, seed, checks)
    roles = load_csv(role_dir / f"{CELL}_seed{seed:03d}.roletarget.csv")
    side = run / "side" / CELL
    answers = load_csv(side / f"seed{seed:03d}.answers.csv")
    bits = {}
    with (side / f"seed{seed:03d}.jsonl").open() as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("kind") == "v39":
                assert rec["trial"] not in bits
                bits[rec["trial"]] = rec["bits_after"]
    assert set(bits) == set(range(1740))
    outcomes = collections.Counter()
    reasons = collections.Counter()
    variants = collections.Counter()
    switch = collections.defaultdict(collections.Counter)
    switch_details = collections.defaultdict(collections.Counter)
    role_outcomes = collections.defaultdict(collections.Counter)
    sources = collections.defaultdict(collections.Counter)
    ledger = run / "ledgers/cells" / CELL / f"seed{seed:03d}.jsonl.gz"
    digest = hashlib.sha256()
    count = 0
    trial_path = destination / "trials.csv.gz"
    fields = ["arm", "seed", "trial", "world_variant", "held_out_switch", "outcome", "abstain_reason", "source", "seat_state",
              "slot", "cid", "cid_why", "role_class", "bits_after", "R_used", "pred_predicate", "held_predicate", "disclosed"]
    with gzip.open(ledger, "rb") as f, gzip.open(trial_path, "wt", encoding="utf-8", newline="") as out:
        header = json.loads(next(f))
        assert header["trial_count"] == 1740 and header["run_seed"] == seed
        assert header["f_setting"] == 0.5 and header["arm_holdout_second_order"] is True
        assert header["code_commit"] == json.loads((ROOT / "gate1_passed.json").read_text())["code_commit"]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for line in f:
            digest.update(line)
            row = json.loads(line)
            assert row.get("record_type", "trial") == "trial"
            t = row["prediction_order"]
            assert t == count
            count += 1
            outcome = OUTCOMES[row["outcome_category"]]
            reason = row.get("abstain_reason")
            variant = row["world_variant"]
            assert variant in ("A", "B")
            outcomes[outcome] += 1
            variants[variant] += 1
            if row["held_out_switch"]:
                switch[variant][outcome] += 1
                switch_details[f"{row['held_out_switch']}_{variant}"][outcome] += 1
            rec = dict(arm=arm, seed=seed, trial=t, world_variant=variant, held_out_switch=row["held_out_switch"], outcome=outcome,
                       abstain_reason=reason, bits_after=bits[t], R_used=row["R_used"], held_predicate=row["held_out_content"]["predicate"],
                       disclosed=int(bool(row.get("f_fired"))))
            if outcome == "abstain":
                assert reason and t not in answers
                reasons[reason] += 1
            else:
                assert not reason and t in answers and t in roles
                answer = answers[t]
                role = roles[t]
                assert int(answer["hit"]) == int(outcome == "correct")
                assert role["answered"] == "1" and role["hit"] == answer["hit"]
                assert role["R_used"] == answer["R"] == row["R_used"]
                cls = next((value for prefix, value in ROLE_PREFIXES.items() if role["cls"].startswith(prefix)), None)
                assert cls is not None, (arm, seed, t, role)
                role_outcomes[cls][outcome] += 1
                sources[answer["source"]][outcome] += 1
                rec.update(source=answer["source"], seat_state=answer["seat_state"], slot=answer["slot"], cid=role["cid"],
                           cid_why=role["cid_why"], role_class=cls, pred_predicate=answer["pred"])
            writer.writerow(rec)
    assert count == 1740 and sum(outcomes.values()) == 1740 and sum(reasons.values()) == outcomes["abstain"]
    assert len(answers) == outcomes["correct"] + outcomes["wrong"]
    result = dict(arm=arm, seed=seed, condition=ARMS[arm]["condition"], price=float(ARMS[arm]["price"]),
                  trials=count, outcomes=dict(outcomes), abstain_reasons=dict(reasons), variants=dict(variants),
                  switch={k: dict(v) for k, v in switch.items()}, switch_details={k: dict(v) for k, v in switch_details.items()},
                  role_outcomes={k: dict(v) for k, v in role_outcomes.items()}, sources={k: dict(v) for k, v in sources.items()},
                  memory_bits_sum=sum(bits.values()), memory_bits_mean=sum(bits.values())/1740,
                  world_hash=header["world_hash"], body_sha=digest.hexdigest(), checks=checks,
                  ledger_path=str(ledger), run_path=str(run), code_commit=header["code_commit"])
    metrics_path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    event(kind="analysed", arm=arm, seed=seed, trials=count)
    return result

def watch(workers=1):
    all_jobs = [(arm, seed) for arm in ARMS if arm.startswith("v4spc_") for seed in range(1, 21)]
    jobs = [(a, s) for a, s in all_jobs if not (ROOT / "analysis" / a / f"seed{s:03d}/metrics.json").exists()]
    finished = len(all_jobs) - len(jobs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        active = {}
        while jobs or active:
            ready = [(a, s) for a, s in jobs if completed(a, s)]
            for arm, seed in ready[:workers-len(active)]:
                active[executor.submit(analyse_one, arm, seed)] = (arm, seed)
                jobs.remove((arm, seed))
            if not active:
                time.sleep(15)
                continue
            done, _ = concurrent.futures.wait(active, timeout=5, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                arm, seed = active.pop(future)
                result = future.result()
                finished += 1
                print(f"解析 {finished}/180 {arm} seed{seed:03d} 全{result['trials']}試行、席の不一致0", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--one", nargs=2, metavar=("ARM", "SEED"))
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--workers", type=int, choices=(1, 2, 4), default=1)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(analyse_one(args.one[0], int(args.one[1])), ensure_ascii=False))
    else:
        watch(args.workers)
