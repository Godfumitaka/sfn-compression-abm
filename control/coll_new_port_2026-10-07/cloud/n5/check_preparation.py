"""模型を走らせず、台本の開始防止と比較の拒否条件を合成記録で確かめる。"""
import copy
import gzip
import json
from pathlib import Path
import sys
import cloud_run as R
import compare_off8 as C
import export_tables as E


def rejected(function):
    try:
        function()
    except (AssertionError, KeyError, FileNotFoundError):
        return True
    raise AssertionError("拒否すべき例が通った")


def fixture(root):
    folders = [root / "serial", root / "parallel"]
    specs = [R.read(R.HERE / "specs" / f"cloud_off8_{mode}200.json") for mode in ("serial", "parallel")]
    for folder, spec in zip(folders, specs):
        folder.mkdir(parents=True)
        output = folder / "output"
        runtime = R.materialize(spec, Path("/fixture/source"), output, folder, "python3", None)
        R.save(folder / "runtime.json", runtime)
        R.save(folder / "resource.json", {"exitcode": 0, "warnings": [], "elapsed_seconds": 1,
                                         "rss_sum_peak_bytes": 1})
        summary = {"trials": 200, "errors": [], "delivered": 0, "agents": []}
        for directory in ("comm", "side", "evictions", "ledgers/cells"):
            (output / directory).mkdir(parents=True)
        for i in range(8):
            seed = 1 + 1000 * i
            cell = f"actor{i}"
            ledger = output / "ledgers/cells" / cell / f"seed{seed:03d}.jsonl.gz"
            ledger.parent.mkdir()
            with gzip.open(ledger, "wt") as stream:
                stream.write(json.dumps({"code_commit": R.COMMIT, "agent_ids": ["agent"]}) + "\n")
                for t in range(200):
                    stream.write(json.dumps({"trial": t, "f_realized": 0.1 if i < 4 else 0.9,
                                             "opaque_state": "state-" + str(t)}) + "\n")
            row = {"cell": cell, "seed": seed, "code_commit": R.COMMIT,
                   "ledger_bytes": ledger.stat().st_size, "elapsed_sec": 2, "finished_at": "clock",
                   "peak_rss_mb": 1, "v39": {"not_in_dictionary": 0},
                   "v311c": {"dictionary_checks": 400}}
            R.save(ledger.with_suffix("").with_suffix(".done"), row)
            summary["agents"].append(row)
            R.save(output / "evictions" / f"agent{i}.summary.json", {"tombstone_enabled": True, "tombstone_hits": 0})
            for suffix in ("final-sme.jsonl.gz", "model-rng.jsonl", "rng.jsonl"):
                path = folder / f"agent{i}.{suffix}"
                if path.suffix == ".gz":
                    with gzip.open(path, "wb") as stream:
                        stream.write(b'{"state":"same"}\n')
                else:
                    path.write_bytes(b'{"state":"same"}\n')
        R.save(output / "comm/run001.summary.json", summary)
        for name in ("run001.jsonl", "run001.jsonl.state.jsonl", "run001.lineage.jsonl"):
            (output / "comm" / name).write_bytes(b'{"kind":"fixture","state":"same"}\n')
    return folders


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    checks = []
    specs = [R.read(p) for p in sorted((R.HERE / "specs").glob("*.json"))]
    for spec in specs:
        R.validate(spec)
    checks.append("13specの体数・種・旗・順の構造")
    bad = copy.deepcopy(specs[0])
    bad["seeds"] = [21]
    checks.append("種21を拒否" if rejected(lambda: R.validate(bad)) else "")
    prod = next(s for s in specs if s["phase"] == "production1740")
    rejected(lambda: R.materialize(prod, Path("/s"), Path("/o"), Path("/e"), "python3", None))
    checks.append("未確定L50_refを拒否")
    rejected(lambda: R.prerequisite(prod, root / "missing-gates", None))
    checks.append("未合格の先行関門と取得記録を拒否")
    folders = fixture(root / "full")
    assert C.compare(*folders)["passed"]
    checks.append("合成八体200の直列並列が一致")
    out = folders[0] / "output"
    row = R.read(next((out / "ledgers/cells").glob("*/*.done")))
    bad_row = dict(row, code_commit="wrong")
    rejected(lambda: C.checked_done(bad_row, out, R.COMMIT))
    checks.append("誤った固定版を拒否")
    rejected(lambda: C.checked_done(dict(row, ledger_bytes=row["ledger_bytes"] + 1), out, R.COMMIT))
    checks.append("誤った実サイズを拒否")
    (folders[1] / "agent0.model-rng.jsonl").write_bytes(b'{"state":"changed"}\n')
    assert not C.compare(*folders)["passed"]
    checks.append("乱数の一バイト差を不合格")
    path = next((folders[1] / "output/ledgers/cells").glob("*/*.jsonl.gz"))
    rows = list(C.lines(path))
    header = json.loads(rows[0]); header["agent_ids"] = ["changed"]
    with gzip.open(path, "wb") as stream:
        stream.write(json.dumps(header).encode() + b"\n")
        stream.writelines(rows[1:])
    rejected(lambda: C.compare(*folders))
    checks.append("同版の見出しの変更を拒否")
    dest = E.export(folders[0], root / "tables")
    assert sorted(p.name for p in dest.iterdir()) == ["runs.tsv", "sha256.tsv"]
    checks.append("表とsha256だけを書き出す")
    result = {"scope": "合成記録による台本検査のみ。模型の関門判定ではない",
              "real_model_runs": 0, "aws_api_calls": 0, "checks": checks, "checks_passed": len(checks)}
    R.save(root / "preparation-checks.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
