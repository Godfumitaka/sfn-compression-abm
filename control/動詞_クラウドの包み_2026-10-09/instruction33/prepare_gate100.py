"""指示33。別の固定sourceと新しい出力先に三本のspecを準備するだけ。"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def prepare(base, candidate, case_root, machine='Mac'):
    base,candidate,case_root=map(lambda p:Path(p).resolve(),(base,candidate,case_root))
    plan=json.loads((HERE/'plan.json').read_text())['commands']
    made=[]
    for label,draft in plan.items():
        source=base if label=='baseline6e4' else candidate
        assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==draft['source_commit']
        assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip()==draft['source_tree']
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=source)
        case=case_root/label;case.mkdir(parents=True,exist_ok=False)
        output=case/'output'
        command=[sys.executable,str(HERE/'tools/production/prefix_measurement_driver.py'),str(source),'100',
                 str(source/'config/sweep_verb_hide1_s1_2026-10-04.json'),str(output),*draft['flags']]
        observer_files={str(HERE/file):hashlib.sha256((HERE/file).read_bytes()).hexdigest() for file in (
            'tools/production/prefix_measurement_driver.py','tools/checkpoint_observer.py',
            'tools/confirmed_hash.py','tools/instruction11_io.py','tools/timing100_observer.py')}
        spec={**draft,'cwd':str(source),'output':str(output),'command':command,'machine':machine,
              'observer_files':observer_files,'runner_sha256':hashlib.sha256((HERE/'run_gate100.py').read_bytes()).hexdigest()}
        (case/'spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
        made.append(dict(case=str(case),spec_sha256=hashlib.sha256((case/'spec.json').read_bytes()).hexdigest(),
             ready_to_start=False,model_starts=0,required_memory_gib=10,required_CPU_slots=6,required_model_slots=5))
    return made


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('base');p.add_argument('candidate');p.add_argument('case_root');p.add_argument('--machine',default='Mac')
    a=p.parse_args();print(json.dumps(prepare(a.base,a.candidate,a.case_root,a.machine),ensure_ascii=False))
