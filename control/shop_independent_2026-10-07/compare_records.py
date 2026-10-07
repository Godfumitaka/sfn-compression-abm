"""Compare independently replayed values in a format-neutral audit table.

The creator's record adapter is intentionally separate from reference.py.
Inputs here are explicit #0 seed-1/2 records, not model result directories.
This file does not claim that a reference value supplied by somebody else is
independently calculated: provenance/hashes must be retained by the adapter.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random


def read(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["world_seed"] not in (1, 2):
                raise ValueError("this comparison is restricted to queue #0, seeds 1 and 2")
            rows.append(row)
    keys = [(r["configuration"], r["trial_key"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate configuration/trial key")
    return rows


def flatten(value, key=""):
    if isinstance(value, dict):
        return {k: v for sub, item in value.items() for k, v in flatten(item, f"{key}.{sub}" if key else str(sub)).items()}
    if isinstance(value, list):
        return {k: v for i, item in enumerate(value) for k, v in flatten(item, f"{key}[{i}]").items()}
    return {key: value}


def compare(actual_path, reference_path, output_dir, *, sample_size=50, expected_configurations=9):
    if sample_size < 50:
        raise ValueError("at least 50 trials per configuration")
    actual, reference = read(actual_path), read(reference_path)
    refs = {(r["configuration"], r["trial_key"]): r for r in reference}
    configurations = sorted({r["configuration"] for r in actual})
    if len(configurations) != expected_configurations:
        raise ValueError("queue #0 configuration set is incomplete")
    rng = random.Random(20261007)  # reviewer sampling stream, not a world seed
    differences, summary, selected = [], [], {}
    for config in configurations:
        available = [r for r in actual if r["configuration"] == config]
        if len(available) < sample_size:
            raise ValueError(f"{config}: only {len(available)} trials available")
        chosen = rng.sample(available, sample_size)
        selected[config] = [r["trial_key"] for r in chosen]
        counts = {}
        for a in chosen:
            key = config, a["trial_key"]
            if key not in refs:
                raise ValueError(f"missing independently replayed trial: {key}")
            left, right = flatten(a["values"]), flatten(refs[key]["values"])
            for field in sorted(set(left) | set(right)):
                lv, rv = left.get(field), right.get(field)
                numeric = (type(lv) in (float, int) and type(rv) in (float, int))
                absolute = abs(lv-rv) if numeric else None
                equal = (math.isclose(lv, rv, rel_tol=1e-10, abs_tol=1e-10) if numeric else
                         field in left and field in right and lv == rv)
                stats = counts.setdefault(field, {"compared": 0, "different": 0, "maximum_absolute_difference": 0.0})
                stats["compared"] += 1
                stats["different"] += int(not equal)
                if absolute is not None:
                    stats["maximum_absolute_difference"] = max(stats["maximum_absolute_difference"], absolute)
                if not equal:
                    differences.append({"configuration": config, "trial_key": a["trial_key"], "field": field,
                                        "actual": lv, "reference": rv, "absolute_difference": absolute})
        summary.extend({"configuration": config, "field": field, **stats} for field, stats in counts.items())
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with open(output/"differences.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("configuration", "trial_key", "field", "actual", "reference", "absolute_difference"))
        writer.writeheader()
        writer.writerows(differences)
    with open(output/"summary.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("configuration", "field", "compared", "different", "maximum_absolute_difference"))
        writer.writeheader()
        writer.writerows(summary)
    manifest = {"scope": "queue #0 numerical/reference comparison", "selected_trials": selected,
                "sampling_stream": "reviewer only, Random(20261007); independent of world RNG",
                "sample_size_per_configuration": sample_size, "configurations": len(configurations),
                "absolute_tolerance": 1e-10, "relative_tolerance": 1e-10,
                "different_values": len(differences), "input_sha256":
                {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (actual_path, reference_path)}}
    (output/"sampling.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("actual")
    parser.add_argument("reference")
    parser.add_argument("output")
    parser.add_argument("--sample-size", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(compare(args.actual, args.reference, args.output), ensure_ascii=False))
