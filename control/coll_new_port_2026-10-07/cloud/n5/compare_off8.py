"""同じ固定版の八体OFF直列・並列を、保存済み出力だけで比較する。"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import cloud_run as R


def lines(path):
    with (gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")) as stream:
        yield from stream


def check(name, left, right):
    hashes = [hashlib.sha256(), hashlib.sha256()]
    count = [0, 0]
    first = None
    for n, pair in enumerate(itertools.zip_longest(left, right), 1):
        for i, value in enumerate(pair):
            if value is not None:
                hashes[i].update(value)
                count[i] += 1
        if pair[0] != pair[1] and first is None:
            first = n
    return {"name": name, "passed": first is None, "lines": count,
            "first_difference": first, "sha256": [h.hexdigest() for h in hashes]}


def checked_done(row, output, commit):
    assert row["code_commit"] == commit, "終了記録の固定版が違う"
    path = output / "ledgers/cells" / row["cell"] / f"seed{row['seed']:03d}.jsonl.gz"
    assert path.is_file() and row["ledger_bytes"] == path.stat().st_size, "実サイズが違う"
    header = json.loads(next(lines(path)))
    assert header["code_commit"] == commit
    result = dict(row)
    for field in ("code_commit", "ledger_bytes", "elapsed_sec", "finished_at", "peak_rss_mb"):
        result.pop(field, None)
    return result


def files(root):
    return {str(p.relative_to(root)): p for p in root.rglob("*") if p.is_file()}


def normalized(row):
    return [json.dumps(row, ensure_ascii=False).encode()]


def compare(serial_folder, parallel_folder):
    folders = [Path(serial_folder), Path(parallel_folder)]
    runtime = [R.read(p / "runtime.json") for p in folders]
    for r in runtime:
        R.validate(r)
        assert r["phase"] == "off200" and r["seeds"] == [1]
    assert runtime[0]["parallel"] is False and runtime[1]["parallel"] is True
    assert [x for x in runtime[0]["model_argv"] if x != "--v311c-serial"] == runtime[1]["model_argv"], "並列の旗以外の引数が違う"
    assert runtime[0]["config_sha256"] == runtime[1]["config_sha256"]
    outputs = [Path(r["output"]) for r in runtime]
    resource = [R.read(p / "resource.json") for p in folders]
    assert all(x["exitcode"] == 0 and not x["warnings"] for x in resource)
    checks, metadata = [], []
    for directory in ("ledgers", "side", "evictions"):
        sides = [files(out / directory) for out in outputs]
        assert sides[0].keys() == sides[1].keys(), (directory, "種類が違う")
        for key in sorted(sides[0]):
            paths = [side[key] for side in sides]
            if directory == "ledgers" and key.endswith(".jsonl.gz"):
                headers = [json.loads(next(lines(p))) for p in paths]
                assert all(h["code_commit"] == R.COMMIT for h in headers)
                assert headers[0] == headers[1], "同版の見出しに差がある"
                for path, spec in zip(paths, runtime):
                    stream = lines(path)
                    next(stream)
                    body = [json.loads(x) for x in stream]
                    assert [row["trial"] for row in body] == list(range(200)), "200試行の本体が揃っていない"
                    index = (int(path.name.split(".")[0][4:]) - 1) // 1000
                    assert 0 <= index < 8
                    assigned = float(R.flag(spec["model_argv"], "--v311c-f").split(",")[index])
                    assert all(row["f_realized"] == assigned for row in body)
                checks.append(check(directory + "/" + key, lines(paths[0]), lines(paths[1])))
            elif key.endswith(".done"):
                rows = [checked_done(R.read(p), out, R.COMMIT) for p, out in zip(paths, outputs)]
                metadata.append({"file": directory + "/" + key, "fixed_commit_and_actual_size": True})
                checks.append(check(directory + "/" + key, *[normalized(r) for r in rows]))
            elif key.endswith(".cfvalue.jsonl"):
                def without_clock(path):
                    for line in lines(path):
                        row = json.loads(line)
                        assert "sec_trial" in row
                        del row["sec_trial"]
                        yield json.dumps(row, ensure_ascii=False).encode()
                checks.append(check(directory + "/" + key, *map(without_clock, paths)))
            else:
                checks.append(check(directory + "/" + key, *map(lines, paths)))
    def events(path):
        for line in lines(path):
            if json.loads(line).get("kind") != "summary":
                yield line
    checks.append(check("通信全事象", *[events(out / "comm/run001.jsonl") for out in outputs]))
    summaries = [R.read(out / "comm/run001.summary.json") for out in outputs]
    for summary, out in zip(summaries, outputs):
        assert summary["trials"] == 200 and not summary["errors"]
        assert summary["delivered"] == 0 and len(summary["agents"]) == 8
        for agent in summary["agents"]:
            assert agent["v39"].get("not_in_dictionary", 0) == 0
            assert agent["v311c"]["dictionary_checks"] == 400
        summary["agents"] = [checked_done(row, out, R.COMMIT) for row in summary["agents"]]
        tomb = list((out / "evictions").rglob("*.summary.json"))
        assert len(tomb) == 8
        assert all(R.read(p)["tombstone_enabled"] and R.read(p)["tombstone_hits"] == 0 for p in tomb)
    checks.append(check("終了集計の模型の全欄", *map(normalized, summaries)))
    for name in ("run001.jsonl.state.jsonl", "run001.lineage.jsonl"):
        checks.append(check(name, *[lines(out / "comm" / name) for out in outputs]))
    for agent in range(8):
        for suffix in ("final-sme.jsonl.gz", "model-rng.jsonl", "rng.jsonl"):
            paths = [folder / f"agent{agent}.{suffix}" for folder in folders]
            assert paths[0].is_file() == paths[1].is_file(), "乱数・控えの保存の有無が違う"
            if suffix != "rng.jsonl":
                assert all(p.is_file() for p in paths)
            if paths[0].is_file():
                checks.append(check(f"個体{agent}:{suffix}", *map(lines, paths)))
    return {"candidate": R.COMMIT, "time": datetime.now(timezone.utc).isoformat(),
            "passed": all(c["passed"] for c in checks), "checks": checks,
            "mandatory_metadata_checks": metadata, "tombstone_hits": 0,
            "dictionary_unknown_names": 0,
            "exclusions": ["cfvalue.sec_trial", "終了記録の時計/RSS",
                           "固定版と物理サイズを検査したcode_commit/ledger_bytes",
                           "flag/manifestの起動・出力先情報（specで別検査）",
                           "研究者の性能採録（本体・乱数・状態は除外しない）"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial_evidence")
    parser.add_argument("parallel_evidence")
    parser.add_argument("result")
    args = parser.parse_args()
    assert not Path(args.result).exists(), "判定を上書きしない"
    try:
        result = compare(args.serial_evidence, args.parallel_evidence)
    except (AssertionError, KeyError, FileNotFoundError) as error:
        result = {"candidate": R.COMMIT, "passed": False, "failure": str(error), "stop": True}
    R.save(args.result, result)
    print(json.dumps({"passed": result["passed"], "result": args.result}, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
