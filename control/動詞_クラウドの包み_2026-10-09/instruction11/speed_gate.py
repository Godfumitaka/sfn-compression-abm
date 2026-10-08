"""指示11：同機械の200組を読み、試験回答・試験後の学習と実発生数を記録。"""
from pathlib import Path
import argparse, gzip, json,re
from cloud_run import read, complete
from cloud_compare import compare
from instruction11_io import content, compare_outputs, save, sha

def mechanisms(case):
    out = Path(case)/"output"
    counts = dict(birth=0, assimilation=0, forgetting_FH=0, forgetting_HU=0,
                  definition_removed=0, probe_answers=0)
    seen_side = set()
    for p in sorted(out.glob("side/**/*.jsonl")):
        if p.name.endswith(".probe.jsonl"):
            counts["probe_answers"] += len(content(p).splitlines())
            continue
        for line in content(p).splitlines():
            row = json.loads(line)
            if row.get("kind") in ("birth","assim"):
                key = (row.get("trial"),row.get("R"),row["kind"])
                if key not in seen_side:
                    counts["birth" if row["kind"]=="birth" else "assimilation"] += 1
                    seen_side.add(key)
    ledger = list(out.glob("ledgers/**/*.jsonl.gz"))
    assert len(ledger)==1
    trials = []
    for line in content(ledger[0]).splitlines():
        row = json.loads(line)
        if row.get("record_type")!="trial": continue
        trials.append(row["prediction_order"])
        for event in row["deletion_event"]:
            if event.get("v39")=="FH": counts["forgetting_FH"] += 1
            elif event.get("v39")=="HU": counts["forgetting_HU"] += 1
            elif event.get("kind")=="definition_removed": counts["definition_removed"] += 1
    assert trials==list(range(200)), "試験後100〜199も含む確定200行を要求"
    m=complete(Path(case),200)
    p=m.get("probeworld",{})
    counts.update(probe_fingerprint_checks=p.get("fingerprint_checks",0),
                  probe_attention_restore_checks=len(p.get("attention_checks",[])))
    assert counts["probe_answers"]==p["rows"]==96
    guards=list(out.rglob("p10_cache_guard.jsonl.gz"))
    if guards:
        assert len(guards)==1
        rows=[json.loads(line) for line in content(guards[0]).splitlines()]
        summary=read(Path(str(guards[0])+".summary.json"))
        counts.update(p10_boundaries=sum(x.get("kind")=="trial_boundary" for x in rows),
                      p10_removed_cache=sum(x.get("removed",{}).get("cache",0) for x in rows if x.get("kind")=="trial_boundary"),
                      p10_removed_cache_rng=sum(x.get("removed",{}).get("cache_rng",0) for x in rows if x.get("kind")=="trial_boundary"),
                      p10_forbidden_reads=summary["forbidden_reads"])
        assert summary["native_loop_returned"] and counts["p10_forbidden_reads"]==0
        assert counts["p10_removed_cache"]==summary["removed"]["cache"]
        assert counts["p10_removed_cache_rng"]==summary["removed"]["cache_rng"]
    else:
        counts.update(p10_boundaries=None,p10_removed_cache=None,p10_removed_cache_rng=None,
                      p10_forbidden_reads=None)
    noforget="--no-forget-exec" in read(Path(case)/"runtime.json")["flags"]
    executed=counts["forgetting_FH"]+counts["forgetting_HU"]+counts["definition_removed"]
    if noforget: assert executed==0
    def status(n): return "実発生を確認" if n else "関門では未検証"
    return dict(counts=counts, coverage=dict(
        birth=status(counts["birth"]),
        forgetting="較正の命令により実行停止・実変換0" if noforget else status(executed),
        p10_discard=status((counts["p10_removed_cache"] or 0)+(counts["p10_removed_cache_rng"] or 0)),
        probe_save_restore=status(counts["probe_fingerprint_checks"]) if counts["probe_attention_restore_checks"] else "関門では未検証"),
        ledger_trials=200, post_probe_learning_trials=list(range(100,200)),
        counts_are_actual=True, model_modified=False)

def gate(left,right,destination,on100_decision,on100_report_commit):
    left,right=Path(left),Path(right)
    assert re.fullmatch("[0-9a-f]{40}",on100_report_commit), "on100を先に判定・報告した通常pushのコミットを記す"
    decision=read(on100_decision)
    expected=read(Path(__file__).with_name("plan.json"))
    from cloud_run import first_pair_check
    selected=decision["pairs"][decision["selected_pair"]]["comparison"]
    first_pair_check(decision,dict(model_commit=expected["base_model_commit"],
        observer_sha256="6ca7af8f64dbc9599ac256f84d15930d37d102aeff56bf2e1f29b861c49217f4"),selected)
    assert selected["completed_trials"]==100
    destination=Path(destination);destination.mkdir(exist_ok=False)
    compare(left,right,destination/"content_comparison.json",200)
    a=compare_outputs(left/"output",right/"output")
    # stage2もTIME欄以外を比べる。原結果を合格に書き換えない。
    save(destination/"all_outputs_comparison.json",a)
    l,r=mechanisms(left),mechanisms(right)
    save(destination/"mechanisms_off.json",l);save(destination/"mechanisms_on.json",r)
    basic=read(destination/"content_comparison.json")
    proof=dict(passed=basic["passed"] and a["passed"], completed_trials=200,
               source_commit=basic["source_commit"], model_commit=basic["model_commit"],
               observer_sha256=basic["observer_sha256"],machine_sha256=basic["machine_sha256"],
               calibration="--no-forget-exec" in read(left/"runtime.json")["flags"],
               comparator_sha256=sha(Path(__file__).read_bytes()),
               io_sha256=sha(Path(__file__).with_name("instruction11_io.py").read_bytes()),
               on100_decision_sha256=sha(Path(on100_decision).read_bytes()),
               on100_report_commit=on100_report_commit,
               full_5000_match=False, production_result_status="仮",
               comparison_files=["content_comparison.json","all_outputs_comparison.json"],
               coverage={"off":l["coverage"],"on":r["coverage"]})
    required=("birth","probe_save_restore")
    proof["coverage_verified_for_production"]=all(
        item["coverage"][k]=="実発生を確認" for item in (l,r) for k in required
    ) and r["coverage"]["p10_discard"]=="実発生を確認" and (
        proof["calibration"] or all(item["coverage"]["forgetting"]=="実発生を確認" for item in (l,r)))
    save(destination/"gate.json",proof)
    return 0 if proof["passed"] else 1

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("left",type=Path);p.add_argument("right",type=Path);p.add_argument("destination",type=Path)
    p.add_argument("--on100-decision",required=True,type=Path)
    p.add_argument("--on100-report-commit",required=True)
    a=p.parse_args();raise SystemExit(gate(a.left,a.right,a.destination,a.on100_decision,a.on100_report_commit))
