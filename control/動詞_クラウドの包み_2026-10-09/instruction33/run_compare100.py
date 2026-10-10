"""指示33。jobs0.3GiBの内側で、一度だけ同機械の全内容を読む。"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from run_gate100 import start_counts
from compare100 import compare


def admitted(left,right,destination,mode,clearance=None):
    left,right,destination=map(Path,(left,right,destination))
    assert not destination.exists() and mode in ('a','b')
    assert destination.name==f'speed100_{mode}.json', '結果の名前だけを比較のglobへ入れる'
    assert datetime.now(timezone.utc)<datetime.fromisoformat('2026-10-13T09:00:00+09:00')
    linux=sys.platform.startswith('linux')
    if linux:
        proof=json.loads(Path(clearance).read_text())
        assert 0<=time.time()-proof['checked_epoch']<=60 and proof['memory_reservation_gb']==0.3
        assert proof['memory_admission_ok'] and proof['swap_stable_10min'] and proof['thermal_ok'] and proof['warning'] is False
        budget=proof['cpu_budget'];assert budget==proof['physical_cpu_count']-2
        boot=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        assert proof['machine_boot_sha256']==boot
        model_limit=budget if proof.get('dedicated_google_cloud_gate_and_production_machine') is True else 8
        thermal='既存受付の最新実確認'
    else:
        assert sys.platform=='darwin'
        budget=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.physicalcpu'],text=True))-2
        boot=hashlib.sha256(subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'])).hexdigest()
        thermal=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True)
        assert 'No thermal warning level has been recorded' in thermal
        assert not re.search(r'CPU_Speed_Limit\s*=\s*(?!100(?:\s|$))\d+',thermal)
        model_limit=8
    for case in (left,right):
        original=json.loads((case/'machine_before_start.json').read_text())
        assert original['machine_boot_sha256']==boot
    raw=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,pgid=,rss=,stat=,args='],text=True)
    counts=start_counts(raw)
    # runtimeは結果フォルダの外。原psは非公開で保持する。
    runtime=right/f'comparison_runtime_{mode}';runtime.mkdir(exist_ok=False)
    (runtime/'before_start.json').write_text(json.dumps(dict(at=datetime.now().astimezone().isoformat(),
        processes=raw,thermal=thermal,budget=budget,**counts),ensure_ascii=False,indent=2)+'\n')
    assert counts['model_process_count']<=model_limit and counts['unknown_active_spawn']==0
    assert counts['outside_heavy']+1<=budget and shutil.disk_usage(runtime).free>=20*2**30
    return compare(left,right,destination,mode)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('left');p.add_argument('right');p.add_argument('destination')
    p.add_argument('--mode',choices=('a','b'),required=True);p.add_argument('--clearance')
    a=p.parse_args();raise SystemExit(admitted(a.left,a.right,a.destination,a.mode,a.clearance))
