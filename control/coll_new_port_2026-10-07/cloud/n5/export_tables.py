"""クラウドに本体を残し、運用表とsha256だけを新しい報告先へ保存する。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def export(evidence, destination):
    runtime = json.loads((evidence / "runtime.json").read_text())
    resource = json.loads((evidence / "resource.json").read_text())
    output = Path(runtime["output"])
    summary = json.loads((output / "comm/run001.summary.json").read_text())
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for kind, root in (("output", output), ("evidence", evidence)):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rows.append([kind, str(path.relative_to(root)), path.stat().st_size, digest(path)])
    with (destination / "sha256.tsv").open("x") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["location", "relative_path", "bytes", "sha256"])
        writer.writerows(rows)
    with (destination / "runs.tsv").open("x") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["name", "commit", "parallel", "group_seed", "trials", "actors",
                         "elapsed_seconds", "rss_sum_peak_bytes", "output_bytes", "exitcode",
                         "warnings", "spec_sha256"])
        writer.writerow([runtime["name"], runtime["commit"], runtime["parallel"], runtime["seeds"][0],
                         summary["trials"], len(summary["agents"]), resource["elapsed_seconds"],
                         resource["rss_sum_peak_bytes"], sum(r[2] for r in rows if r[0] == "output"),
                         resource["exitcode"], ";".join(resource["warnings"]), runtime["plan_spec_sha256"]])
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(export(args.evidence, args.destination))
