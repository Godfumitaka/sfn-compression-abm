"""Read published seed-1/2 records without importing the model or reference.

The stage2 arithmetic checks are record consistency checks, not independent
matching or a production gate. Large raw pre-state inputs remain necessary.
"""
import argparse
import collections
from datetime import datetime
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import resource
import subprocess


def git(root, revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root)


def inventory(root, revision, output):
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", revision, "ataru-0608/cloud_runs"],
        cwd=root, text=True).splitlines()
    pattern = re.compile(r"ataru-0608/cloud_runs/(wave1_([1-7]a)_w([12])_s([12])(?:_e9)?)/(.+)")
    groups = collections.defaultdict(list)
    for path in paths:
        match = pattern.fullmatch(path)
        if match:
            groups[match[1]].append((path, match[5]))
    deliveries = []
    for name, entries in sorted(groups.items()):
        prefix = f"ataru-0608/cloud_runs/{name}/"
        names = {short for _, short in entries}
        manifest_path = prefix + "files_sha256.tsv"
        manifest = git(root, revision, manifest_path)
        raw_files = []
        for line in manifest.decode().splitlines():
            fields = line.split("\t")
            if len(fields) != 3 or not fields[1].isdigit():
                continue
            raw_path, size, sha = fields
            if any(marker in raw_path for marker in (".sme.jsonl", ".sme.states.jsonl", "attention/", ".initial.jsonl")):
                raw_files.append({"raw_path": raw_path, "size": int(size), "sha256": sha,
                                  "in_git_delivery": raw_path in names,
                                  "s3_uri": f"s3://sfn-abm-results-astra1008/cloud_runs/{name}/output/{raw_path}"})
        match = re.fullmatch(r"wave1_([1-7]a)_w([12])_s([12])(?:_e9)?", name)
        code_status = ("superseded_diagnostic" if match[1] in {"1a", "3a", "4a", "6a"}
                       and not name.endswith("_e9") else "published_queue_version")
        deliveries.append({"run": name, "row": match[1], "world": int(match[2]),
                           "world_seed": int(match[3]), "version_scope": code_status,
                           "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                           "git_files": sorted(names), "raw_inputs": raw_files})

    # Two active-arm pilots: a current C*-off run and a current no-forget run.
    pilots = []
    for name, seed in (("wave1_5a_w1_s2", 2), ("wave1_7a_w1_s1", 1)):
        path = f"ataru-0608/cloud_runs/{name}/seed{seed:03d}.stage2.jsonl.gz"
        blob = git(root, revision, path)
        sha = hashlib.sha256(blob).hexdigest()
        sidecar = git(root, revision, path + ".sha256").decode().split()[0]
        if sha != sidecar:
            raise ValueError(f"published gzip fingerprint mismatch: {path}")
        kinds = collections.Counter()
        top_keys = set()
        trial_ids = []
        checks = collections.Counter()
        errors = []
        maximum_delta_error = 0.0

        def check(condition, label, trial, detail=None):
            checks[label] += 1
            if not condition and len(errors) < 20:
                errors.append({"trial": trial, "check": label, "detail": detail})
            if not condition:
                checks[label + "_failed"] += 1

        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
            for line in stream:
                record = json.loads(line)
                trial = record["trial"]
                trial_ids.append(trial)
                top_keys.update(record)
                kinds[record.get("reason")] += 1
                rows = record.get("rows", [])
                if not record.get("f_fired"):
                    check(not rows and not record.get("applied"), "undisclosed_has_no_updates", trial)
                baseline = record.get("baseline_loss", {})
                mass, value = baseline.get("correct_mass"), baseline.get("value")
                if record.get("loss") == "top1" and mass and not baseline.get("escaped"):
                    check(math.isclose(value, -math.log2(mass), rel_tol=1e-10, abs_tol=1e-10),
                          "recorded_baseline_log_cost", trial)
                for row in rows:
                    check(row.get("state") in {"F", "H"}, "intervention_state_F_or_H", trial)
                    before, after, delta = (row[k] for k in ("r_before", "r_after", "delta"))
                    error = abs(delta - (after - before))
                    maximum_delta_error = max(maximum_delta_error, error)
                    check(math.isclose(delta, after-before, rel_tol=1e-10, abs_tol=1e-10),
                          "delta_is_recorded_after_minus_before", trial,
                          {"R": row["R"], "slot": row["slot"], "absolute_difference": error})
        check(len(trial_ids) == len(set(trial_ids)), "unique_trials", None)
        check(sorted(trial_ids) == list(range(1740)), "complete_1740_trial_ids", None)
        pilots.append({"run": name, "world_seed": seed, "input": path, "sha256": sha,
                       "sidecar_verified": True, "trial_count": len(trial_ids),
                       "top_level_fields": sorted(top_keys), "reason_counts": dict(kinds),
                       "checks": dict(checks), "error_examples": errors,
                       "maximum_delta_subtraction_error": maximum_delta_error,
                       "independent_reference_trials": 0,
                       "production_name_id_permutations": 0})

    result = {"time_jst": datetime.now().astimezone().isoformat(), "source_commit": revision,
              "scope": "published seed-1/2 availability and stage2 record consistency only",
              "configuration_set_complete": False, "required_configurations": 9,
              "deliveries": deliveries, "stage2_pilots": pilots,
              "peak_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "step2_complete": False, "step3_complete": False,
              "missing_for_independent_replay": ["SME mapping/score record", "pretrial memory/input/config/RNG",
                                                "active attention record", "birth initial-value record"],
              "s3_read_status": "AWS session expired; aws login awaiting human confirmation"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.root, args.revision, args.output)
    print(json.dumps({"deliveries": len(result["deliveries"]), "pilots": [
        {"run": p["run"], "trials": p["trial_count"],
         "failed_checks": sum(v for k, v in p["checks"].items() if k.endswith("_failed"))}
        for p in result["stage2_pilots"]], "peak_rss_bytes_macos": result["peak_rss_bytes_macos"],
        "independent_reference_trials": 0}, ensure_ascii=False))
