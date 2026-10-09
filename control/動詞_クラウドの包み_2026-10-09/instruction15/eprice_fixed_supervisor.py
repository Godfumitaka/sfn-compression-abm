"""指示15の#19の20を、列の固定E価格で新しい出力へ一度受付する。"""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
NR = ROOT.parent
RR = NR.parent / 'report-results'
CASE = ROOT / 'production_lambda20_eprice_fixed'
PY = '/opt/homebrew/opt/python@3.12/bin/python3.12'
JOBS = str(Path.home() / 'jobs/jobs.py')
sys.path.insert(0, str(NR))
from inbox_snapshot import snapshot

def save(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def state(**value):
    save('eprice_fixed_status.json', dict(at=datetime.now().astimezone().isoformat(),
         supervisor_pid=os.getpid(), **value))

try:
    assert not (ROOT / 'eprice_fixed_status.json').exists(), '二重起動をしない'
    assert json.loads((ROOT / 'on100_logfix_comparison.json').read_text())['passed']
    assert json.loads((ROOT / 'production_lambda20/result.json').read_text())['exit_code'] == 0
    assert json.loads((NR / 'measurements/allin_s01_300/cancelled_by_instruction14.json').read_text())['started'] is False
    for f in [NR / 'gates/alloff_5000/comparison.json',
              NR / 'instruction6_checks/shop_retry1_comparison.json',
              NR / 'instruction6_checks/cue_counts/output/counts.json']:
        assert json.loads(f.read_text())['passed']
    inbox = (RR / 'control/受け箱/動詞の世界の係.md').read_text()
    for section in re.split(r'(?=^## 指示 \d+)', inbox, flags=re.M):
        if section.startswith('## 指示 '):
            assert '受領（' in section, '未受領指示があるため新しい開始をしない'
    spec = json.loads((CASE / 'spec.json').read_text())
    original = json.loads((ROOT / 'production_lambda20/spec.json').read_text())
    new_flags = list(original['flags'])
    new_flags[new_flags.index('--e-price') + 1] = '0.01873710622997919'
    assert spec['flags'] == new_flags
    assert spec['command'][6:] == new_flags
    assert spec['sources'] == original['sources'] and spec['observer_files'] == original['observer_files']
    assert spec['completed_trials'] == 20 and spec['configured_trial_count'] == spec['horizon'] == 5000
    assert datetime.now(timezone.utc) < datetime.fromisoformat(spec['start_deadline_jst'])
    for rel in ['result.json', 'pid.json', 'jobs.log', 'resources.jsonl']:
        assert not (CASE / rel).exists(), '同じ出力へ再投入しない'
    assert not Path(spec['output']).exists()
    for name, sha in spec['observer_files'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha
    snapshot(SimpleNamespace(workspace=NR.parent.parent,
        output=ROOT / 'production_lambda20_eprice_fixed_before_start.json'))
    machine = {key: subprocess.check_output(cmd, text=True) for key, cmd in {
        'physical_cpu': ['/usr/sbin/sysctl', '-n', 'hw.physicalcpu'],
        'physical_memory_bytes': ['/usr/sbin/sysctl', '-n', 'hw.memsize'],
        'vm_stat': ['/usr/bin/vm_stat'], 'swap': ['/usr/sbin/sysctl', 'vm.swapusage'],
        'thermal': ['/usr/bin/pmset', '-g', 'therm']}.items()}
    machine.update(at=datetime.now().astimezone().isoformat(), free_disk_bytes=shutil.disk_usage(CASE).free,
        swap_window_minutes=10, swap_samples=(Path.home() / 'jobs/swap.tsv').read_text().splitlines()[-11:])
    save('production_lambda20_eprice_fixed_machine_before_start.json', machine)
    state(state='running_or_waiting', label='production_lambda20_eprice_fixed', production_started=False)
    command = ['/usr/bin/python3', JOBS, 'run', '--wait', '--owner',
        'Codex 動詞 指示15 固定E価格20', '--mem', str(spec['memory_reservation_gb']),
        '--disk-path', spec['output'], '--', PY, str(NR / 'run_case.py'), str(CASE)]
    with (CASE / 'jobs.log').open('x') as log:
        code = subprocess.call(command, stdout=log, stderr=subprocess.STDOUT)
    assert code == 0, code
    result = json.loads((CASE / 'result.json').read_text())
    done = json.loads((CASE / 'output/measurement/partial_done.json').read_text())
    count = json.loads((CASE / 'output/measurement/log_fallback_counts.json').read_text())
    manifest = [json.loads(line) for line in (CASE / 'output/manifest.jsonl').read_text().splitlines()]
    assert result['exit_code'] == 0 and len(manifest) == 1 and not manifest[0].get('error')
    assert count['completed_trials'] == done['completed_trials'] == manifest[0]['completed_trials'] == 20
    assert done['full_5000_completed'] is manifest[0]['full_5000_completed'] is False
    assert count['fallback_calls'] >= 0 and count['model_stats_modified'] is False
    state(state='logfix20_fixed_eprice_passed', fallback_calls=count['fallback_calls'],
          completed_trials=20, production_started=False)
except Exception as error:
    state(state='stopped', reason=repr(error), production_started=False)
    raise
