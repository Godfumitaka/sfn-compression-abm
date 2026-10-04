"""判断の五列と、見出しを除いた台帳本体を全バイトで確認する。"""
from pathlib import Path
import gzip
import hashlib
import json
from itertools import zip_longest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "codex_sme_pypy_2026-10-04"))
from compare_expanded import difference, excerpt

FIELDS = ("prediction_kind", "predicted_edge", "hit", "R_used", "abstain_reason")


def lines(p):
    with gzip.open(p, "rb") as f:
        next(f)
        yield from f


def compare(old, new, destination):
    old, new = Path(old), Path(new)
    aa = {p.relative_to(old): p for p in old.glob("ledgers/**/*.jsonl.gz")}
    bb = {p.relative_to(new): p for p in new.glob("ledgers/**/*.jsonl.gz")}
    assert aa.keys() == bb.keys(), "台帳のファイル集合が違う"
    records, differences = [], []
    for name in sorted(aa):
        ha, hb = hashlib.sha256(), hashlib.sha256()
        rows, first, judgment_diffs, equal = 0, None, [], True
        for i, (a, b) in enumerate(zip_longest(lines(aa[name]), lines(bb[name]), fillvalue=b"")):
            ha.update(a); hb.update(b); rows += 1
            x, y = json.loads(a) if a else {}, json.loads(b) if b else {}
            if any(x.get(k) != y.get(k) for k in FIELDS):
                judgment_diffs.append(i)
            if a != b:
                equal = False
                if first is None:
                    d = difference(x, y)
                    field, u, v = d if d is not None else ("JSONの字句", a[:200].decode(), b[:200].decode())
                    first = {"trial": i, "human_trial": i + 1, "field": field,
                             "baseline": excerpt(u), "candidate": excerpt(v)}
        row = {"file": str(name), "rows": rows, "body_all_equal": equal,
               "judgment_differing_trials": judgment_diffs, "first_difference": first,
               "baseline_body_sha256": ha.hexdigest(), "candidate_body_sha256": hb.hexdigest()}
        records.append(row)
        if first is not None:
            differences.append(first)
    result = {"passed": not differences, "records": records,
              "judgment_fields": FIELDS, "scope": "台帳見出し一行だけを除き、本体の全バイトを比較"}
    Path(destination).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result
