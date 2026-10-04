"""圧縮を展開した全バイトを比較し、最初の違いの試行と欄を残す。"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import re
from itertools import zip_longest

SEC = re.compile(rb'("sec_trial"\s*:\s*)-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')


def stream(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as f:
        if "ledgers" in path.parts:
            next(f)
        yield from f


def difference(a, b, path="$", depth=0):
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return path + ".keys", sorted(a), sorted(b)
        for k in a:
            result = difference(a[k], b[k], path + "." + str(k), depth + 1)
            if result is not None:
                return result
    elif isinstance(a, list):
        if len(a) != len(b):
            return path + ".length", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            result = difference(x, y, path + "[" + str(i) + "]", depth + 1)
            if result is not None:
                return result
    elif a != b:
        return path, a, b
    return None


def excerpt(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 400 else text[:400] + "…"


def inspect_line(a, b, name, row, byte_offset, offsets, header):
    trial = None
    field, x, y = "行のバイト", a[:200].decode(errors="replace"), b[:200].decode(errors="replace")
    try:
        aa, bb = json.loads(a), json.loads(b)
        trial = aa.get("trial", bb.get("trial")) if isinstance(aa, dict) else None
        result = difference(aa, bb)
        if result is not None:
            field, x, y = result
        else:
            field = "JSONの字句（読み戻した値と型は同じ）"
    except (ValueError, UnicodeError):
        if name.endswith(".csv") and header is not None:
            aa = dict(zip(header, next(csv.reader([a.decode()]))))
            bb = dict(zip(header, next(csv.reader([b.decode()]))))
            result = difference(aa, bb)
            if result is not None:
                field, x, y = result
            trial = aa.get("trial", bb.get("trial"))
    if trial is None and name.endswith((".sme.jsonl.gz", ".sme.diagnostics.jsonl.gz")):
        key = "diagnostic_log_end" if ".diagnostics." in name else "sme_log_end"
        trial = next((r["trial"] for r in offsets if r.get(key, 0) > byte_offset), None)
    if trial is not None:
        trial = int(trial)
    return {"file": name, "line": row + 1, "trial": trial,
            "human_trial": None if trial is None else trial + 1,
            "field": field, "cpython": excerpt(x), "pypy": excerpt(y)}


def compare(old, new, destination):
    old, new = Path(old), Path(new)
    aa = {p.relative_to(old): p for pattern in ("ledgers/**/*.jsonl.gz", "side/**/*")
          for p in old.glob(pattern) if p.is_file()}
    bb = {p.relative_to(new): p for pattern in ("ledgers/**/*.jsonl.gz", "side/**/*")
          for p in new.glob(pattern) if p.is_file()}
    if aa.keys() != bb.keys():
        result = {"all_equal": False, "first_difference": {"field": "ファイル集合", "trial": None,
                  "old_only": [str(p) for p in aa.keys() - bb.keys()],
                  "new_only": [str(p) for p in bb.keys() - aa.keys()]}}
        Path(destination).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result
    aa[Path("tie_rng.jsonl")] = old.parent / "tie_rng.jsonl"
    bb[Path("tie_rng.jsonl")] = new.parent / "tie_rng.jsonl"
    offsets = [json.loads(x) for x in (new.parent / "performance.jsonl").open()]
    records, diffs = [], []
    for name in sorted(aa):
        ha, hb = hashlib.sha256(), hashlib.sha256()
        equal, first, offset, size_a, size_b, header = True, None, 0, 0, 0, None
        for row, (a, b) in enumerate(zip_longest(stream(aa[name]), stream(bb[name]), fillvalue=b"")):
            if aa[name].name.endswith((".cflearn.jsonl", ".cfvalue.jsonl")):
                a, b = SEC.sub(rb'\g<1>0', a), SEC.sub(rb'\g<1>0', b)
            if row == 0 and str(name).endswith(".csv"):
                header = next(csv.reader([a.decode()]))
            if a != b:
                equal = False
                if first is None:
                    first = inspect_line(a, b, str(name), row, offset, offsets, header)
            ha.update(a); hb.update(b); size_a += len(a); size_b += len(b); offset += len(b)
        records.append({"file": str(name), "equal": equal, "old_expanded_sha256": ha.hexdigest(),
                        "new_expanded_sha256": hb.hexdigest(), "old_expanded_bytes": size_a,
                        "new_expanded_bytes": size_b})
        if first is not None:
            diffs.append(first)
    # 未対応の初期化の記録は、試行のある記録より先として明示する。
    first = min(diffs, key=lambda d: (-1 if d["trial"] is None else d["trial"], d["line"])) if diffs else None
    result = {"all_equal": not diffs, "first_difference": first, "first_by_file": diffs,
              "records": records, "scope": "gzipを展開した全バイト。台帳見出し一行とsec_trial数値だけを除く"}
    Path(destination).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result
