"""指示11。#19の種1・2の試行番号200〜500のM1を、確定した観察から読む。"""
from pathlib import Path
import argparse
from cloud_run import read
from instruction11_io import save,sha

def extract(case1,case2,destination,through=500):
    assert through in (500,1000,2000,3000,4000,4999)
    rows=[]
    commits=[]
    for seed,case in enumerate((Path(case1),Path(case2)),1):
        v=read(case/"runtime.json")
        assert v["flags"][v["flags"].index("--seeds")+1]==str(seed)
        paths=list((case/"output").glob(f"**/comparison_checkpoints/m1_at_trial{through}.json"))
        assert len(paths)==1,"指定番号の記録が確定するまで待つ。未読部分を補わない"
        row=read(paths[0]);assert row["zero_based"] and row["first_trial"]==200 and row["last_trial"]==through and row["trials"]==through-199
        rows.append(dict(seed=seed,**row,proof_sha256=sha(paths[0].read_bytes())))
        commits.append(v["source_commit"])
    assert commits[0]==commits[1]
    result=dict(rows=rows,claude_confirmation_required=True,
                no_stop_criterion=all(not x["stop_criterion"] for x in rows),
                seeds3_to10_may_start=False,other_queue_conditions_required=True,
                do_not_wait_for_calibration_1000=True,report_to_Claude_if_criterion=True,
                source_commit=commits[0],automatic_stop=False)
    save(destination,result)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("seed1",type=Path);p.add_argument("seed2",type=Path);p.add_argument("destination",type=Path)
    p.add_argument("--through",type=int,default=500)
    a=p.parse_args();extract(a.seed1,a.seed2,a.destination,a.through)
