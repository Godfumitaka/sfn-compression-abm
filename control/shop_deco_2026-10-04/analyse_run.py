"""既存の分類道具で一本を読む。候補の答えを変えず、水準の配線と記録を加える。"""
from collections import Counter
from pathlib import Path
import argparse
import gzip
import importlib.util
import json
import resource
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]


def load_existing():
    # 別の作業枝のabmを読み込まない。写した研究者用道具だけをロードする。
    for name in ("extrap_reader", "sealrestore", "sealmem", "selcands"):
        spec = importlib.util.spec_from_file_location(name, HERE / "vendor" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "W"):
            mod.W = str(ROOT)
    sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("seed", type=int)
    parser.add_argument("out")
    parser.add_argument("--pilot-all-spoken", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.seed <= 5
    root, dest = Path(args.root).resolve(), Path(args.out).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    fl = json.loads((root / "flag.json").read_text())
    cell_paths = list((root / "ledgers/cells").iterdir())
    assert len(cell_paths) == 1
    cell = cell_paths[0].name
    counts = {cue: Counter() for cue in ("e", "n")}
    misses = {cue: [] for cue in ("e", "n")}
    targets = {}
    with gzip.open(cell_paths[0] / f"seed{args.seed:03d}.jsonl.gz", "rt") as f:
        header = json.loads(next(f))
        assert header["run_seed"] == args.seed
        for line in f:
            row = json.loads(line)
            if row.get("record_type") != "trial":
                continue
            if row.get("held_out_is_door"):
                cue = row["shop_cue"]
                outcome = "黙り" if row["prediction_kind"] == "Abstain" else ("正解" if row["hit"] == 1 else "外れ")
                counts[cue][outcome] += 1
                if outcome == "外れ":
                    misses[cue].append(row["prediction_order"])
                    targets[row["prediction_order"]] = row["hit"]
            if args.pilot_all_spoken and row["prediction_kind"] != "Abstain":
                targets[row["prediction_order"]] = row["hit"]
    load_existing()
    import abm
    assert Path(abm.__file__).resolve().parents[1] == ROOT
    import extrap_reader as er
    import sealrestore as sr
    import sealmem as sm
    import selcands as sc
    original_make = sr.make_task

    def make_task(*params):
        task, _cfg = original_make(*params)
        task["shop_deco"] = fl.get("shop_deco")
        # 実際の走行と同じCLIのnsim等を適用した設定を渡す。
        return task, task["cfg"]

    sr.make_task = make_task
    restore = sr.restore_state
    restored_bad = [0]

    def restore_checked(*params):
        state, bad = restore(*params)
        restored_bad[0] += bad
        return state, bad

    sr.restore_state = restore_checked
    original_iter = er.iter_run
    holder = {}
    mem_count = [0]
    mem_sum = Counter()
    mem_max = [0]
    mem_final = {}
    entity_expected = {}
    bits_mismatch = [0]
    mp_keys = ("G", "Idef", "S", "seat2", "Hc", "Fc", "total", "defs", "nF", "nH", "nU")
    mem_f = gzip.open(dest / "memory.jsonl.gz", "wt", encoding="utf-8")

    def measure(*params, **kwargs):
        import v39
        for tr in original_iter(*params, **kwargs):
            mp = sm.mem_parts(v39, tr["post"])
            entity_expected[tr["t"]] = {"graph_id": tr["world"].G_star.graph_id,
                "full_entity_count": len(tr["world"].G_star.entities),
                "public_entity_count": len(tr["world"].target_graph_partial.entities)}
            actual = (tr["side"].get("v310be") or [{}])[0].get("C_end")
            if actual is not None and mp["total"] != actual:
                bits_mismatch[0] += 1
            mem_f.write(json.dumps({"seed": args.seed, "trial": tr["t"], **mp, "C_end": actual}) + "\n")
            mem_count[0] += 1
            mem_sum.update({k: mp[k] for k in mp_keys})
            mem_max[0] = max(mem_max[0], mp["total"])
            mem_final.clear(); mem_final.update(mp)
            yield tr

    def iter_measured(*params, **kwargs):
        holder["iterator"] = measure(*params, **kwargs)
        class ReadProxy:
            # 分類のyield fromが早く終わっても、記憶用の読み手を閉じない。
            def __iter__(self):
                return self

            def __next__(self):
                return next(holder["iterator"])
        return ReadProxy()

    er.iter_run = iter_measured
    original_analysis = sc.analysis

    def analysis(job):
        check = original_analysis(job)
        # 候補の対象が早く終わっても、状態の指紋と記憶は全試行を読む。
        for _tr in holder["iterator"]:
            pass
        return check

    sc.analysis = analysis
    check = sc.one((str(root), cell, args.seed, targets, str(dest / "candidates")))
    mem_f.close()
    (dest / "validation.json").write_text(json.dumps({"check": check, "args_unrestored": restored_bad[0],
        "C_end_mismatch": bits_mismatch[0], "memory_trials_read": mem_count[0],
        "expected_trials": header["trial_count"]}, ensure_ascii=False, indent=2) + "\n")
    for key in ("予測が本物と違う", "一位が本物の選びと違う", "一位でやり直した答えが本物と違う"):
        assert check[key] == 0, check
    assert check["作った試行"] == len(targets)
    assert restored_bad[0] == 0
    assert bits_mismatch[0] == 0
    assert mem_count[0] == header["trial_count"]
    cases = {}
    for line in (dest / "candidates" / root.name / f"seed{args.seed:03d}.cases.jsonl").read_text().splitlines():
        row = json.loads(line)
        cases[row["trial"]] = row
    days = {}
    for cue in ("e", "n"):
        cls = Counter("選び間違い" if cases[t]["正しく答える候補"] else "区別の喪失" for t in misses[cue])
        assert sum(cls.values()) == counts[cue]["外れ"]
        days[cue] = {**{k: counts[cue][k] for k in ("正解", "外れ", "黙り")},
                     **{k: cls[k] for k in ("選び間違い", "区別の喪失")}}
    public = Counter()
    entity_file = root / "research" / cell / f"seed{args.seed:03d}.entities.jsonl"
    all_entity_rows = [json.loads(s) for s in entity_file.read_text().splitlines()]
    # probe-worldの診断用の別種も同じ生成器を通る。本番の種と場面IDで区別する。
    entity_rows = [r for r in all_entity_rows if r["run_seed"] == header["run_seed"]]
    assert len(entity_rows) == header["trial_count"]
    assert [r["trial"] for r in entity_rows] == list(range(header["trial_count"]))
    for row in entity_rows:
        assert row["level"] == fl["shop_deco"]
        assert all(row[k] == v for k, v in entity_expected[row["trial"]].items())
        public[row["public_entity_count"]] += 1
    result = {"seed": args.seed, "level": fl["shop_deco"], "world": fl["shop_world"],
        "selection": "N3" if fl["select_n3"] else "support", "retention": "D" if fl["use_forget"] is not None else "A",
        "trial_count": header["trial_count"], "days": days, "check": check,
        "args_unrestored": restored_bad[0], "C_end_mismatch": bits_mismatch[0],
        "memory": {"trials": mem_count[0], "mean": {k: mem_sum[k] / mem_count[0] for k in mp_keys},
                   "max_total_bits": mem_max[0], "final": mem_final},
        "public_entity_distribution": dict(public), "pilot_all_spoken": args.pilot_all_spoken,
        "extra_research_scene_records_excluded": len(all_entity_rows) - len(entity_rows),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (dest / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"completed": True, "targets_checked": len(targets), "trials_read": mem_count[0],
                      "peak_rss_bytes": result["peak_rss_bytes"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
