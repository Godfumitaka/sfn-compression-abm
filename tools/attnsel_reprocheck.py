"""二つの保存済み台帳を全欄比較する。模型・乱数・比較条件を変更しない。

本体はrun_headerを除く元のバイト列。JSONの欄はキー順だけを正準化し、
配列順序・数値表現の型・全欄を保つ。除外欄や許容誤差は設けない。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
from itertools import zip_longest
import json
from pathlib import Path


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def leaves(a, b, path, limit=8):
    """異なる欄の最初の葉を少数控える。配列の位置はそのまま比較する。"""
    if packed(a) == packed(b):
        return []
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append({"path": path + "." + k, "first_present": k in a, "second_present": k in b})
            else:
                out.extend(leaves(a[k], b[k], path + "." + k, limit - len(out)))
            if len(out) >= limit:
                break
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path + ".length", "first": len(a), "second": len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(leaves(x, y, path + f"[{i}]", limit - len(out)))
            if len(out) >= limit:
                break
    else:
        def short(v):
            text = packed(v).decode()
            return text if len(text) <= 200 else text[:197] + "..."
        out.append({"path": path, "first": short(a), "second": short(b)})
    return out[:limit]


def compare(first, second, output):
    output.mkdir(parents=True, exist_ok=False)
    inventory = {name: defaultdict(lambda: {"present": 0, "null": 0, "types": Counter()})
                 for name in ("header", "body")}
    hashes = [hashlib.sha256(), hashlib.sha256()]
    counts = [0, 0]
    changed = Counter()
    samples = {}
    raw_differing = 0
    value_differing = 0
    identity_differing = 0
    with gzip.open(first, "rb") as f, gzip.open(second, "rb") as g, \
         gzip.open(output / "row_comparison.jsonl.gz", "wt", encoding="utf-8") as log:
        ah, bh = f.readline(), g.readline()
        header = [json.loads(ah), json.loads(bh)]
        header_changed = [k for k in sorted(set(header[0]) | set(header[1]))
                          if k not in header[0] or k not in header[1] or packed(header[0][k]) != packed(header[1][k])]
        for h in header:
            for k, v in h.items():
                inv = inventory["header"][k]
                inv["present"] += 1
                inv["null"] += v is None
                inv["types"][type(v).__name__] += 1
        for line_no, (a, b) in enumerate(zip_longest(f, g), 2):
            row = [json.loads(x) if x is not None else None for x in (a, b)]
            for i, (raw, data) in enumerate(zip((a, b), row)):
                if raw is not None:
                    hashes[i].update(raw)
                    counts[i] += 1
                    for k, v in data.items():
                        inv = inventory["body"][k]
                        inv["present"] += 1
                        inv["null"] += v is None
                        inv["types"][type(v).__name__] += 1
            keys = sorted(set(row[0] or {}) | set(row[1] or {}))
            fields = [k for k in keys if row[0] is None or row[1] is None or k not in row[0] or k not in row[1]
                      or packed(row[0][k]) != packed(row[1][k])]
            raw_differing += a != b
            value_differing += bool(fields)
            same_identity = all(row[0] is not None and row[1] is not None and row[0].get(k) == row[1].get(k)
                                for k in ("record_type", "agent_id", "prediction_order"))
            identity_differing += not same_identity
            changed.update(fields)
            for k in fields:
                if k not in samples:
                    samples[k] = {"file_line": line_no, "prediction_order": (row[0] or {}).get("prediction_order"),
                                  "examples": leaves((row[0] or {}).get(k), (row[1] or {}).get(k), k)}
            rec = {"file_line": line_no, "prediction_order": (row[0] or {}).get("prediction_order"),
                   "row_identity_match": same_identity, "raw_bytes_match": a == b, "changed_fields": fields,
                   "first_line_sha256": digest(a) if a else None, "second_line_sha256": digest(b) if b else None}
            log.write(json.dumps(rec, ensure_ascii=False) + "\n")
    result = {"first": str(first), "second": str(second), "comparison_excluded_fields": [],
              "header_raw_bytes_match": ah == bh, "header_changed_fields": header_changed,
              "body_sha256_first": hashes[0].hexdigest(), "body_sha256_second": hashes[1].hexdigest(),
              "body_row_counts": counts, "raw_differing_body_rows": raw_differing,
              "value_differing_body_rows": value_differing, "row_identity_mismatch_count": identity_differing,
              "field_difference_row_counts": dict(sorted(changed.items())), "first_difference_examples": samples,
              "inventory": {kind: {k: {**v, "types": dict(v["types"])} for k, v in sorted(items.items())}
                            for kind, items in inventory.items()}}
    (output / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    with (output / "field_inventory.tsv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(("record_type", "field", "present_rows_both_runs", "null_rows_both_runs", "types", "different_rows"))
        for kind, fields in result["inventory"].items():
            for k, v in fields.items():
                writer.writerow((kind, k, v["present"], v["null"], json.dumps(v["types"], sort_keys=True),
                                 int(k in header_changed) if kind == "header" else changed[k]))
    print(json.dumps({k: v for k, v in result.items() if k not in ("inventory", "first_difference_examples")}, ensure_ascii=False))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("first", type=Path)
    ap.add_argument("second", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    compare(args.first, args.second, args.output)


if __name__ == "__main__":
    main()
