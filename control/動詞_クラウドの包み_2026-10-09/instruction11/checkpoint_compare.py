"""指示11。確定500境の(a)記録・STATE・RNG、(b)P10後の控え、(c)禁止参照0。"""
from pathlib import Path
import argparse,json
from instruction11_io import names, compare_paths, compare_outputs, byte_row, save, sha
from cloud_run import read

def compare(left_case,right_case,completed,destination):
    left_case,right_case=Path(left_case),Path(right_case)
    assert completed in range(500,5001,500)
    a,b=read(left_case/"runtime.json"),read(right_case/"runtime.json")
    x,y=read(left_case/"start.json"),read(right_case/"start.json")
    assert x["machine_sha256"]==y["machine_sha256"]
    for key in ("source_commit","model_commit","observer_sha256","configured_trial_count","horizon"):
        assert a[key]==b[key]
    assert a["configured_trial_count"]==a["horizon"]==5000
    expected=list(a["flags"])
    for flag in ("--stage2-speed","--stage2-cache-prune"):
        i=expected.index(flag);assert expected[i+1]=="off";expected[i+1]="on"
    assert expected==b["flags"] and a["flags"][a["flags"].index("--seeds")+1]=="1"
    def checkpoint(case):
        paths=list((case/"output").glob(f"**/comparison_checkpoints/completed_{completed:04d}"))
        assert len(paths)==1
        path=paths[0];proof=read(path/"confirmed.json")
        assert proof["confirmed"] and proof["completed_trials"]==completed and proof["last_trial"]==completed-1
        for row in proof["records"]:
            import hashlib
            h=hashlib.sha256()
            with (path/"records"/row["path"]).open("rb") as f:
                while data:=f.read(1024*1024):h.update(data)
            assert h.hexdigest()==row["sha256"]
        assert {str(p) for p in names(path/"records")}=={r["path"] for r in proof["records"]}
        assert proof["probe_save_calls"]==proof["probe_restore_calls"] and proof["probe_save_calls"]>0
        return path,proof
    l,lp=checkpoint(left_case);r,rp=checkpoint(right_case)
    rows=[]
    la,ra=names(l/"records"),names(r/"records")
    for rel in sorted(la|ra):
        if rel not in la or rel not in ra:
            rows.append(dict(path=str(rel),equal=False,mismatching_bytes=None));continue
        u,v=(p/"records"/rel for p in (l,r))
        rows.append(compare_paths(rel,u,v,raw_evidence=True))
    for name in ("state.json","rng.json","cache_sme.json","cache_posthoc_p10.json"):
        rows.append(byte_row(name,(l/name).read_bytes(),(r/name).read_bytes()))
    # on側では原控えとP10後の控えが同一であることも確認する。
    on_cache=read(r/"cache_raw.json")==read(r/"cache_posthoc_p10.json")
    forbidden=(lp["forbidden_reads"],rp["forbidden_reads"],rp["guard_forbidden_reads"])
    full_outputs=None
    if completed==5000:
        for case in (left_case,right_case):
            result=read(case/"result.json")
            assert result["exit_code"]==0 and not result.get("warnings"), "両方の正常終了を待つ"
            manifests=[json.loads(line) for line in (case/"output"/"manifest.jsonl").read_text().splitlines()]
            assert len(manifests)==1 and manifests[0]["trial_count"]==5000 and not manifests[0].get("error")
            assert list((case/"output").glob("ledgers/**/*.done")), "原本の完了印を待つ"
        full_outputs=compare_outputs(left_case/"output",right_case/"output")
    # 不一致の後に別の境の一致で採用へ戻さない。累積の判定を新しい場所へ保存。
    history=list(Path(destination).parent.glob("checkpoint_*.json"))
    earlier_failure=any(not read(p)["passed"] for p in history if p!=Path(destination))
    result=dict(passed=all(x["equal"] for x in rows) and on_cache and forbidden==(0,0,0)
                        and not earlier_failure and (full_outputs is None or full_outputs["passed"]),
        completed_trials=completed, full_length_match=completed==5000,
        provisional=completed<5000, flagged_results_usable=False,
        a_records_state_rng_equal=all(x["equal"] for x in rows if x["path"] not in ("cache_sme.json","cache_posthoc_p10.json")),
        b_off_posthoc_p10_equals_on=on_cache and all(x["equal"] for x in rows if x["path"] in ("cache_sme.json","cache_posthoc_p10.json")),
        c_forbidden_reads=forbidden, prior_mismatch=earlier_failure,
        mismatching_files=sum(not x["equal"] for x in rows),files=rows,
        on_raw_cache_retained=True,off_raw_cache_retained=True,
        source_commit=a["source_commit"],observer_sha256=a["observer_sha256"],
        machine_sha256=x["machine_sha256"],comparator_sha256=sha(Path(__file__).read_bytes()))
    result["final_closed_outputs_comparison"]=full_outputs
    result["full_length_flag_match_confirmed"]=result["passed"] and result["full_length_match"]
    result["verb_calibration_and_queue_confirmations_still_required"]=True
    save(destination,result)
    return 0 if result["passed"] else 1

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("left_case",type=Path);p.add_argument("right_case",type=Path)
    p.add_argument("completed",type=int);p.add_argument("destination",type=Path)
    a=p.parse_args();raise SystemExit(compare(a.left_case,a.right_case,a.completed,a.destination))
