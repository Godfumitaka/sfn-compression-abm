"""係が受付表と熱・性能を確認した記録を作る。受付を代行しない。"""
import argparse
from pathlib import Path
import subprocess
import sys
from run_B6 import HERE,host,now,read,save,spec_sha,validate

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('name');p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
p.add_argument('--jobs',type=Path,required=True);p.add_argument('--mem',type=float,required=True)
p.add_argument('--existing-gb',type=float,required=True)
p.add_argument('--resource-file',type=Path);p.add_argument('--memory-note',required=True)
p.add_argument('--no-resource-warning',action='store_true',required=True)
p.add_argument('--record',type=Path,required=True)
a=p.parse_args();assert sys.platform.startswith('linux')
s=validate(read(HERE/'spec.json'));assert a.name==s['name']
assert a.existing_gb>=0 and 0<a.mem<=24 and a.existing_gb+a.mem<=24
status=subprocess.check_output([sys.executable,str(a.jobs),'status'],text=True)
basis=dict(kind='measured' if a.resource_file else 'bootstrap',note=a.memory_note)
if a.resource_file:basis['resource_file']=str(a.resource_file.resolve())
assert a.resource_file is not None,'八体の実測と条件差の記録が必要'
save(a.record,dict(host=host(),spec_sha256=spec_sha(s),checked_at=now(),
 source=str(a.source.resolve()),output=str(a.root.resolve()/'outputs'/a.name),reservation_gb=a.mem,
 warning=False,cpu_limit_models=8,budget_gb=24,existing_reservations_gb=a.existing_gb,
 admission_status=status,memory_basis=basis,resource_warning_checked_by='デスクトップの走行の係'))
print(a.record)
