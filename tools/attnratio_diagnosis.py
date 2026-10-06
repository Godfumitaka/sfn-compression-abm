"""案2′の確定済み記録に段1と同じ診断の会計を使う。"""
import argparse
from pathlib import Path
from attnposition_diagnosis import diagnose
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--old-job',type=Path,required=True)
    p.add_argument('--world',type=int,choices=(1,2),required=True);p.add_argument('--seed',type=int,choices=range(1,21),required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();diagnose(a.base,a.old_job,a.world,a.seed,a.output)
