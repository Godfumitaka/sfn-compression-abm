"""台帳本体・全side・控え破棄記録を、欄の丸めや並べ替えなしで照合する。"""
from pathlib import Path
import argparse
import gzip
import hashlib
import itertools
import json
import re


def without_measured_sec(line):
    # 2026-10-05に承認された実時間の数値だけ。他の文字は全て残す。
    value = json.loads(line)["sec_trial"]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    pattern = rb'("sec_trial"\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?=\s*[,}])'
    normalized, count = re.subn(pattern, rb'\1<measured_time>', line)
    assert count == 1
    return normalized


def compare_streams(left, right, *, ledger=False, timing=False):
    opener = gzip.open if ledger else open
    raw_a, raw_b = hashlib.sha256(), hashlib.sha256()
    cmp_a, cmp_b = hashlib.sha256(), hashlib.sha256()
    equal = raw_equal = True
    with opener(left, "rb") as a, opener(right, "rb") as b:
        # cfvalueは一行ずつ、それ以外は固定長ずつ読む。大量のSME状態を一括展開しない。
        ia = iter(a.readline, b"") if timing else iter(lambda: a.read(65536), b"")
        ib = iter(b.readline, b"") if timing else iter(lambda: b.read(65536), b"")
        for x, y in itertools.zip_longest(ia, ib, fillvalue=b""):
            raw_a.update(x);raw_b.update(y)
            xx = without_measured_sec(x) if timing and x else x
            yy = without_measured_sec(y) if timing and y else y
            cmp_a.update(xx);cmp_b.update(yy)
            raw_equal &= x == y
            equal &= xx == yy
    return {"equal": equal, "raw_equal": raw_equal,
        "left_sha256": raw_a.hexdigest(), "right_sha256": raw_b.hexdigest(),
        "comparison_left_sha256": cmp_a.hexdigest(), "comparison_right_sha256": cmp_b.hexdigest(),
        "exception": "sec_trial数値だけ。元の時間は両側で保存" if timing else None,
        "ledger_decompressed_body_including_header": ledger}


def compare(left, right):
    left, right = Path(left), Path(right)
    files = {}
    # done・manifest・受付ログは実時間を持つ走行管理資料で、台帳本体やsideではない。
    for category in ("side", "evictions", "ledgers"):
        def paths(root):
            return {str(p.relative_to(root)):p for p in (root / category).rglob("*")
                    if p.is_file() and (category != "ledgers" or p.name.endswith(".jsonl.gz"))}
        a, b = paths(left), paths(right)
        for name in sorted(a.keys() | b.keys()):
            if name not in a or name not in b:
                files[name] = {"equal": False, "missing_side": "left" if name not in a else "right"}
            else:
                files[name] = compare_streams(a[name], b[name], ledger=category == "ledgers",
                    timing=name.endswith(".cfvalue.jsonl"))
    files["flag.json"] = compare_streams(left / "flag.json", right / "flag.json")
    assert any(name.startswith("ledgers/") for name in files)
    assert any(name.startswith("side/") for name in files)
    return {"passed": all(row["equal"] for row in files.values()), "left":str(left), "right":str(right),
        "compared_files": len(files), "files":files}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("left");parser.add_argument("right");parser.add_argument("output")
    args = parser.parse_args()
    result = compare(args.left, args.right)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed":result["passed"], "compared_files":result["compared_files"]}), flush=True)
    raise SystemExit(0 if result["passed"] else 1)
