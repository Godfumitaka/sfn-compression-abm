"""既存受付の内側で新しい関門の一走行だけを始める。既存run_caseを変更しない。"""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pair_common import ROOT, NR, completion, read, sha, validate_spec
from instruction11_io import save

sys.path.insert(0, str(NR))
from inbox_snapshot import snapshot
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'


def main():
    case = Path(sys.argv[1]).resolve()
    assert case.parent == ROOT and case.name in ('probe100_off', 'probe100_on')
    mode = case.name.rsplit('_', 1)[1]
    spec = read(case / 'spec.json')
    validate_spec(spec, mode)
    prepared = read(ROOT / 'prepared.json')
    for filename, expected in prepared['files'].items():
        assert sha(ROOT / filename) == expected
    assert not (case / 'admitted_status.json').exists()
    for filename in ('result.json', 'pid.json', 'run.log', 'resources.jsonl'):
        assert not (case / filename).exists(), '同じ関門の原出力へ再投入しない'
    assert not Path(spec['output']).exists()
    assert datetime.now(timezone.utc) < datetime.fromisoformat(spec['start_deadline_jst'])
    for path, expected in spec['sources'].items():
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip() == expected
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=path, text=True).strip()
    for path, expected in spec['observer_files'].items():
        assert sha(path) == expected
    save(case / 'admitted_status.json', dict(at=datetime.now().astimezone().isoformat(),
         state='admitted_waiting_for_existing_resource_gate', wrapper_pid=os.getpid(), production_started=False))
    # 新しい模型の開始を試みるときだけ、実workerと機械の原値を記録する。
    snapshot(SimpleNamespace(workspace=NR.parent.parent, output=case / 'before_start.json'))
    machine = {key: subprocess.check_output(command, text=True) for key, command in {
        'physical_cpu': ['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'],
        'physical_memory_bytes': ['/usr/sbin/sysctl', '-n', 'hw.memsize'],
        'swap': ['/usr/sbin/sysctl', 'vm.swapusage'],
        'thermal': ['/usr/bin/pmset', '-g', 'therm']}.items()}
    identity = platform.node() + subprocess.check_output(['/usr/sbin/sysctl', '-n', 'kern.boottime'], text=True)
    machine.update(at=datetime.now().astimezone().isoformat(),
                   machine_boot_sha256=hashlib.sha256(identity.encode()).hexdigest(),
                   free_disk_bytes=shutil.disk_usage(case).free,
                   swap_samples=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-11:])
    save(case / 'machine_before_start.json', machine)
    # 待機・模型8本・CPU・熱・容量の既存判定と監督をそのまま使う。
    rc = subprocess.call([PY, str(ROOT / 'run_case_birth.py'), str(case)])
    if rc == 0:
        evidence = completion(case)
        save(case / 'completion_checked.json', evidence)
    save(case / 'admitted_finished.json', dict(at=datetime.now().astimezone().isoformat(), exit_code=rc,
         production_started=False, model_started=(case / 'pid.json').exists(), completed_trials=100 if rc == 0 else None))
    return rc


if __name__ == '__main__':
    sys.exit(main())
